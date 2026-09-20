"""In-process signed JWT -> REAL protected API -> REAL isolated SQL (LAB ONLY).

No API dependency override: every request traverses the actual Bearer auth dependency,
RS256 JWT validation, tenant DB membership, SQL session-context RLS and per-user ACL.
An EPHEMERAL key and in-memory public-key resolver replace the external test IdP.
This proves the integration path, NOT that a real OIDC provider is configured.
Never import/copy the local resolver into a deployed API or expose this test as a service.
"""
import os
import time
from unittest.mock import patch
from uuid import UUID

import jwt
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient

from commercial.api import app
from commercial.security import VerifiedTokenAuthenticator

ISSUER = "https://local-lab-issuer.example.test/"
AUDIENCE = "commercial-meeting-lab-api"
JWKS = "https://local-lab-issuer.example.test/jwks"
TENANT_A = UUID("11111111-1111-4111-8111-111111111111")
TENANT_B = UUID("22222222-2222-4222-8222-222222222222")


def check(value, label):
    if not value:
        raise AssertionError("FAIL: " + label)
    print("PASS: " + label)


def main():
    if os.getenv("RUN_COMMERCIAL_SQL_INTEGRATION") != "LAB_ONLY_NO_SERVER":
        raise SystemExit("Set RUN_COMMERCIAL_SQL_INTEGRATION=LAB_ONLY_NO_SERVER first.")
    if os.getenv("COMMERCIAL_MODE") != "lab" or (
        os.getenv("COMMERCIAL_SQL_DATABASE") != "EnterpriseProcess2_AI_Test"
    ):
        raise SystemExit("Only the isolated synthetic commercial test DB is allowed.")
    if os.getenv("COMMERCIAL_SQL_USER", "").lower() != "ai_commercialreader":
        raise SystemExit("Use the dedicated AI_CommercialReader test SQL login.")
    if os.getenv("COMMERCIAL_CHAT_ENABLED") == "1":
        raise SystemExit("Set COMMERCIAL_CHAT_ENABLED=0 (no external model calls).")
    if app.dependency_overrides:
        raise SystemExit("Refusing to test with any overridden FastAPI dependencies.")

    # Generated strictly in memory, with no password, files or production IdP.
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    public_key = private_key.public_key()
    authenticator = VerifiedTokenAuthenticator(
        ISSUER, AUDIENCE, JWKS, key_resolver=lambda _: public_key
    )

    def token(subject, tenant, **changes):
        now = int(time.time())
        claims = {
            "iss": ISSUER, "aud": AUDIENCE, "sub": subject,
            "tenant_id": str(tenant), "iat": now, "exp": now + 300,
        }
        claims.update(changes)
        return jwt.encode(claims, private_key, algorithm="RS256")

    def get(client, bearer, path="/v1/meetings"):
        headers = {} if bearer is None else {"Authorization": "Bearer " + bearer}
        return client.get(path, headers=headers)

    # Patch only the protected endpoint's TRUSTED public-key resolution.
    # No FastAPI auth-dependency bypass: _authenticated_principal still runs.
    with patch("commercial.api._verifier", return_value=authenticator):
        with TestClient(app) as client:
            check(get(client, None).status_code == 401,
                  "Unauthenticated protected request returns 401")
            check(get(client, "not-a-jwt").status_code == 401,
                  "Malformed bearer JWT is rejected")
            check(get(client, token("lab-alice", TENANT_A), "/v1/me").status_code == 200,
                  "Valid signed JWT reaches real tenant SQL membership")
            alice = get(client, token("lab-alice", TENANT_A))
            alice_ids = [m["meeting_id"] for m in alice.json()["meetings"]]
            check(alice.status_code == 200 and alice_ids
                  and all(mid == 900001 or 910001 <= mid <= 910100
                          for mid in alice_ids)
                  and (900001 in alice_ids or 910100 in alice_ids),
                  "Signed Alice token returns only explicitly granted A-001 / optional lab meetings")

            bob = get(client, token("lab-bob", TENANT_A))
            check(bob.status_code == 200
                  and [m["meeting_id"] for m in bob.json()["meetings"]] == [900002],
                  "Signed Bob token cannot inherit Alice's meeting grant")

            carol = get(client, token("lab-carol", TENANT_B))
            check(carol.status_code == 200
                  and [m["meeting_id"] for m in carol.json()["meetings"]] == [900003],
                  "Signed tenant B token is isolated from tenant A")

            # Change payload but retain original signature: tampering must fail
            # BEFORE the SQL membership or tenant routing step.
            original = token("lab-alice", TENANT_A)
            h, p, sig = original.split(".")
            import base64
            import json
            payload = json.loads(base64.urlsafe_b64decode(p + "=" * (-len(p) % 4)))
            payload["tenant_id"] = str(TENANT_B)
            forged_p = base64.urlsafe_b64encode(
                json.dumps(payload, separators=(",", ":")).encode("utf-8")
            ).decode("ascii").rstrip("=")
            check(get(client, ".".join((h, forged_p, sig))).status_code == 401,
                  "Tampered tenant claim fails signature verification")
            check(get(client, token("lab-alice", TENANT_A, aud="other-api")).status_code == 401,
                  "JWT issued for another API audience is rejected")
            check(get(client, token("lab-alice", TENANT_A,
                                    iss="https://untrusted.example.test/")).status_code == 401,
                  "JWT from untrusted issuer is rejected")
            now = int(time.time())
            check(get(client, token("lab-alice", TENANT_A,
                                    iat=now-500, exp=now-300)).status_code == 401,
                  "Expired signed JWT is rejected")
            check(get(client, token("lab-alice", TENANT_B)).status_code == 403,
                  "Valid signature is insufficient without membership in claimed tenant")
            check(get(client, token("lab-unknown", TENANT_A)).status_code == 403,
                  "Unknown signed subject is denied by real SQL membership")
            answer = client.post(
                "/v1/chat/answer",
                headers={"Authorization": "Bearer " + token("lab-alice", TENANT_A)},
                json={"question": "گمرک و شماره شاسی", "meeting_id": 900001},
            )
            check(answer.status_code == 503,
                  "Signed-token test still leaves external OpenAI chat disabled")

    print("PASS: IN-PROCESS SIGNED JWT + REAL SQL/API LAB integration completed.")
    print("SCOPE: local ephemeral test issuer only; NO external IdP, web server or LLM.")


if __name__ == "__main__":
    main()
