import base64
import pytest

from commercial import login_appearance as appearance


def test_default_appearance_is_vivid_and_configurable():
    cfg=appearance.normalize(None)
    assert cfg["globe_brightness"] >= 1.2
    assert cfg["globe_scale"] > 1.0
    assert cfg["hover_mode"] == "card"
    assert cfg["show_idle_cards"] is True
    assert cfg["version"] == 4
    assert cfg["background_contrast"] >= 1.0
    assert cfg["globe_opacity"] == 1.0
    assert cfg["orbit_primary"].startswith("#")
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
        "background_dim":-3,"globe_brightness":12,
        "background_blur":100,"globe_x":-20,"card_width":900
    })
    assert cfg["node_size"] == 110
    assert cfg["hover_scale"] == 1.8
    assert cfg["orbit_speed"] == 3.0
    assert cfg["background_dim"] == 0.0
    assert cfg["globe_brightness"] == 2.0
    assert cfg["background_blur"] == 20.0
    assert cfg["globe_x"] == 8.0
    assert cfg["card_width"] == 320


def test_per_node_v4_overrides_are_bounded():
    cfg=appearance.normalize({"elements":[{
        "id":"node","title":"Node","svg":'<svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="5"/></svg>',
        "size":999,"hover_scale":9,"glow":9,"opacity":0,"card_side":"sideways","label_mode":"maybe"
    }]})
    item=cfg["elements"][0]
    assert item["size"] == 110
    assert item["hover_scale"] == 1.85
    assert item["glow"] == 2.5
    assert item["opacity"] == 0.25
    assert item["card_side"] == "auto"
    assert item["label_mode"] == "inherit"
