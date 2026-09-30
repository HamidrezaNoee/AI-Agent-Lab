import base64
import pytest

from commercial import login_appearance as appearance


def test_default_appearance_is_vivid_and_configurable():
    cfg=appearance.normalize(None)
    assert cfg["globe_brightness"] >= 1.2
    assert cfg["globe_scale"] > 1.0
    assert cfg["hover_mode"] == "card"
    assert cfg["show_idle_cards"] is True
    assert len(cfg["elements"]) == 8


def test_svg_event_handlers_are_removed():
    cfg=appearance.normalize({"elements":[{
        "id":"safe","title":"Safe",
        "svg":'<svg viewBox="0 0 24 24" onload="alert(1)"><path d="M2 2h10" onclick="evil()" /></svg>'
    }]})
    svg=cfg["elements"][0]["svg"]
    assert "onload" not in svg
    assert "onclick" not in svg
    assert "<path" in svg


def test_svg_script_is_rejected():
    with pytest.raises(appearance.AppearanceError):
        appearance.normalize({"elements":[{
            "id":"bad","title":"Bad",
            "svg":'<svg viewBox="0 0 24 24"><script>alert(1)</script></svg>'
        }]})


def test_background_requires_real_raster_magic():
    fake=base64.b64encode(b"not an image").decode()
    with pytest.raises(appearance.AppearanceError):
        appearance.normalize({"background_image":"data:image/png;base64,"+fake})


def test_visual_ranges_are_clamped():
    cfg=appearance.normalize({
        "node_size":500,"hover_scale":9,"orbit_speed":99,
        "background_dim":-3,"globe_brightness":12
    })
    assert cfg["node_size"] == 96
    assert cfg["hover_scale"] == 1.65
    assert cfg["orbit_speed"] == 3.0
    assert cfg["background_dim"] == 0.0
    assert cfg["globe_brightness"] == 1.8
