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
 * Hybrid AVAN anti-bot:
 * Cloudflare Turnstile Managed is primary and the self-hosted ALTCHA-compatible
 * proof-of-work service is the automatic fallback. The password is not checked
 * until one provider verifies successfully.
 */
public final class AvanCaptchaForm extends UsernamePasswordForm {
    private static final String ACTION = "avan-login";
    private static final String SERVICE_URL = serviceUrl();
    private static final String VERIFY_URL =
        "https://challenges.cloudflare.com/turnstile/v0/siteverify";
    private static final Path SITE_KEY =
        Path.of("/run/secrets/avan_turnstile_site_key");
    private static final Path SECRET_KEY =
        Path.of("/run/secrets/avan_turnstile_secret_key");
    private static final String TEST_SITE_KEY = "1x00000000000000000000AA";
    private static final String TEST_SECRET_KEY =
        "1x0000000000000000000000000000000AA";
    private static final HttpClient CLIENT = HttpClient.newBuilder()
        .connectTimeout(Duration.ofSeconds(2))
        .followRedirects(HttpClient.Redirect.NEVER)
        .build();

    public AvanCaptchaForm(KeycloakSession session) {
        super(session);
    }

    @Override
    protected Response createLoginForm(LoginFormsProvider form) {
        try {
            Map<String,Object> challenge = challenge();
            form.setAttribute("antibotProvider", string(challenge, "provider"));
            form.setAttribute("antibotAction", string(challenge, "action"));
            form.setAttribute("antibotAlgorithm", string(challenge, "algorithm"));
            form.setAttribute("antibotChallenge", string(challenge, "challenge"));
            form.setAttribute("antibotSalt", string(challenge, "salt"));
            form.setAttribute("antibotSignature", string(challenge, "signature"));
            form.setAttribute("antibotMaxNumber", integer(challenge, "maxNumber"));
            form.setAttribute("antibotExpiresIn", integer(challenge, "expiresIn"));

            String siteKey = cloudflareSiteKey();
            if (!siteKey.isEmpty()) {
                form.setAttribute("turnstileSiteKey", siteKey);
                form.setAttribute("turnstileAction", ACTION);
                form.setAttribute("turnstileTimeoutMs", 2500);
            }
        } catch (RuntimeException ex) {
            form.setError("سرویس ضدربات داخلی آوان در دسترس نیست.");
        }
        return super.createLoginForm(form);
    }

    @Override
    protected boolean validateForm(AuthenticationFlowContext context,
                                   MultivaluedMap<String, String> data) {
        String envelope = data.getFirst("avan-antibot");
        if (!verify(envelope)) {
            LoginFormsProvider form = context.form().setError(
                "اعتبارسنجی ضدربات نامعتبر یا منقضی شده است؛ دوباره تلاش کنید."
            );
            if ("cloudflare-turnstile".equals(providerOf(envelope))) {
                form.setAttribute("antibotForceLocal", true);
            }
            context.failureChallenge(
                AuthenticationFlowError.INVALID_CREDENTIALS,
                createLoginForm(form)
            );
            return false;
        }
        return super.validateForm(context, data);
    }

    private static Map<String,Object> challenge() {
        HttpRequest request = HttpRequest.newBuilder(
                URI.create(SERVICE_URL + "/v1/challenge?action=" + ACTION))
            .timeout(Duration.ofSeconds(4))
            .header("Accept", "application/json")
            .GET()
            .build();
        try {
            HttpResponse<String> response = CLIENT.send(
                request, HttpResponse.BodyHandlers.ofString(StandardCharsets.UTF_8));
            if (response.statusCode() != 200 || response.body().length() > 8192) {
                throw new IllegalStateException("Anti-bot challenge unavailable");
            }
            @SuppressWarnings("unchecked")
            Map<String,Object> result =
                JsonSerialization.readValue(response.body(), Map.class);
            if (!"altcha-self-hosted".equals(result.get("provider")) ||
                !ACTION.equals(result.get("action")) ||
                !"SHA-256".equals(result.get("algorithm"))) {
                throw new IllegalStateException("Invalid anti-bot challenge");
            }
            integer(result, "maxNumber");
            string(result, "challenge");
            string(result, "salt");
            string(result, "signature");
            return result;
        } catch (IOException | InterruptedException | RuntimeException ex) {
            if (ex instanceof InterruptedException) Thread.currentThread().interrupt();
            throw new IllegalStateException("Anti-bot service unavailable", ex);
        }
    }

    private static String providerOf(String envelope) {
        if (envelope == null || envelope.isBlank() || envelope.length() > 12288) {
            return "";
        }
        try {
            @SuppressWarnings("unchecked")
            Map<String,Object> value = JsonSerialization.readValue(envelope, Map.class);
            Object provider = value.get("provider");
            return provider instanceof String ? (String)provider : "";
        } catch (IOException | RuntimeException ex) {
            return "";
        }
    }

    private static boolean verify(String envelope) {
        if (envelope == null) return false;
        envelope = envelope.trim();
        if (envelope.isEmpty() || envelope.length() > 12288 ||
            envelope.indexOf('\r') >= 0 || envelope.indexOf('\n') >= 0) {
            return false;
        }
        try {
            @SuppressWarnings("unchecked")
            Map<String,Object> value = JsonSerialization.readValue(envelope, Map.class);
            Object provider = value.get("provider");
            Object token = value.get("token");
            if (!(provider instanceof String) || !(token instanceof String)) {
                return false;
            }
            if ("cloudflare-turnstile".equals(provider)) {
                return verifyCloudflare((String)token);
            }
            if ("altcha-self-hosted".equals(provider)) {
                return verifyLocal((String)token);
            }
            return false;
        } catch (IOException | RuntimeException ex) {
            return false;
        }
    }

    private static boolean verifyLocal(String payload) {
        if (payload == null || payload.isBlank() || payload.length() > 8192 ||
            payload.indexOf('\r') >= 0 || payload.indexOf('\n') >= 0) {
            return false;
        }
        try {
            String body = JsonSerialization.writeValueAsString(
                Map.of("payload", payload, "action", ACTION));
            HttpRequest request = HttpRequest.newBuilder(
                    URI.create(SERVICE_URL + "/v1/verify"))
                .timeout(Duration.ofSeconds(4))
                .header("Accept", "application/json")
                .header("Content-Type", "application/json")
                .POST(HttpRequest.BodyPublishers.ofString(body, StandardCharsets.UTF_8))
                .build();
            HttpResponse<String> response = CLIENT.send(
                request, HttpResponse.BodyHandlers.ofString(StandardCharsets.UTF_8));
            if (response.statusCode() != 200 || response.body().length() > 8192) {
                return false;
            }
            @SuppressWarnings("unchecked")
            Map<String,Object> result =
                JsonSerialization.readValue(response.body(), Map.class);
            return Boolean.TRUE.equals(result.get("verified"));
        } catch (IOException | InterruptedException | RuntimeException ex) {
            if (ex instanceof InterruptedException) Thread.currentThread().interrupt();
            return false;
        }
    }

    private static boolean verifyCloudflare(String token) {
        String siteKey = cloudflareSiteKey();
        String secret = readOptional(SECRET_KEY);
        if (siteKey.isEmpty() || secret.isEmpty() || token == null ||
            token.isBlank() || token.length() > 4096 ||
            token.indexOf('\r') >= 0 || token.indexOf('\n') >= 0) {
            return false;
        }
        if (productionRequired() &&
            (TEST_SITE_KEY.equals(siteKey) || TEST_SECRET_KEY.equals(secret))) {
            return false;
        }

        String body = "secret=" + enc(secret) + "&response=" + enc(token);
        HttpRequest request = HttpRequest.newBuilder(URI.create(VERIFY_URL))
            .timeout(Duration.ofSeconds(5))
            .header("Accept", "application/json")
            .header("Content-Type", "application/x-www-form-urlencoded")
            .POST(HttpRequest.BodyPublishers.ofString(body, StandardCharsets.UTF_8))
            .build();

        try {
            HttpResponse<String> response = CLIENT.send(
                request, HttpResponse.BodyHandlers.ofString(StandardCharsets.UTF_8));
            if (response.statusCode() != 200 || response.body().length() > 16384) {
                return false;
            }
            @SuppressWarnings("unchecked")
            Map<String,Object> result =
                JsonSerialization.readValue(response.body(), Map.class);
            if (!Boolean.TRUE.equals(result.get("success"))) return false;
            if (TEST_SITE_KEY.equals(siteKey) && TEST_SECRET_KEY.equals(secret)) {
                return true;
            }
            return ACTION.equals(result.get("action"));
        } catch (IOException | InterruptedException | RuntimeException ex) {
            if (ex instanceof InterruptedException) Thread.currentThread().interrupt();
            return false;
        }
    }

    private static String cloudflareSiteKey() {
        String site = readOptional(SITE_KEY);
        String secret = readOptional(SECRET_KEY);
        if (site.isEmpty() || secret.isEmpty()) return "";
        if (productionRequired() &&
            (TEST_SITE_KEY.equals(site) || TEST_SECRET_KEY.equals(secret))) {
            return "";
        }
        return site;
    }

    private static String readOptional(Path path) {
        try {
            String value = Files.readString(path, StandardCharsets.UTF_8).trim();
            if (value.isEmpty() || value.length() > 512 ||
                value.indexOf('\r') >= 0 || value.indexOf('\n') >= 0) {
                return "";
            }
            return value;
        } catch (IOException ex) {
            return "";
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

    private static String serviceUrl() {
        String value = System.getenv("AVAN_ANTIBOT_URL");
        if (value == null || value.isBlank()) return "http://antibot:8090";
        value = value.trim();
        if (!value.matches("^http://[a-zA-Z0-9.-]+(?::[0-9]{1,5})?$")) {
            throw new IllegalStateException("Invalid AVAN_ANTIBOT_URL");
        }
        return value.replaceAll("/+$", "");
    }

    private static String string(Map<String,Object> map, String key) {
        Object value = map.get(key);
        if (!(value instanceof String) || ((String)value).isBlank() ||
            ((String)value).length() > 4096) {
            throw new IllegalStateException("Invalid anti-bot field " + key);
        }
        return (String)value;
    }

    private static int integer(Map<String,Object> map, String key) {
        Object value = map.get(key);
        int result;
        if (value instanceof Number) result = ((Number)value).intValue();
        else {
            try { result = Integer.parseInt(String.valueOf(value)); }
            catch (NumberFormatException ex) {
                throw new IllegalStateException("Invalid anti-bot number " + key, ex);
            }
        }
        if (result < 1 || result > 250000) {
            throw new IllegalStateException("Invalid anti-bot number " + key);
        }
        return result;
    }
}
