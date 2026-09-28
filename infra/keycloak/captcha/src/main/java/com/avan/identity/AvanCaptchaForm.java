package com.avan.identity;

import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.SecureRandom;
import java.util.Base64;
import java.util.Locale;
import jakarta.ws.rs.core.MultivaluedMap;
import jakarta.ws.rs.core.Response;
import org.keycloak.authentication.AuthenticationFlowContext;
import org.keycloak.authentication.AuthenticationFlowError;
import org.keycloak.authentication.authenticators.browser.UsernamePasswordForm;
import org.keycloak.forms.login.LoginFormsProvider;
import org.keycloak.models.AuthenticationSessionModel;
import org.keycloak.models.KeycloakSession;

/** Captcha is bound to the Keycloak authentication session, consumed before any password check. */
public final class AvanCaptchaForm extends UsernamePasswordForm {
    private static final SecureRandom RANDOM = new SecureRandom();
    private static final String ALPHABET = "23456789ABCDEFGHJKLMNPQRSTUVWXYZ";
    private static final String ANSWER = "avan.captcha.answer";
    private static final String ISSUED = "avan.captcha.issued";
    private static final String ATTEMPTS = "avan.captcha.attempts";
    private String image;

    public AvanCaptchaForm(KeycloakSession session) { super(session); }

    @Override public void authenticate(AuthenticationFlowContext context) {
        issue(context.getAuthenticationSession());
        super.authenticate(context);
    }

    @Override protected Response createLoginForm(LoginFormsProvider form) {
        // The image is a data URI: no separate endpoint that can leak the answer or be cached.
        form.setAttribute("avanCaptchaImage", image);
        return super.createLoginForm(form);
    }

    @Override protected boolean validateForm(AuthenticationFlowContext context,
                                             MultivaluedMap<String, String> data) {
        AuthenticationSessionModel session = context.getAuthenticationSession();
        String expected = session.getAuthNote(ANSWER);
        String issued = session.getAuthNote(ISSUED);
        String supplied = data.getFirst("avan_captcha");
        if (supplied != null) supplied = supplied.trim().toUpperCase(Locale.ROOT);
        session.removeAuthNote(ANSWER);
        session.removeAuthNote(ISSUED);
        int attempts;
        try { attempts = Integer.parseInt(session.getAuthNote(ATTEMPTS)); }
        catch (RuntimeException ignored) { attempts = 0; }
        long age;
        try { age = System.currentTimeMillis() - Long.parseLong(issued); }
        catch (RuntimeException ignored) { age = Long.MAX_VALUE; }
        if (attempts >= 5 || expected == null || issued == null || supplied == null ||
            !supplied.matches("[2-9A-HJ-NP-Z]{6}") ||
            age < 0 || age > 120000 ||
            !MessageDigest.isEqual(expected.getBytes(StandardCharsets.US_ASCII),
                                   supplied.getBytes(StandardCharsets.US_ASCII))) {
            session.setAuthNote(ATTEMPTS, Integer.toString(attempts + 1));
            issue(session);
            context.failureChallenge(AuthenticationFlowError.INVALID_CREDENTIALS,
                createLoginForm(context.form().setError("کد امنیتی اشتباه یا منقضی شده است؛ تصویر جدید را وارد کنید.")));
            return false;
        }
        // Rotate even on a wrong password: no challenge can be replayed.
        issue(session);
        return super.validateForm(context, data);
    }

    private void issue(AuthenticationSessionModel session) {
        StringBuilder code = new StringBuilder(6);
        for (int i = 0; i < 6; ++i) code.append(ALPHABET.charAt(RANDOM.nextInt(ALPHABET.length())));
        session.setAuthNote(ANSWER, code.toString());
        session.setAuthNote(ISSUED, Long.toString(System.currentTimeMillis()));
        StringBuilder svg = new StringBuilder("<svg xmlns='http://www.w3.org/2000/svg' width='260' height='85' viewBox='0 0 260 85'><rect width='260' height='85' rx='12' fill='#ecf4f5'/>");
        for (int i = 0; i < 16; ++i) {
            int x1 = RANDOM.nextInt(260), y1 = RANDOM.nextInt(85);
            svg.append("<path d='M").append(x1).append(' ').append(y1).append(" l")
               .append(RANDOM.nextInt(110) - 55).append(' ').append(RANDOM.nextInt(70) - 35)
               .append("' stroke='#8bafba' stroke-width='1' opacity='.55'/>");
        }
        for (int i = 0; i < 6; ++i) {
            int x = 23 + i * 38 + RANDOM.nextInt(5), y = 53 + RANDOM.nextInt(12);
            int rotation = RANDOM.nextInt(27) - 13;
            svg.append("<text x='").append(x).append("' y='").append(y)
               .append("' transform='rotate(").append(rotation).append(' ').append(x).append(' ').append(y)
               .append(")' font-family='monospace' font-weight='900' font-size='39' fill='#123d55'>")
               .append(code.charAt(i)).append("</text>");
        }
        svg.append("</svg>");
        image = "data:image/svg+xml;base64," + Base64.getEncoder().encodeToString(
            svg.toString().getBytes(StandardCharsets.UTF_8));
    }
}
