"""Persistent, safe public appearance settings for the AVAN login scene."""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path
import base64
import json
import math
import os
import re
import xml.etree.ElementTree as ET

from . import setup_console as setup

PUBLIC_ROOT=Path(os.getenv("AVAN_UI_STATE_DIR","/var/lib/avan-ui")).resolve()
PUBLIC_FILE=PUBLIC_ROOT/"appearance.json"
MAX_BACKGROUND_BYTES=5*1024*1024
MAX_ELEMENTS=12

DEFAULT_SVGS={
    "docs":'<svg viewBox="0 0 24 24"><path d="M6 3h8l4 4v14H6z"/><path d="M14 3v5h5M9 12h6m-6 4h6"/></svg>',
    "bi":'<svg viewBox="0 0 24 24"><path d="M4 19V10m5 9V5m5 14v-7m5 7V8"/><path d="M3 19h18"/></svg>',
    "meetings":'<svg viewBox="0 0 24 24"><circle cx="8" cy="9" r="3"/><circle cx="16" cy="9" r="3"/><path d="M3.5 19c.8-3.2 2.8-5 5.5-5s4.7 1.8 5.5 5M12.5 15c.8-.7 1.8-1 2.9-1 2.6 0 4.5 1.7 5.1 5"/></svg>',
    "bpms":'<svg viewBox="0 0 24 24"><circle cx="6" cy="6" r="2.4"/><circle cx="18" cy="6" r="2.4"/><circle cx="12" cy="18" r="2.4"/><path d="M8.1 7.3 10.7 15m5.2-7.7L13.3 15M8.4 6h7.2"/></svg>',
    "agent":'<svg viewBox="0 0 24 24"><rect x="4" y="7" width="16" height="12" rx="3"/><path d="M9 7V4m6 3V4M8 13h.01M16 13h.01M9 16h6"/></svg>',
    "voice":'<svg viewBox="0 0 24 24"><rect x="9" y="3" width="6" height="12" rx="3"/><path d="M5.5 11.5A6.5 6.5 0 0 0 18.5 11.5M12 18v3m-4 0h8"/></svg>',
    "alert":'<svg viewBox="0 0 24 24"><path d="M12 3 2.8 20h18.4L12 3Z"/><path d="M12 9v5M12 17.5v.5"/></svg>',
    "security":'<svg viewBox="0 0 24 24"><path d="M12 3 19 6v5c0 4.5-2.5 7.7-7 10-4.5-2.3-7-5.5-7-10V6z"/><path d="m9.2 12 1.8 1.8 3.8-4"/></svg>',
}

DEFAULT_ELEMENTS=[
    {"id":"docs","enabled":True,"title":"مدیریت اسناد",
     "subtitle":"استخراج، طبقه‌بندی و جستجوی هوشمند",
     "description":"تحلیل قرارداد، صورت‌جلسه، گزارش و فایل؛ استخراج اطلاعات و تبدیل محتوا به Context قابل استفاده برای Agent و جست‌وجوی سازمانی.",
     "tags":["Documents","Extraction","RAG"],"svg":DEFAULT_SVGS["docs"],"accent":"#63ECFF",
     "radius":1.22,"ellipse":0.70,"angle":4.35,"speed":-0.00014},
    {"id":"bi","enabled":True,"title":"تحلیل و گزارشات",
     "subtitle":"داشبوردها و هوش تجاری",
     "description":"اتصال گزارش‌های مدیریتی، KPIها و تحلیل روند به فضای کاری آوان؛ با امکان پرسش‌وپاسخ روی داده و یافتن گلوگاه‌ها.",
     "tags":["Power BI","KPI","Root Cause"],"svg":DEFAULT_SVGS["bi"],"accent":"#65EEF2",
     "radius":1.40,"ellipse":0.64,"angle":3.35,"speed":0.00013},
    {"id":"meetings","enabled":True,"title":"جلسات و مصوبات",
     "subtitle":"مدیریت جلسات، مصوبات و پیگیری",
     "description":"از برنامه‌ریزی و صورت‌جلسه تا اقدام، مسئول، موعد، درصد پیشرفت، ارزیابی و جلسه بعدی؛ متصل به AI Agent جلسات.",
     "tags":["Minutes","Actions","Follow-up"],"svg":DEFAULT_SVGS["meetings"],"accent":"#FF7358",
     "radius":1.25,"ellipse":0.76,"angle":2.85,"speed":-0.00016},
    {"id":"bpms","enabled":True,"title":"اتصالات BPMS",
     "subtitle":"ProcessMaker، Camunda و سایر موتورها",
     "description":"کاتالوگ یکپارچه اتصال ProcessMaker، Camunda، Appian، UiPath و سایر BPMSها با تست، ویرایش، OAuth و کنترل دسترسی.",
     "tags":["ProcessMaker","BPMS","OAuth"],"svg":DEFAULT_SVGS["bpms"],"accent":"#61EAF7",
     "radius":1.42,"ellipse":0.62,"angle":5.55,"speed":-0.00012},
    {"id":"agent","enabled":True,"title":"Agent هوشمند",
     "subtitle":"اتوماسیون فرایندها با AI",
     "description":"Agentهای تخصصی برای تحلیل، تصمیم‌یار و اجرای کنترل‌شده کارها؛ هماهنگ با انسان، سیستم و Workflowهای سازمان.",
     "tags":["Agents","Tools","Workflow"],"svg":DEFAULT_SVGS["agent"],"accent":"#FF8064",
     "radius":1.20,"ellipse":0.74,"angle":0.05,"speed":0.00017},
    {"id":"voice","enabled":True,"title":"دستیار صوتی",
     "subtitle":"تعامل صوتی و گفتگوی طبیعی",
     "description":"ورودی صوتی، تبدیل گفتار به متن، پاسخ صوتی، خلاصه‌سازی جلسه و ثبت سریع داده بدون نیاز به فرم‌های طولانی.",
     "tags":["STT","TTS","Assistant"],"svg":DEFAULT_SVGS["voice"],"accent":"#68EEEF",
     "radius":1.39,"ellipse":0.67,"angle":0.75,"speed":-0.00014},
    {"id":"alert","enabled":True,"title":"هشدار و نظارت",
     "subtitle":"پایش، یادآورها و اعلان‌های هوشمند",
     "description":"پایش تأخیرها، SLA، ریسک و اقدامات باز و ایجاد هشدار برای مدیر، مسئول و دبیر فرایند با قابلیت پیگیری.",
     "tags":["SLA","Risk","Monitoring"],"svg":DEFAULT_SVGS["alert"],"accent":"#FF7459",
     "radius":1.29,"ellipse":0.75,"angle":1.45,"speed":0.00018},
    {"id":"security","enabled":True,"title":"هویت و امنیت",
     "subtitle":"مدیریت کاربران و دسترسی‌ها",
     "description":"ورود سازمانی، MFA، مدیریت Tenant، نقش‌ها، Secret Management و Anti-Bot برای استفاده امن و تجاری آوان.",
     "tags":["Keycloak","MFA","RBAC"],"svg":DEFAULT_SVGS["security"],"accent":"#67F1D0",
     "radius":1.45,"ellipse":0.62,"angle":2.25,"speed":-0.00013},
]

DEFAULT={
    "version":5,
    "background_image":"",
    "background_fit":"cover",
    "background_position_x":50,
    "background_position_y":50,
    "background_brightness":1.12,
    "background_contrast":1.08,
    "background_saturation":1.08,
    "background_blur":0.0,
    "background_dim":0.03,
    "overlay_color":"#031522",
    "overlay_opacity":0.05,
    "background_parallax":6.0,
    "globe_image":"",
    "globe_visible":True,
    "globe_x":29.0,
    "globe_y":44.0,
    "globe_scale":1.22,
    "globe_opacity":1.0,
    "globe_brightness":1.32,
    "globe_contrast":1.10,
    "globe_saturation":1.22,
    "globe_hue":0.0,
    "globe_glow":1.30,
    "globe_wobble":1.0,
    "globe_rotation_speed":1.0,
    "globe_point_density":1.0,
    "globe_point_size":1.0,
    "globe_point_opacity":1.0,
    "node_size":70,
    "node_opacity":1.0,
    "node_border_width":1.0,
    "node_glow":1.0,
    "hover_scale":1.24,
    "hover_duration":180,
    "hover_mode":"card",
    "pause_on_hover":True,
    "show_orbits":True,
    "show_idle_cards":True,
    "orbit_speed":0.22,
    "orbit_mode":"orbit",
    "orbit_line_width":1.15,
    "orbit_opacity":0.78,
    "orbit_glow":1.0,
    "orbit_primary":"#50EAF7",
    "orbit_secondary":"#FF7053",
    "card_width":176,
    "card_opacity":0.94,
    "elements":DEFAULT_ELEMENTS,
}

_ALLOWED_SVG_TAGS={"svg","g","path","circle","rect","line","polyline","polygon","ellipse"}
_ALLOWED_SVG_ATTRS={
    "viewBox","d","cx","cy","r","x","y","width","height","rx","ry",
    "x1","y1","x2","y2","points","fill","stroke","stroke-width",
    "stroke-linecap","stroke-linejoin","transform","opacity",
}
_HEX=re.compile(r"^#[0-9A-Fa-f]{6}$")
_ID=re.compile(r"^[A-Za-z][A-Za-z0-9_-]{0,39}$")
_BG=re.compile(r"^data:image/(png|jpeg|webp);base64,([A-Za-z0-9+/=]+)$")

class AppearanceError(ValueError):
    pass

def _number(value,default,minimum,maximum):
    try:value=float(value)
    except (TypeError,ValueError):value=float(default)
    if not math.isfinite(value):value=float(default)
    return max(minimum,min(maximum,value))

def _integer(value,default,minimum,maximum):
    try:value=int(value)
    except (TypeError,ValueError):value=int(default)
    return max(minimum,min(maximum,value))

def _text(value,default,max_len,required=False):
    value=str(value if value is not None else default).strip()
    if required and not value:
        value=str(default).strip()
    return value[:max_len]

def _local_tag(tag):
    return tag.rsplit("}",1)[-1] if "}" in tag else tag

def sanitize_svg(svg:str)->str:
    svg=_text(svg,"",5000,True)
    try:root=ET.fromstring(svg)
    except ET.ParseError as exc:raise AppearanceError("SVG معتبر نیست.") from exc
    if _local_tag(root.tag)!="svg":
        raise AppearanceError("آیکن باید با تگ svg شروع شود.")
    for elem in root.iter():
        tag=_local_tag(elem.tag)
        if tag not in _ALLOWED_SVG_TAGS:
            raise AppearanceError("SVG شامل تگ غیرمجاز است.")
        elem.tag=tag
        clean={}
        for key,value in elem.attrib.items():
            key=_local_tag(key)
            if key in _ALLOWED_SVG_ATTRS:
                value=str(value)[:2000]
                if re.search(r"url\s*\(|javascript:|data:|https?:|//",value,re.I):
                    raise AppearanceError("ارجاع خارجی در SVG مجاز نیست.")
                clean[key]=value
        elem.attrib.clear();elem.attrib.update(clean)
        elem.text=None;elem.tail=None
    view=root.attrib.get("viewBox","")
    if not re.fullmatch(r"-?\d+(?:\.\d+)?\s+-?\d+(?:\.\d+)?\s+\d+(?:\.\d+)?\s+\d+(?:\.\d+)?",view):
        root.attrib["viewBox"]="0 0 24 24"
    root.attrib.pop("width",None);root.attrib.pop("height",None)
    return ET.tostring(root,encoding="unicode",short_empty_elements=True)

def validate_image(value)->str:
    value=_text(value,"",8_000_000)
    if not value:return ""
    match=_BG.fullmatch(value)
    if not match:raise AppearanceError("تصویر پس‌زمینه باید PNG، JPG یا WebP باشد.")
    try:raw=base64.b64decode(match.group(2),validate=True)
    except Exception as exc:raise AppearanceError("داده تصویر پس‌زمینه معتبر نیست.") from exc
    if not raw or len(raw)>MAX_BACKGROUND_BYTES:
        raise AppearanceError("حجم تصویر پس‌زمینه باید حداکثر ۵ مگابایت باشد.")
    kind=match.group(1)
    good=(kind=="png" and raw.startswith(b"\x89PNG\r\n\x1a\n")) or \
         (kind=="jpeg" and raw.startswith(b"\xff\xd8\xff")) or \
         (kind=="webp" and raw[:4]==b"RIFF" and raw[8:12]==b"WEBP")
    if not good:raise AppearanceError("فرمت واقعی تصویر با نوع اعلام‌شده یکسان نیست.")
    return value

def _element(raw:dict,index:int)->dict:
    base=DEFAULT_ELEMENTS[index % len(DEFAULT_ELEMENTS)]
    identifier=_text(raw.get("id"),base["id"],40,True)
    if not _ID.fullmatch(identifier):
        raise AppearanceError("شناسه المان ظاهری معتبر نیست.")
    tags=raw.get("tags",base["tags"])
    if isinstance(tags,str):tags=[x.strip() for x in tags.split(",")]
    if not isinstance(tags,list):tags=base["tags"]
    tags=[_text(x,"",30) for x in tags if _text(x,"",30)][:8]
    accent=_text(raw.get("accent"),base["accent"],7)
    if not _HEX.fullmatch(accent):accent=base["accent"]
    return {
        "id":identifier,
        "enabled":bool(raw.get("enabled",True)),
        "title":_text(raw.get("title"),base["title"],80,True),
        "subtitle":_text(raw.get("subtitle"),base["subtitle"],140),
        "description":_text(raw.get("description"),base["description"],600),
        "tags":tags,
        "svg":sanitize_svg(raw.get("svg") or base["svg"]),
        "accent":accent.upper(),
        "radius":_number(raw.get("radius"),base["radius"],0.75,1.95),
        "ellipse":_number(raw.get("ellipse"),base["ellipse"],0.35,1.0),
        "angle":_number(raw.get("angle"),base["angle"],-20.0,20.0),
        "speed":_number(raw.get("speed"),base["speed"],-0.001,0.001),
        "size":_integer(raw.get("size"),0,0,110),
        "hover_scale":_number(raw.get("hover_scale"),0.0,0.0,1.85),
        "glow":_number(raw.get("glow"),1.0,0.0,2.5),
        "opacity":_number(raw.get("opacity"),1.0,0.25,1.0),
        "card_side":_text(raw.get("card_side"),"auto",10),
        "label_mode":_text(raw.get("label_mode"),"inherit",12),
    }

def normalize(raw:dict|None)->dict:
    raw=dict(raw) if isinstance(raw,dict) else {}
    # Upgrade the former default drifting preset once; retain custom/static modes.
    if raw.get("version",5)==4 and raw.get("orbit_mode","drift")=="drift":
        raw["orbit_mode"]="orbit"
        if raw.get("orbit_speed",1)==1:raw["orbit_speed"]=0.22
    items=raw.get("elements",DEFAULT_ELEMENTS)
    if not isinstance(items,list):items=DEFAULT_ELEMENTS
    items=items[:MAX_ELEMENTS]
    normalized=[]
    seen=set()
    for i,item in enumerate(items):
        if not isinstance(item,dict):continue
        value=_element(item,i)
        if value["card_side"] not in {"auto","left","right","top","bottom"}:value["card_side"]="auto"
        if value["label_mode"] not in {"inherit","always","hover","hidden"}:value["label_mode"]="inherit"
        if value["id"] in seen:raise AppearanceError("شناسه المان‌های ظاهری باید یکتا باشد.")
        seen.add(value["id"]);normalized.append(value)
    mode=_text(raw.get("hover_mode"),DEFAULT["hover_mode"],20)
    if mode not in {"card","tooltip","label","glow","none"}:mode=DEFAULT["hover_mode"]
    fit=_text(raw.get("background_fit"),DEFAULT["background_fit"],20)
    if fit not in {"cover","contain","stretch","auto"}:fit=DEFAULT["background_fit"]
    overlay=_text(raw.get("overlay_color"),DEFAULT["overlay_color"],7)
    if not _HEX.fullmatch(overlay):overlay=DEFAULT["overlay_color"]
    orbit_primary=_text(raw.get("orbit_primary"),DEFAULT["orbit_primary"],7)
    if not _HEX.fullmatch(orbit_primary):orbit_primary=DEFAULT["orbit_primary"]
    orbit_secondary=_text(raw.get("orbit_secondary"),DEFAULT["orbit_secondary"],7)
    if not _HEX.fullmatch(orbit_secondary):orbit_secondary=DEFAULT["orbit_secondary"]
    return {
        "version":5,
        "background_image":validate_image(raw.get("background_image","")),
        "background_fit":fit,
        "background_position_x":_number(raw.get("background_position_x"),DEFAULT["background_position_x"],0,100),
        "background_position_y":_number(raw.get("background_position_y"),DEFAULT["background_position_y"],0,100),
        "background_brightness":_number(raw.get("background_brightness"),DEFAULT["background_brightness"],0.45,1.7),
        "background_contrast":_number(raw.get("background_contrast"),DEFAULT["background_contrast"],0.5,1.8),
        "background_saturation":_number(raw.get("background_saturation"),DEFAULT["background_saturation"],0.0,2.0),
        "background_blur":_number(raw.get("background_blur"),DEFAULT["background_blur"],0.0,20.0),
        "background_dim":_number(raw.get("background_dim"),DEFAULT["background_dim"],0.0,0.8),
        "overlay_color":overlay.upper(),
        "overlay_opacity":_number(raw.get("overlay_opacity"),DEFAULT["overlay_opacity"],0.0,0.8),
        "background_parallax":_number(raw.get("background_parallax"),DEFAULT["background_parallax"],0.0,30.0),
        "globe_image":validate_image(raw.get("globe_image","")),
        "globe_visible":bool(raw.get("globe_visible",DEFAULT["globe_visible"])),
        "globe_x":_number(raw.get("globe_x"),DEFAULT["globe_x"],8.0,60.0),
        "globe_y":_number(raw.get("globe_y"),DEFAULT["globe_y"],18.0,82.0),
        "globe_scale":_number(raw.get("globe_scale"),DEFAULT["globe_scale"],0.55,1.85),
        "globe_opacity":_number(raw.get("globe_opacity"),DEFAULT["globe_opacity"],0.0,1.0),
        "globe_brightness":_number(raw.get("globe_brightness"),DEFAULT["globe_brightness"],0.5,2.0),
        "globe_contrast":_number(raw.get("globe_contrast"),DEFAULT["globe_contrast"],0.5,1.8),
        "globe_saturation":_number(raw.get("globe_saturation"),DEFAULT["globe_saturation"],0.0,2.0),
        "globe_hue":_number(raw.get("globe_hue"),DEFAULT["globe_hue"],-180.0,180.0),
        "globe_glow":_number(raw.get("globe_glow"),DEFAULT["globe_glow"],0.0,2.5),
        "globe_wobble":_number(raw.get("globe_wobble"),DEFAULT["globe_wobble"],0.0,2.0),
        "globe_rotation_speed":_number(raw.get("globe_rotation_speed"),DEFAULT["globe_rotation_speed"],0.0,3.0),
        "globe_point_density":_number(raw.get("globe_point_density"),DEFAULT["globe_point_density"],0.5,2.5),
        "globe_point_size":_number(raw.get("globe_point_size"),DEFAULT["globe_point_size"],0.5,2.5),
        "globe_point_opacity":_number(raw.get("globe_point_opacity"),DEFAULT["globe_point_opacity"],0.1,1.0),
        "node_size":_integer(raw.get("node_size"),DEFAULT["node_size"],40,110),
        "node_opacity":_number(raw.get("node_opacity"),DEFAULT["node_opacity"],0.25,1.0),
        "node_border_width":_number(raw.get("node_border_width"),DEFAULT["node_border_width"],0.0,4.0),
        "node_glow":_number(raw.get("node_glow"),DEFAULT["node_glow"],0.0,2.5),
        "hover_scale":_number(raw.get("hover_scale"),DEFAULT["hover_scale"],1.0,1.8),
        "hover_duration":_integer(raw.get("hover_duration"),DEFAULT["hover_duration"],0,1200),
        "hover_mode":mode,
        "pause_on_hover":bool(raw.get("pause_on_hover",DEFAULT["pause_on_hover"])),
        "show_orbits":bool(raw.get("show_orbits",DEFAULT["show_orbits"])),
        "show_idle_cards":bool(raw.get("show_idle_cards",DEFAULT["show_idle_cards"])),
        "orbit_speed":_number(raw.get("orbit_speed"),DEFAULT["orbit_speed"],0.0,3.0),
        "orbit_mode":raw.get("orbit_mode") if raw.get("orbit_mode") in {"orbit","drift","static"} else "orbit",
        "orbit_line_width":_number(raw.get("orbit_line_width"),DEFAULT["orbit_line_width"],0.2,4.0),
        "orbit_opacity":_number(raw.get("orbit_opacity"),DEFAULT["orbit_opacity"],0.0,1.0),
        "orbit_glow":_number(raw.get("orbit_glow"),DEFAULT["orbit_glow"],0.0,2.5),
        "orbit_primary":orbit_primary.upper(),
        "orbit_secondary":orbit_secondary.upper(),
        "card_width":_integer(raw.get("card_width"),DEFAULT["card_width"],120,320),
        "card_opacity":_number(raw.get("card_opacity"),DEFAULT["card_opacity"],0.35,1.0),
        "elements":normalized,
    }

def current()->dict:
    stored=setup.get_setting("appearance")
    try:return normalize(stored)
    except AppearanceError:return deepcopy(DEFAULT)

def sync_public(config:dict|None=None)->bool:
    config=normalize(config if config is not None else setup.get_setting("appearance"))
    try:
        PUBLIC_ROOT.mkdir(parents=True,exist_ok=True)
        temp=PUBLIC_ROOT/"appearance.json.tmp"
        temp.write_text(json.dumps(config,ensure_ascii=False,separators=(",",":")),encoding="utf-8")
        os.chmod(temp,0o644)
        temp.replace(PUBLIC_FILE)
        os.chmod(PUBLIC_FILE,0o644)
        return True
    except OSError:
        return False

def save(raw:dict)->dict:
    config=normalize(raw)
    setup.put_setting("appearance",config)
    synced=sync_public(config)
    return {"saved":True,"identity_theme_synced":synced,"appearance":config}

def reset()->dict:
    config=deepcopy(DEFAULT)
    setup.put_setting("appearance",config)
    synced=sync_public(config)
    return {"reset":True,"identity_theme_synced":synced,"appearance":config}

