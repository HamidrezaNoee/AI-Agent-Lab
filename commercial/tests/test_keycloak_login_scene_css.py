from pathlib import Path

CSS = Path(__file__).resolve().parents[2] / "infra" / "keycloak" / "themes" / "avan" / "login" / "resources" / "css" / "avan.css"


def test_keycloak_login_button_rules_do_not_resize_orbit_nodes():
    css = CSS.read_text(encoding="utf-8")
    assert ".avan-signin button{" not in css
    assert ".avan-signin .signin-panel button{" in css
