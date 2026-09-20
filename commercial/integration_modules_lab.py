"""Optional modules paid-license gating integration against FICTIONAL TEST SQL only.

Prerequisite SQL: 14,15,16,17. Uses a local EPHEMERAL RSA signer with the real
FastAPI auth dependency; NEVER host this test or copy its key resolver to API.
Writes only temporary tenant-admin toggles in synthetic TenantModule and audit.
"""
import os
import time
from unittest.mock import patch

import jwt
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient

from commercial.api import app
from commercial.security import VerifiedTokenAuthenticator

A = "11111111-1111-4111-8111-111111111111"
B = "22222222-2222-4222-8222-222222222222"
ISS = "https://ephemeral-module-lab.example.test/"
AUD = "commercial-module-lab-api"
JWKS = ISS + "jwks"


def check(condition, message):
    if not condition:
        raise AssertionError("FAIL: " + message)
    print("PASS: " + message)


def main():
    if (os.getenv("RUN_COMMERCIAL_SQL_INTEGRATION") != "LAB_ONLY_NO_SERVER" or
        os.getenv("COMMERCIAL_MODE") != "lab" or
        os.getenv("COMMERCIAL_SQL_DATABASE") != "EnterpriseProcess2_AI_Test" or
        os.getenv("COMMERCIAL_SQL_USER","").lower() != "ai_commercialreader" or
        os.getenv("COMMERCIAL_CHAT_ENABLED") == "1" or
        app.dependency_overrides):
        raise SystemExit("Real TEST SQL + reader + CHAT=0, no auth overrides required.")

    private_key = rsa.generate_private_key(public_exponent=65537,key_size=2048)
    auth = VerifiedTokenAuthenticator(ISS,AUD,JWKS,
                                      key_resolver=lambda _:private_key.public_key())

    def headers(subject, tenant):
        now=int(time.time())
        token=jwt.encode({"iss":ISS,"aud":AUD,"sub":subject,
                          "tenant_id":tenant,"iat":now,"exp":now+300},
                         private_key,algorithm="RS256")
        return {"Authorization":"Bearer "+token}

    with patch("commercial.api._verifier",return_value=auth):
        with TestClient(app) as client:
            ha, hb, hc, hadmin = (headers("lab-alice",A),headers("lab-bob",A),
                                 headers("lab-carol",B),headers("lab-admin",A))
            mods=client.get("/v1/modules",headers=ha)
            check(mods.status_code==200, "Alice can inspect own purchased modules")
            states={m["module_code"]:m for m in mods.json()["modules"]}
            check(states[1]["active"] and states[2]["active"]
                  and states[3]["licensed"] and not states[3]["active"]
                  and states[4]["active"], "Tenant A module 1,2,4 ON; module 3 purchased but OFF")
            cmods=client.get("/v1/modules",headers=hc)
            check(cmods.status_code==200 and all(
                not x["active"] for x in cmods.json()["modules"] if x["module_code"]!=1),
                "Tenant B has no access to A's optional licenses")
            check(client.get("/v1/secretary/preparation/900001",headers=hc).status_code==403,
                  "Unlicensed tenant B cannot access secretary module")
            check(client.get("/v1/analytics/status-overview",headers=ha).status_code==403,
                  "Purchased but disabled analytics module denies access")
            check(client.put("/v1/admin/modules/3",json={"enabled":True},headers=ha).status_code==403,
                  "Viewer cannot toggle even purchased modules")
            check(client.put("/v1/admin/modules/3",json={"enabled":True},headers=hc).status_code==403,
                  "Unlicensed tenant cannot self-activate a module")

            # Ensure prior synthetic module state is restored, even on failed checks.
            changed=False
            try:
                enabled=client.put("/v1/admin/modules/3",json={"enabled":True},
                                   headers=hadmin)
                check(enabled.status_code==200 and enabled.json()["module"]["enabled"],
                      "Tenant admin enables an already licensed analytics module")
                changed=True
                report=client.get("/v1/analytics/status-overview",headers=ha)
                check(report.status_code==200 and
                      report.json()["total_visible_meetings"]>=101,
                      "Enabled analytics counts Alice's 100+ explicitly granted test meetings")
                check(client.get("/v1/analytics/status-overview",headers=hc).status_code==403,
                      "Tenant B is still barred from tenant A's enabled analytics")
            finally:
                if changed:
                    restored=client.put("/v1/admin/modules/3",json={"enabled":False},
                                        headers=hadmin)
                    check(restored.status_code==200 and
                          not restored.json()["module"]["enabled"],
                          "Synthetic analytics module restored to OFF")
            prep=client.get("/v1/secretary/preparation/910001",headers=ha)
            check(prep.status_code==200 and
                  prep.json()["processmaker_write_performed"] is False,
                  "Purchased secretary module returns read-only permitted meeting draft")
            monitoring=client.get("/v1/monitoring/overdue",headers=ha)
            check(monitoring.status_code==200 and monitoring.json()["returned"]>0
                  and all(910001<=a["meeting_id"]<=910100 for a in monitoring.json()["alerts"]),
                  "Purchased monitoring shows only permitted synthetic overdue actions")
    print("PASS: real SQL + signed JWT + optional module entitlement/toggle lab tests completed.")
    print("SCOPE: only fictitious test purchases; NO checkout, external IdP, voice, reminders or model API.")


if __name__=="__main__":
    main()
