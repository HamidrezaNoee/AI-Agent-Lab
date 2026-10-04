package com.avan.identity;

import java.io.IOException;
import java.net.URI;
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
 * AVAN login anti-bot adapter.
 *
 * Keycloak does not implement a second CAPTCHA stack. It delegates challenge
 * creation and verification to the AVAN security bridge, which uses the exact
 * same commercial.turnstile implementation as /admin/.
 */
public final class AvanCaptchaForm extends UsernamePasswordForm {
    private static final String ACTION = "avan-login";
    private static final String BRIDGE_URL = bridgeUrl();
    private static final Path BRIDGE_TOKEN = Path.of(
        System.getenv().getOrDefault(
            "AVAN_SECURITY_BRIDGE_TOKEN_PATH",
            "/run/secrets/avan_bff_client_secret"
        )
    );
    private static final HttpClient CLIENT = HttpClient.newBuilder()
        .connectTimeout(Duration.ofSeconds(2))
        .followRedirects(HttpClient.Redirect.NEVER)
        .build();

    public AvanCaptchaForm(KeycloakSession session) {
        super(session);
    }

    @Override
    protected Response createLoginForm(LoginFormsProvider form) {
        boolean providerReady = false;
        try {
            Map<String,Object> config = challenge();
            if (Boolean.TRUE.equals(config.get("localAvailable"))) {
                form.setAttribute("antibotProvider", string(config, "provider"));
                form.setAttribute("antibotAction", string(config, "action"));
                form.setAttribute("antibotAlgorithm", string(config, "algorithm"));
                form.setAttribute("antibotChallenge", string(config, "challenge"));
                form.setAttribute("antibotSalt", string(config, "salt"));
                form.setAttribute("antibotSignature", string(config, "signature"));
                form.setAttribute("antibotMaxNumber", integer(config, "maxNumber", 250000));
                form.setAttribute("antibotExpiresIn", integer(config, "expiresIn", 3600));
                providerReady = true;
            }

            String siteKey = optionalString(config, "turnstileSiteKey");
            if (!siteKey.isEmpty()) {
                form.setAttribute("turnstileSiteKey", siteKey);
                form.setAttribute("turnstileAction", ACTION);
                form.setAttribute(
                    "turnstileTimeoutMs",
                    integer(config, "turnstileTimeoutMs", 10000)
                );
                providerReady = true;
            }
        } catch (RuntimeException ignored) {
            // Fail closed below. The AVAN bridge remains the single source of truth.
        }

        if (!providerReady) {
            form.setError("سرویس امنیتی آوان موقتاً آماده نیست.");
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
                URI.create(BRIDGE_URL + "/challenge?action=" + ACTION))
            .timeout(Duration.ofSeconds(5))
            .header("Accept", "application/json")
            .header("X-AVAN-Internal-Token", bridgeToken())
            .GET()
            .build();
        try {
            HttpResponse<String> response = CLIENT.send(
                request,
                HttpResponse.BodyHandlers.ofString(StandardCharsets.UTF_8)
            );
            if (response.statusCode() != 200 || response.body().length() > 16384) {
                throw new IllegalStateException("AVAN security bridge unavailable");
            }
            @SuppressWarnings("unchecked")
            Map<String,Object> result =
                JsonSerialization.readValue(response.body(), Map.class);
            if (!ACTION.equals(result.get("action"))) {
                throw new IllegalStateException("Invalid AVAN security bridge action");
            }
            boolean local = Boolean.TRUE.equals(result.get("localAvailable"));
            String siteKey = optionalString(result, "turnstileSiteKey");
            if (!local && siteKey.isEmpty()) {
                throw new IllegalStateException("No AVAN anti-bot provider available");
            }
            if (local) {
                if (!"altcha-self-hosted".equals(result.get("provider")) ||
                    !"SHA-256".equals(result.get("algorithm"))) {
                    throw new IllegalStateException("Invalid AVAN local challenge");
                }
                integer(result, "maxNumber", 250000);
                string(result, "challenge");
                string(result, "salt");
                string(result, "signature");
            }
            return result;
        } catch (IOException | InterruptedException | RuntimeException ex) {
            if (ex instanceof InterruptedException) {
                Thread.currentThread().interrupt();
            }
            throw new IllegalStateException("AVAN security bridge unavailable", ex);
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
            String body = JsonSerialization.writeValueAsString(
                Map.of("action", ACTION, "envelope", envelope)
            );
            HttpRequest request = HttpRequest.newBuilder(
                    URI.create(BRIDGE_URL + "/verify"))
                .timeout(Duration.ofSeconds(7))
                .header("Accept", "application/json")
                .header("Content-Type", "application/json")
                .header("X-AVAN-Internal-Token", bridgeToken())
                .POST(HttpRequest.BodyPublishers.ofString(
                    body, StandardCharsets.UTF_8))
                .build();
            HttpResponse<String> response = CLIENT.send(
                request,
                HttpResponse.BodyHandlers.ofString(StandardCharsets.UTF_8)
            );
            if (response.statusCode() != 200 || response.body().length() > 8192) {
                return false;
            }
            @SuppressWarnings("unchecked")
            Map<String,Object> result =
                JsonSerialization.readValue(response.body(), Map.class);
            return Boolean.TRUE.equals(result.get("verified"));
        } catch (IOException | InterruptedException | RuntimeException ex) {
            if (ex instanceof InterruptedException) {
                Thread.currentThread().interrupt();
            }
            return false;
        }
    }

    private static String providerOf(String envelope) {
        if (envelope == null || envelope.isBlank() || envelope.length() > 12288) {
            return "";
        }
        try {
            @SuppressWarnings("unchecked")
            Map<String,Object> value =
                JsonSerialization.readValue(envelope, Map.class);
            Object provider = value.get("provider");
            return provider instanceof String ? (String)provider : "";
        } catch (IOException | RuntimeException ex) {
            return "";
        }
    }

    private static String bridgeToken() {
        try {
            String value =
                Files.readString(BRIDGE_TOKEN, StandardCharsets.UTF_8).trim();
            if (value.length() < 16 || value.length() > 4096 ||
                value.indexOf('\r') >= 0 || value.indexOf('\n') >= 0) {
                throw new IllegalStateException("Invalid AVAN bridge token");
            }
            return value;
        } catch (IOException ex) {
            throw new IllegalStateException("AVAN bridge token unavailable", ex);
        }
    }

    private static String bridgeUrl() {
        String value = System.getenv("AVAN_SECURITY_BRIDGE_URL");
        if (value == null || value.isBlank()) {
            return "http://avan:8188/internal/security";
        }
        value = value.trim().replaceAll("/+$", "");
        if (!value.matches("^http://[a-zA-Z0-9.-]+(?::[0-9]{1,5})?/internal/security$")) {
            throw new IllegalStateException("Invalid AVAN security bridge URL");
        }
        return value;
    }

    private static String string(Map<String,Object> map, String key) {
        Object value = map.get(key);
        if (!(value instanceof String) || ((String)value).isBlank() ||
            ((String)value).length() > 4096) {
            throw new IllegalStateException("Invalid AVAN security field " + key);
        }
        return (String)value;
    }

    private static String optionalString(Map<String,Object> map, String key) {
        Object value = map.get(key);
        if (!(value instanceof String)) return "";
        String result = ((String)value).trim();
        if (result.length() > 4096 ||
            result.indexOf('\r') >= 0 || result.indexOf('\n') >= 0) {
            return "";
        }
        return result;
    }

    private static int integer(Map<String,Object> map, String key, int maximum) {
        Object value = map.get(key);
        int result;
        if (value instanceof Number) {
            result = ((Number)value).intValue();
        } else {
            try {
                result = Integer.parseInt(String.valueOf(value));
            } catch (NumberFormatException ex) {
                throw new IllegalStateException(
                    "Invalid AVAN security number " + key, ex);
            }
        }
        if (result < 1 || result > maximum) {
            throw new IllegalStateException(
                "Invalid AVAN security number " + key);
        }
        return result;
    }
}
