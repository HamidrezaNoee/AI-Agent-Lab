from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_avan_realm_declares_avan_login_theme():
    text=(ROOT/"infra/keycloak/avan-realm.json").read_text(encoding="utf-8")
    assert '"loginTheme": "avan"' in text


def test_keycloak_image_forces_avan_theme_selector():
    dockerfile=(ROOT/"infra/keycloak/Dockerfile").read_text(encoding="utf-8")
    assert "--spi-theme-selector--provider-default=avan" in dockerfile
    assert "--health-enabled=true" in dockerfile
    assert "--metrics-enabled=true" in dockerfile


def test_theme_selector_spi_is_registered_and_scoped_to_avan_realm():
    service=(ROOT/"infra/keycloak/captcha/src/main/resources/META-INF/services/org.keycloak.theme.ThemeSelectorProviderFactory").read_text(encoding="utf-8")
    provider=(ROOT/"infra/keycloak/captcha/src/main/java/com/avan/identity/AvanThemeSelectorProvider.java").read_text(encoding="utf-8")
    assert "com.avan.identity.AvanThemeSelectorProviderFactory" in service
    assert '"avan".equals(realm.getName())' in provider
    assert 'type == Theme.Type.LOGIN' in provider
    assert 'return "avan";' in provider
    assert "delegate.getThemeName(type)" in provider


def test_keycloak_runs_prebuilt_optimized_image():
    compose=(ROOT/"compose.yaml").read_text(encoding="utf-8")
    assert "kc.sh start --optimized" in compose


def test_avan_waits_for_keycloak_readiness_not_container_start():
    compose=(ROOT/"compose.yaml").read_text(encoding="utf-8")
    assert "--server-async-bootstrap=false" in compose
    assert "/health/ready" in compose
    assert "keycloak:\n        condition: service_healthy" in compose
