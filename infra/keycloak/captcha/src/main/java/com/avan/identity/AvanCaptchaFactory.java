package com.avan.identity;

import org.keycloak.authentication.Authenticator;
import org.keycloak.authentication.authenticators.browser.UsernamePasswordFormFactory;
import org.keycloak.models.KeycloakSession;

public final class AvanCaptchaFactory extends UsernamePasswordFormFactory {
    public static final String ID = "avan-captcha-password";

    @Override public String getId() { return ID; }
    @Override public String getDisplayType() { return "AVAN username, password and image challenge"; }
    @Override public String getHelpText() { return "One-use server-validated image challenge before password authentication."; }
    @Override public Authenticator create(KeycloakSession session) { return new AvanCaptchaForm(session); }
}
