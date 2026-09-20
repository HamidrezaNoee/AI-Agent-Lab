"""Real SQL + synthetic directory hierarchy + actual JWT validation (LAB ONLY).

Requires test DBA migrations 19 and fictional fixture 22. Uses only in-memory
RSA signer; NO ProcessMaker network, no real identity provider, no writes,
no OpenAI, and NO operational MTG database.
"""
import os
import time
from unittest.mock import patch
from cryptography.hazmat.primitives.asymmetric import rsa
import jwt
from fastapi.testclient import TestClient

from commercial.api import app
from commercial.security import VerifiedTokenAuthenticator

A="11111111-1111-4111-8111-111111111111"
B="22222222-2222-4222-8222-222222222222"
ISS="https://fictional-hierarchy-lab.example.test/"
AUD="fictional-hierarchy-lab-api"


def check(ok,text):
    if not ok:raise AssertionError("FAIL: "+text)
    print("PASS: "+text)


def main():
    if (os.getenv("RUN_COMMERCIAL_SQL_INTEGRATION")!="LAB_ONLY_NO_SERVER" or
        os.getenv("COMMERCIAL_MODE")!="lab" or
        os.getenv("COMMERCIAL_SQL_DATABASE")!="EnterpriseProcess2_AI_Test" or
        os.getenv("COMMERCIAL_SQL_USER","").lower()!="ai_commercialreader" or
        os.getenv("COMMERCIAL_CHAT_ENABLED")=="1" or app.dependency_overrides):
        raise SystemExit("Isolated TEST SQL and dedicated reader, CHAT=0 required.")
    key=rsa.generate_private_key(public_exponent=65537,key_size=2048)
    verifier=VerifiedTokenAuthenticator(ISS,AUD,ISS+"jwks",
                                        key_resolver=lambda _:key.public_key())
    def h(sub,tenant,roles=()):
        now=int(time.time())
        claims={"iss":ISS,"aud":AUD,"sub":sub,"tenant_id":tenant,
                "iat":now,"exp":now+300,"realm_access":{"roles":list(roles)}}
        return {"Authorization":"Bearer "+jwt.encode(claims,key,algorithm="RS256")}

    def all_ids(client,headers):
        ids=[];cursor=None
        for iteration in range(10):
            args={"limit":25}
            if cursor is not None:args["cursor"]=cursor
            res=client.get("/v2/meetings/page",headers=headers,params=args)
            check(res.status_code==200,"Authorized hierarchy meeting page returned")
            body=res.json()
            ids.extend(m["meeting_id"] for m in body["meetings"])
            if not body["has_more"]:return ids,body["scope"]
            cursor=body["next_cursor"]
            if cursor is None:raise AssertionError("Missing hierarchy pagination cursor")
        raise AssertionError("Hierarchy pagination did not terminate")

    with patch("commercial.api._verifier",return_value=verifier):
        with TestClient(app) as client:
            check(client.get("/v2/meetings/page").status_code==401,
                  "Directory API refuses missing bearer token")
            alice,scope=all_ids(client,h("lab-alice",A))
            check(scope=="self-and-org-subtree" and len(alice)==len(set(alice))==102
                  and {900001,900002,910001,910100}.issubset(alice),
                  "Expert Alice sees own and Bob subordinate meetings without duplicate/missing pages")
            bob,scope=all_ids(client,h("lab-bob",A))
            check(scope=="self-and-org-subtree" and bob==[900002],
                  "Expert Bob cannot inspect supervisor's or unrelated meetings")
            mgr,scope=all_ids(client,h("lab-manager",A))
            check(scope=="tenant" and set(mgr)==set(alice),
                  "Tenant Manager sees all 102 fictional A meetings without being an actor")
            admin,scope=all_ids(client,h("lab-admin",A,("SysAdmin",)))
            check(scope=="tenant" and set(admin)==set(mgr),
                  "Verified tenant SysAdmin sees all same-tenant meetings")
            carol,scope=all_ids(client,h("lab-carol",B,("GodAdmin",)))
            check(carol==[900003],
                  "GodAdmin token role alone DOES NOT bypass other-tenant data boundaries")
            for sub,tenant in (("lab-bob",B),("lab-carol",A),("lab-unknown",A)):
                result=client.get("/v2/meetings/page",headers=h(sub,tenant))
                check(result.status_code==403,
                      "Unknown/cross-tenant directory identity rejected")
            denied=client.get("/v2/admin/processmaker/users/preview",
                              headers=h("lab-alice",A,("SysAdmin",)))
            check(denied.status_code==403,
                  "Forged administrative claim does not override SQL directory role")
            check(client.get("/v2/admin/processmaker/users/preview",
                             headers=h("lab-admin",A)).status_code==403,
                  "SQL SysAdmin alone without signed Keycloak role is insufficient")
            check(client.get("/v2/admin/processmaker/users/preview",
                             headers=h("lab-admin",A,("SysAdmin",))).status_code==503,
                  "Verified SysAdmin preview fails safely when PM source is unconfigured")
    print("PASS: real SQL + signed identity + tenant hierarchy ACL regression completed.")
    print("SCOPE: fictional directory, no real PM or IdP, no production meeting data.")


if __name__=="__main__":
    main()
