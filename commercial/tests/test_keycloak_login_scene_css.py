from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
THEME = ROOT / "infra" / "keycloak" / "themes" / "avan" / "login" / "resources"
ADMIN = ROOT / "commercial" / "web" / "admin"
AVAN_CSS = THEME / "css" / "avan.css"
COMPOSE = ROOT / "compose.yaml"


def test_keycloak_login_button_rules_do_not_resize_orbit_nodes():
    css = AVAN_CSS.read_text(encoding="utf-8")
    assert ".avan-signin button{" not in css
    assert ".avan-signin .signin-panel button{" in css


def test_keycloak_scene_assets_match_canonical_admin_scene():
    assert (THEME / "css" / "login-scene.css").read_text(encoding="utf-8") == (
        ADMIN / "login-scene.css"
    ).read_text(encoding="utf-8")
    assert (THEME / "js" / "login-scene.js").read_text(encoding="utf-8") == (
        ADMIN / "login-scene.js"
    ).read_text(encoding="utf-8")


def test_existing_realm_repairs_and_binds_protected_browser_flow():
    compose = COMPOSE.read_text(encoding="utf-8")
    sql = (ROOT / "infra" / "keycloak" / "ensure-avan-browser-flow.sql").read_text(encoding="utf-8")
    assert "ensure-avan-browser-flow.sql" in compose
    assert "condition: service_healthy" in compose
    assert "alias='avan-browser'" in sql
    assert "authenticator='avan-captcha-password'" in sql
    assert "conditional-user-configured" in sql
    assert "auth-otp-form" in sql
    assert "browser_flow=v_flow" in sql


def test_keycloak_uses_avan_security_bridge_not_a_second_captcha_stack():
    provider = (
        ROOT / "infra" / "keycloak" / "captcha" / "src" / "main" / "java" /
        "com" / "avan" / "identity" / "AvanCaptchaForm.java"
    ).read_text(encoding="utf-8")
    app = (ROOT / "commercial" / "production_app.py").read_text(encoding="utf-8")
    compose = COMPOSE.read_text(encoding="utf-8")
    assert "AVAN_SECURITY_BRIDGE_URL" in provider
    assert "/internal/security/challenge" in app
    assert "/internal/security/verify" in app
    assert "from .turnstile import public_config" in app
    assert "from .turnstile import verify" in app
    assert "AVAN_SECURITY_BRIDGE_URL: http://avan:8188/internal/security" in compose
    assert "AVAN_ALLOWED_HOSTS: 127.0.0.1,localhost,avan" in compose


def test_keycloak_initial_login_challenge_injects_avan_captcha():
    provider = (
        ROOT / "infra" / "keycloak" / "captcha" / "src" / "main" / "java" /
        "com" / "avan" / "identity" / "AvanCaptchaForm.java"
    ).read_text(encoding="utf-8")
    assert "protected Response challenge(AuthenticationFlowContext context" in provider
    assert "prepareSecurity(form);" in provider
    assert "return form.createLoginUsernamePassword();" in provider
