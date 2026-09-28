package com.avan.identity;

import java.io.IOException;
import java.net.URI;
import java.net.URLEncoder;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.time.Duration;
import java.util.Map;

import jakarta.ws.rs.core.MultivaluedMap;
import jakarta.ws.rs.core.Response;
import org.keycloak.authentication.AuthenticationFlowContext;
import org.keycloak.authentication.AuthenticationFlowError;
import org.keycloak.authentication.authenticators.browser.UsernamePasswordForm;
import org.keycloak.forms.login.LoginFormsProvider;
import org.keycloak.models.KeycloakSession;
import org.keycloak.util.JsonSerialization;

/**
 * Username/password form protected by Cloudflare Turnstile.
 *
 * Turnstile is validated server-side before Keycloak checks credentials.
 * A missing, expired, replayed or unverifiable token fails closed.
 */
public final class AvanCaptchaForm extends UsernamePasswordForm {
    private static final String VERIFY_URL =
        "https://challenges.cloudflare.com/turnstile/v0/siteverify";
    private static final String ACTION = "avan-login";
    private static final String TEST_SITE_KEY = "1x00000000000000000000AA";
    private static final String TEST_SECRET_KEY = "1x0000000000000000000000000000000AA";
    private static final Path SITE_KEY =
        Path.of("/run/secrets/avan_turnstile_site_key");
    private static final Path SECRET_KEY =
        Path.of("/run/secrets/avan_turnstile_secret_key");

    public AvanCaptchaForm(KeycloakSession session) {
        super(session);
    }

    @Override
    protected Response createLoginForm(LoginFormsProvider form) {
        try {
            form.setAttribute("turnstileSiteKey", read(SITE_KEY));
            form.setAttribute("turnstileAction", ACTION);
        } catch (RuntimeException ignored) {
            form.setError("سرویس ضدربات برای این نصب آماده نشده است.");
        }
        return super.createLoginForm(form);
    }

    @Override
    protected boolean validateForm(AuthenticationFlowContext context,
                                   MultivaluedMap<String, String> data) {
        String token = data.getFirst("cf-turnstile-response");
        if (!verify(token)) {
            context.failureChallenge(
                AuthenticationFlowError.INVALID_CREDENTIALS,
                createLoginForm(context.form().setError(
                    "اعتبارسنجی ضدربات نامعتبر، منقضی یا در دسترس نیست؛ دوباره تلاش کنید."
                ))
            );
            return false;
        }
        return super.validateForm(context, data);
    }

    private boolean verify(String token) {
        if (token == null) return false;
        token = token.trim();
        if (token.isEmpty() || token.length() > 2048 ||
            token.indexOf('\r') >= 0 || token.indexOf('\n') >= 0) {
            return false;
        }

        String siteKey;
        String secret;
        try {
            siteKey = read(SITE_KEY);
            secret = read(SECRET_KEY);
        } catch (RuntimeException ex) {
            return false;
        }

        if (productionRequired() &&
            (TEST_SITE_KEY.equals(siteKey) || TEST_SECRET_KEY.equals(secret))) {
            return false;
        }

        String body = "secret=" + enc(secret) + "&response=" + enc(token);
        HttpRequest request = HttpRequest.newBuilder(URI.create(VERIFY_URL))
            .timeout(Duration.ofSeconds(6))
            .header("Accept", "application/json")
            .header("Content-Type", "application/x-www-form-urlencoded")
            .POST(HttpRequest.BodyPublishers.ofString(body))
            .build();

        try {
            HttpClient client = HttpClient.newBuilder()
                .connectTimeout(Duration.ofSeconds(3))
                .followRedirects(HttpClient.Redirect.NEVER)
                .build();
            HttpResponse<String> response = client.send(
                request, HttpResponse.BodyHandlers.ofString(StandardCharsets.UTF_8));
            if (response.statusCode() != 200 || response.body().length() > 16384) {
                return false;
            }
            @SuppressWarnings("unchecked")
            Map<String,Object> result =
                JsonSerialization.readValue(response.body(), Map.class);
            if (!Boolean.TRUE.equals(result.get("success"))) {
                return false;
            }
            if (TEST_SITE_KEY.equals(siteKey) && TEST_SECRET_KEY.equals(secret)) {
                return true;
            }
            return ACTION.equals(result.get("action"));
        } catch (IOException | InterruptedException | RuntimeException ex) {
            if (ex instanceof InterruptedException) Thread.currentThread().interrupt();
            return false;
        }
    }

    private static String read(Path path) {
        try {
            String value = Files.readString(path, StandardCharsets.UTF_8).trim();
            if (value.isEmpty() || value.length() > 512 ||
                value.indexOf('\r') >= 0 || value.indexOf('\n') >= 0) {
                throw new IllegalStateException("Invalid Turnstile credential");
            }
            return value;
        } catch (IOException ex) {
            throw new IllegalStateException("Missing Turnstile credential", ex);
        }
    }

    private static boolean productionRequired() {
        String value = System.getenv("AVAN_TURNSTILE_REQUIRE_PRODUCTION");
        if (value == null) return false;
        value = value.trim().toLowerCase();
        return value.equals("1") || value.equals("true") ||
               value.equals("yes") || value.equals("on");
    }

    private static String enc(String value) {
        return URLEncoder.encode(value, StandardCharsets.UTF_8);
    }
}
