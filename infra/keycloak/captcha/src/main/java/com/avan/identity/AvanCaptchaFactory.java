package com.avan.identity;

import org.keycloak.authentication.Authenticator;
import org.keycloak.authentication.authenticators.browser.UsernamePasswordFormFactory;
import org.keycloak.authentication.authenticators.browser.UsernamePasswordForm;
import org.keycloak.models.KeycloakSession;

public final class AvanCaptchaFactory extends UsernamePasswordFormFactory {
    public static final String ID = "avan-captcha-password";

    @Override public String getId() { return ID; }
    @Override public String getDisplayType() { return "AVAN username and password (legacy flow compatibility)"; }
    @Override public String getHelpText() { return "Maintains existing AVAN browser flows without requesting a CAPTCHA."; }
    @Override public Authenticator create(KeycloakSession session) { return new UsernamePasswordForm(session); }
}
