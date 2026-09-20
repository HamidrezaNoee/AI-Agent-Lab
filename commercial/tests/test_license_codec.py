"""Offline commercial ECDSA licensing tests. All keys generated in memory."""
from datetime import datetime, timedelta, timezone
import unittest
import uuid
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec

from commercial.licensing.codec import LicenseInvalid, make_payload, sign_license, verify_license


class LicenseCodecTests(unittest.TestCase):
    def setUp(self):
        self.private=ec.generate_private_key(ec.SECP256R1())
        self.public=self.private.public_key().public_bytes(
            serialization.Encoding.PEM,serialization.PublicFormat.SubjectPublicKeyInfo)
        self.tenant=str(uuid.uuid4())
        self.other=str(uuid.uuid4())
        self.installation="A"*64
        self.expiry=(datetime.now(timezone.utc)+timedelta(days=30)).isoformat()

    def payload(self,**changes):
        args=dict(tenant_id=self.tenant,installation_id=self.installation,
                  customer="شرکت کاملاً ساختگی",max_users=25,
                  modules=[1,2,4],expires_at=self.expiry)
        args.update(changes)
        return make_payload(**args)

    def verify(self,token,**changes):
        args=dict(tenant_id=self.tenant,installation_id=self.installation,
                  active_users=5)
        args.update(changes)
        return verify_license(token,self.public,**args)

    def test_genuine_license_with_scoped_modules(self):
        original=self.payload()
        token=sign_license(original,self.private)
        confirmed=self.verify(token)
        self.assertEqual(confirmed["modules"],[1,2,4])
        self.assertEqual(confirmed["tenant_id"],self.tenant)
        self.assertEqual(confirmed["max_users"],25)

    def test_changed_payload_or_signature_is_rejected(self):
        token=sign_license(self.payload(),self.private)
        from base64 import urlsafe_b64encode
        import json
        h,s=token.split(".")
        changed=self.payload()
        changed["modules"]=[1,2,3,4]
        p=urlsafe_b64encode(json.dumps(changed).encode()).decode().rstrip("=")
        with self.assertRaises(LicenseInvalid):
            self.verify(p+"."+s)
        with self.assertRaises(LicenseInvalid):
            self.verify(h+"."+("A" if s[0]!="A" else "B")+s[1:])

    def test_wrong_tenant_installation_capacity_or_expiry_denied(self):
        token=sign_license(self.payload(),self.private)
        for options in ({"tenant_id":self.other},{"installation_id":"B"*64},
                        {"active_users":26},
                        {"now":datetime.now(timezone.utc)+timedelta(days=60)}):
            with self.subTest(options=options),self.assertRaises(LicenseInvalid):
                self.verify(token,**options)

    def test_unpurchased_feature_and_invalid_issuer_payload_denied(self):
        for features in ([2,3],[1,1],[1,5],[]):
            with self.subTest(features=features),self.assertRaises(LicenseInvalid):
                self.payload(modules=features)
        with self.assertRaises(LicenseInvalid):
            self.payload(installation_id="not-a-fingerprint")


if __name__=="__main__":
    unittest.main()
