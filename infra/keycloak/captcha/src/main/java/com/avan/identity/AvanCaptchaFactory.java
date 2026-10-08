package com.avan.identity;

import org.keycloak.authentication.Authenticator;
import org.keycloak.authentication.authenticators.browser.UsernamePasswordFormFactory;
import org.keycloak.models.KeycloakSession;

public final class AvanCaptchaFactory extends UsernamePasswordFormFactory {
    public static final String ID = "avan-captcha-password";

    @Override public String getId() { return ID; }
    @Override public String getDisplayType() { return "AVAN username/password + Hybrid Anti-Bot"; }
    @Override public String getHelpText() { return "Uses Cloudflare Turnstile as primary verification with self-hosted ALTCHA fallback before checking credentials."; }
    @Override public Authenticator create(KeycloakSession session) { return new AvanCaptchaForm(session); }
}
