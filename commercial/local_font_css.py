"""Only advertise locally installed, user-owned B Yekan Plus fonts.

Font binaries are never bundled in GitHub or the downloadable preview. A
missing font uses the browser fallback without causing repeated 404 requests.
"""
from pathlib import Path
ROOT = Path(__file__).resolve().parent

def installed_font_css(endpoint_prefix: str) -> str:
    if endpoint_prefix not in ("/preview-font-", "/portal/font/"):
        raise ValueError("Unrecognized local font endpoint")
    font_dir = ROOT / "web" / "fonts"
    rules = []
    for name, weight in (("regular", "400"), ("bold", "700 900")):
        if not (font_dir / ("byekanplus-" + name + ".ttf")).is_file():
            continue
        url = endpoint_prefix + name
        rules.append(
            '@font-face{font-family:BYekanPlus;src:url("' + url +
            '") format("truetype");font-style:normal;font-weight:' +
            weight + ';font-display:swap}'
        )
    return "\n".join(rules) + ("\n" if rules else "")
