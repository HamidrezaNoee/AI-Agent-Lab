from pathlib import Path

THEME_DIR = Path(__file__).resolve().parents[2] / "infra" / "keycloak" / "themes" / "avan" / "login"


def test_avan_login_templates_do_not_use_legacy_html_builtin():
    """Keycloak 26 enables HTML auto-escaping; FreeMarker rejects ?html in that mode."""
    templates = [THEME_DIR / "login.ftl", THEME_DIR / "login-otp.ftl"]
    for template in templates:
        content = template.read_text(encoding="utf-8")
        assert "?html" not in content, (
            f"{template.name} uses FreeMarker's legacy ?html escaping, which crashes "
            "Keycloak 26 login rendering when HTML auto-escaping is enabled."
        )
