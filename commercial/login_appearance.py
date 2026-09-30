"""Persistent, safe public appearance settings for the AVAN login scene."""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path
import base64
import json
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
    "version":3,
    "background_image":"",
    "background_position":"center",
    "background_brightness":1.10,
    "background_dim":0.05,
    "globe_scale":1.18,
    "globe_brightness":1.24,
    "globe_saturation":1.18,
    "globe_glow":1.15,
    "node_size":68,
    "hover_scale":1.22,
    "hover_mode":"card",
    "pause_on_hover":True,
    "show_orbits":True,
    "show_idle_cards":True,
    "orbit_speed":1.0,
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
                clean[key]=str(value)[:2000]
        elem.attrib.clear();elem.attrib.update(clean)
        elem.text=None;elem.tail=None
    view=root.attrib.get("viewBox","")
    if not re.fullmatch(r"-?\d+(?:\.\d+)?\s+-?\d+(?:\.\d+)?\s+\d+(?:\.\d+)?\s+\d+(?:\.\d+)?",view):
        root.attrib["viewBox"]="0 0 24 24"
    root.attrib.pop("width",None);root.attrib.pop("height",None)
    return ET.tostring(root,encoding="unicode",short_empty_elements=True)

def validate_background(value)->str:
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
        "radius":_number(raw.get("radius"),base["radius"],0.85,1.8),
        "ellipse":_number(raw.get("ellipse"),base["ellipse"],0.4,1.0),
        "angle":_number(raw.get("angle"),base["angle"],-20.0,20.0),
        "speed":_number(raw.get("speed"),base["speed"],-0.001,0.001),
    }

def normalize(raw:dict|None)->dict:
    raw=raw if isinstance(raw,dict) else {}
    items=raw.get("elements",DEFAULT_ELEMENTS)
    if not isinstance(items,list):items=DEFAULT_ELEMENTS
    items=items[:MAX_ELEMENTS]
    normalized=[]
    seen=set()
    for i,item in enumerate(items):
        if not isinstance(item,dict):continue
        value=_element(item,i)
        if value["id"] in seen:raise AppearanceError("شناسه المان‌های ظاهری باید یکتا باشد.")
        seen.add(value["id"]);normalized.append(value)
    if not normalized:normalized=deepcopy(DEFAULT_ELEMENTS)
    mode=_text(raw.get("hover_mode"),DEFAULT["hover_mode"],20)
    if mode not in {"card","tooltip","label","glow","none"}:mode=DEFAULT["hover_mode"]
    position=_text(raw.get("background_position"),DEFAULT["background_position"],20)
    if position not in {"center","left","right","top","bottom"}:position="center"
    return {
        "version":3,
        "background_image":validate_background(raw.get("background_image","")),
        "background_position":position,
        "background_brightness":_number(raw.get("background_brightness"),DEFAULT["background_brightness"],0.55,1.5),
        "background_dim":_number(raw.get("background_dim"),DEFAULT["background_dim"],0.0,0.75),
        "globe_scale":_number(raw.get("globe_scale"),DEFAULT["globe_scale"],0.70,1.65),
        "globe_brightness":_number(raw.get("globe_brightness"),DEFAULT["globe_brightness"],0.65,1.8),
        "globe_saturation":_number(raw.get("globe_saturation"),DEFAULT["globe_saturation"],0.5,1.8),
        "globe_glow":_number(raw.get("globe_glow"),DEFAULT["globe_glow"],0.0,2.0),
        "node_size":_integer(raw.get("node_size"),DEFAULT["node_size"],44,96),
        "hover_scale":_number(raw.get("hover_scale"),DEFAULT["hover_scale"],1.0,1.65),
        "hover_mode":mode,
        "pause_on_hover":bool(raw.get("pause_on_hover",DEFAULT["pause_on_hover"])),
        "show_orbits":bool(raw.get("show_orbits",DEFAULT["show_orbits"])),
        "show_idle_cards":bool(raw.get("show_idle_cards",DEFAULT["show_idle_cards"])),
        "orbit_speed":_number(raw.get("orbit_speed"),DEFAULT["orbit_speed"],0.0,3.0),
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
