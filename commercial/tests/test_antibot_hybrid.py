"""Focused tests for AVAN hybrid anti-bot provider selection."""
import json
import unittest
from unittest.mock import patch

from commercial import turnstile


LOCAL={
    "provider":"altcha-self-hosted",
    "algorithm":"SHA-256",
    "challenge":"a"*64,
    "maxNumber":25000,
    "salt":"abcd?expires=9999999999&action=avan-bootstrap-login&jti="+"1"*36+"&",
    "signature":"b"*64,
    "action":"avan-bootstrap-login",
    "expiresIn":120,
}


class HybridAntiBotTests(unittest.TestCase):
    def test_public_config_exposes_cloudflare_primary_and_local_fallback(self):
        with patch.object(turnstile,"_cloudflare_credentials",
                          return_value=("site-key","secret-key")), \
             patch.object(turnstile,"_local_challenge",return_value=LOCAL):
            result=turnstile.public_config("avan-bootstrap-login")
        self.assertEqual(result["provider"],"hybrid")
        self.assertTrue(result["cloudflare"]["enabled"])
        self.assertEqual(result["cloudflare"]["site_key"],"site-key")
        self.assertEqual(result["local"]["provider"],"altcha-self-hosted")

    def test_cloudflare_can_operate_when_local_provider_is_unavailable(self):
        with patch.object(turnstile,"_cloudflare_credentials",
                          return_value=("site-key","secret-key")), \
             patch.object(turnstile,"_local_challenge",
                          side_effect=turnstile.TurnstileUnavailable("offline")):
            result=turnstile.public_config("avan-bootstrap-login")
        self.assertTrue(result["cloudflare"]["enabled"])
        self.assertIsNone(result["local"])

    def test_local_provider_can_operate_without_cloudflare_keys(self):
        with patch.object(turnstile,"_cloudflare_credentials",return_value=None), \
             patch.object(turnstile,"_local_challenge",return_value=LOCAL):
            result=turnstile.public_config("avan-bootstrap-login")
        self.assertFalse(result["cloudflare"]["enabled"])
        self.assertEqual(result["local"]["provider"],"altcha-self-hosted")

    def test_fails_closed_only_when_both_providers_are_unavailable(self):
        with patch.object(turnstile,"_cloudflare_credentials",return_value=None), \
             patch.object(turnstile,"_local_challenge",
                          side_effect=turnstile.TurnstileUnavailable("offline")):
            with self.assertRaises(turnstile.TurnstileUnavailable):
                turnstile.public_config("avan-bootstrap-login")

    def test_verification_dispatches_explicit_provider_envelope(self):
        cf=json.dumps({"provider":"cloudflare-turnstile","token":"cf-token"})
        local=json.dumps({"provider":"altcha-self-hosted","token":"local-token"})
        with patch.object(turnstile,"_verify_cloudflare",return_value=True) as cloudflare, \
             patch.object(turnstile,"_verify_local",return_value=True) as altcha:
            self.assertTrue(turnstile.verify(
                cf,action="avan-bootstrap-login",remote_ip="127.0.0.1"))
            cloudflare.assert_called_once_with(
                "cf-token","avan-bootstrap-login","127.0.0.1")
            self.assertTrue(turnstile.verify(
                local,action="avan-bootstrap-login",remote_ip="127.0.0.1"))
            altcha.assert_called_once_with("local-token","avan-bootstrap-login")

    def test_unknown_provider_is_rejected(self):
        token=json.dumps({"provider":"unknown","token":"anything"})
        self.assertFalse(turnstile.verify(
            token,action="avan-bootstrap-login",remote_ip="127.0.0.1"))


if __name__=="__main__":
    unittest.main()
