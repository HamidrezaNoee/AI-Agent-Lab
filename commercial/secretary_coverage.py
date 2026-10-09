"""Coverage rules for high-density Smart Secretary turns.

This module does not invent facts. It identifies facts the user explicitly supplied
and checks that the structured extraction covered them before a turn is accepted.
"""
from __future__ import annotations
import re
from . import secretary_resolution as resolution

_USERNAME=re.compile(r'(?<![A-Za-z0-9_.-])([A-Za-z][A-Za-z0-9_-]*(?:\.[A-Za-z0-9_-]+)*)(?![A-Za-z0-9_.-])')
_NUMBERED=re.compile(r'(?m)^\s*([0-9۰-۹٠-٩]+)\s*[-–—.)]\s*(.+?)(?=^\s*[0-9۰-۹٠-٩]+\s*[-–—.)]|\Z)',re.S)
_DIGITS=str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩","01234567890123456789")


def _norm(text):
    return resolution.normalize_text(text)


def _section(notes,start_tokens,end_tokens=()):
    normalized=str(notes or "").replace("\r\n","\n")
    lower=_norm(normalized)
    starts=[]
    for token in start_tokens:
        pos=lower.find(_norm(token))
        if pos>=0:starts.append((pos,token))
    if not starts:return ""
    # Find the same marker in the original through a tolerant line scan.
    lines=normalized.split("\n")
    start=None
    for i,line in enumerate(lines):
        if any(_norm(token) in _norm(line) for token in start_tokens):
            start=i+1;break
    if start is None:return ""
    end=len(lines)
    for i in range(start,len(lines)):
        if any(_norm(token) in _norm(lines[i]) for token in end_tokens):
            end=i;break
    return "\n".join(lines[start:end]).strip()


def _active_username_map(directory):
    result={}
    for uid,person in (directory or {}).items():
        if not person.get("active"):continue
        for key in ("username","avan_username"):
            raw=str(person.get(key) or "").strip()
            if raw:result[raw.casefold()]=str(uid)
    return result


def _uid_for_username(username,directory):
    return _active_username_map(directory).get(str(username or "").strip().casefold())


def _usernames(text,directory):
    known=_active_username_map(directory)
    found=[]
    for match in _USERNAME.finditer(str(text or "")):
        raw=match.group(1)
        uid=known.get(raw.casefold())
        if uid and uid not in found:found.append(uid)
    return found


def is_compound_invitation(notes,task):
    """True when one invitation message clearly carries multiple independent facts."""
    if (task or {}).get("stage")!="invitation":return False
    raw=_norm(notes)
    score=0
    signals=(
        ("title",("با عنوان","عنوان جلسه")),
        ("objective",("هدف جلسه",)),
        ("location",("برگزار کن","مکان جلسه","اتاق جلسات")),
        ("date",("برای تاریخ","تاریخ برگزاری")),
        ("chair",("رئیس جلسه","رییس جلسه")),
        ("secretary",("دبیر جلسه",)),
        ("participants",("شرکت کنندگان","شرکت‌کنندگان","مدعوین")),
        ("agenda",("دستور جلسه","محورهای جلسه")),
    )
    for _,tokens in signals:
        if any(_norm(token) in raw for token in tokens):score+=1
    # Headed lists and long multiline requests are unambiguously high-density.
    return score>=3 or (score>=2 and str(notes).count("\n")>=3) or (
        "دستور جلسه" in raw and ("شرکت کنندگان" in raw or "شرکت‌کنندگان" in raw)
    )


def explicit_field_requirements(notes,task):
    if (task or {}).get("stage")!="invitation":return []
    raw=_norm(notes)
    result=[]
    def add(field,label,condition):
        if condition and field not in {x["field"] for x in result}:
            result.append({"field":field,"label":label})
    add("MTG_MeetingTitle","عنوان جلسه",any(x in raw for x in ("با عنوان","عنوان جلسه")))
    add("MTG_Objective","هدف جلسه","هدف جلسه" in raw)
    add("MTG_Location","مکان جلسه",("برگزار" in raw and " در " in " "+raw+" ") or "مکان جلسه" in raw or "اتاق جلسات" in raw)
    add("MTG_MeetingStartDateTime","تاریخ جلسه",any(x in raw for x in ("برای تاریخ","تاریخ برگزاری")))
    add("MTG_MeetingStartTime","ساعت شروع جلسه",bool(re.search(r'(?:برای تاریخ|تاریخ برگزاری).{0,100}\bساعت\b',raw,re.S)))
    add("MTG_ChairUserUID","رئیس جلسه",any(x in raw for x in ("رئیس جلسه","رییس جلسه")))
    add("MTG_SecretaryUserUID","دبیر جلسه","دبیر جلسه" in raw)
    add("MTG_Participants","شرکت‌کنندگان",any(x in raw for x in ("شرکت کنندگان","شرکت‌کنندگان","مدعوین")))
    add("MTG_Agenda","دستور جلسه",any(x in raw for x in ("دستور جلسه","محورهای جلسه")))
    return result


def participant_expectations(notes,directory):
    block=_section(notes,("شرکت‌کنندگان","شرکت کنندگان","مدعوین"),("دستور جلسه","محورهای جلسه"))
    if not block:return {"uids":[],"positions":{},"all_member":False,"all_required":False}
    positions={};uids=[]
    known=_active_username_map(directory)
    for line in block.splitlines():
        text=line.strip()
        if not text:continue
        match=_USERNAME.search(text)
        if not match:continue
        uid=known.get(match.group(1).casefold())
        if not uid:continue
        if uid not in uids:uids.append(uid)
        remainder=text[match.end():].strip(" :-–—")
        remainder=re.sub(r'^(?:به\s+سمت|سمت)\s*','',remainder).strip()
        if remainder:positions[uid]=remainder
    raw=_norm(notes)
    return {
        "uids":uids,
        "positions":positions,
        "all_member":bool(re.search(r'همه.{0,30}(?:به عنوان )?عضو',raw)),
        "all_required":bool(re.search(r'حضور همه.{0,20}(?:واجب|الزامی)',raw)),
    }


def agenda_expectations(notes,directory):
    block=_section(notes,("دستور جلسه","محورهای جلسه"),("مدت برنامه‌ریزی","مدت برنامه ريزی","پایان برنامه‌ریزی"))
    if not block:return []
    known=_active_username_map(directory);result=[]
    for raw_no,body in _NUMBERED.findall(block):
        no=str(int(str(raw_no).translate(_DIGITS)))
        uids=_usernames(body,directory)
        minutes=None
        match=re.search(r'(?:در\s+مدت|مدت)\s*([0-9۰-۹٠-٩]+)\s*دقیقه',body)
        if match:minutes=str(int(match.group(1).translate(_DIGITS)))
        normalized=_norm(body)
        has_existing_action="اقدام قبلی" in normalized or "اقدام قبلي" in normalized
        existing_owner=(uids[0] if len(uids)==1 and has_existing_action and any(x in normalized for x in ("به خودش","مربوط به خودش")) else None)
        existing_due=None
        if has_existing_action and any(x in normalized for x in ("موعد","مهلت")):
            try:
                from .secretary_time import jalali_date
                existing_due=jalali_date(body)
            except ValueError:
                existing_due=None
        result.append({
            "no":no,"presenter_uid":uids[0] if len(uids)==1 else None,"minutes":minutes,
            "has_existing_action":has_existing_action,
            "existing_owner_uid":existing_owner,
            "existing_due":existing_due,
        })
    return result


def _rows(value):
    if not isinstance(value,dict):return []
    return [(str(k),v) for k,v in value.items() if isinstance(v,dict)]


def coverage_issues(notes,task,values,assignments,directory):
    """Return precise omissions. Empty means all explicitly detectable facts were covered."""
    issues=[];assigned={str(a.field) for a in assignments}
    allowed=set((task.get("pack",{}).get("stages",{}).get(task.get("stage"),{}).get("fields",{}) or {}).keys())
    for req in explicit_field_requirements(notes,task):
        field=req["field"]
        if field not in allowed:continue
        if field not in assigned:
            issues.append(req["label"]+" از پیام استخراج نشد.")

    expected=participant_expectations(notes,directory)
    if expected["uids"] and "MTG_Participants" in allowed:
        rows=[row for _,row in _rows(values.get("MTG_Participants"))]
        by_uid={str(row.get("MTG_ParticipantUserUID") or ""):row for row in rows}
        missing=[uid for uid in expected["uids"] if uid not in by_uid]
        if missing:issues.append(str(len(missing))+" شرکت‌کننده صریح پیام در پیش‌نویس جا افتاده است.")
        for uid,position in expected["positions"].items():
            row=by_uid.get(uid)
            if row is not None and position and not str(row.get("MTG_ParticipantPosition") or "").strip():
                issues.append("سمت یکی از شرکت‌کنندگان صریح پیام استخراج نشد.")
                break
        if expected["all_member"] and any(by_uid.get(uid,{}).get("MTG_ParticipantRole")!="Member" for uid in expected["uids"]):
            issues.append("عبارت «همه عضو هستند» روی همه شرکت‌کنندگان اعمال نشد.")
        if expected["all_required"] and any(str(by_uid.get(uid,{}).get("MTG_ParticipantRequired") or "")!="1" for uid in expected["uids"]):
            issues.append("الزام حضور همه شرکت‌کنندگان روی همه ردیف‌ها اعمال نشد.")

    expected_agenda=agenda_expectations(notes,directory)
    if expected_agenda and "MTG_Agenda" in allowed:
        rows=[row for _,row in _rows(values.get("MTG_Agenda"))]
        if len(rows)<len(expected_agenda):
            issues.append("همه ردیف‌های شماره‌دار دستور جلسه استخراج نشدند.")
        for exp in expected_agenda:
            row=next((row for row in rows if str(row.get("MTG_AgendaNo") or "").lstrip("0")==exp["no"]),None)
            # Legacy model output may omit AgendaNo but preserve row key/order.
            if row is None:
                try:row=rows[int(exp["no"])-1]
                except (IndexError,ValueError):row=None
            if row is None:continue
            if not str(row.get("MTG_AgendaTitle") or "").strip():
                issues.append("عنوان دستور جلسه ردیف "+exp["no"]+" استخراج نشد.")
            if exp["presenter_uid"] and str(row.get("MTG_AgendaPresenterUID") or "")!=exp["presenter_uid"]:
                issues.append("ارائه‌دهنده دستور جلسه ردیف "+exp["no"]+" استخراج نشد.")
            if exp["minutes"] and str(row.get("MTG_AgendaPlannedMinutes") or "")!=exp["minutes"]:
                issues.append("مدت دستور جلسه ردیف "+exp["no"]+" استخراج نشد.")
            if exp.get("has_existing_action") and not str(row.get("MTG_ExistingActionText") or "").strip():
                issues.append("اقدام قبلی مرتبط دستور جلسه ردیف "+exp["no"]+" استخراج نشد.")
            if exp.get("existing_owner_uid") and str(row.get("MTG_ExistingOwnerUID") or "")!=exp["existing_owner_uid"]:
                issues.append("مسئول اقدام قبلی دستور جلسه ردیف "+exp["no"]+" استخراج نشد.")
            if exp.get("existing_due") and str(row.get("MTG_persiandate_ExistingDueDate") or "")!=exp["existing_due"]:
                issues.append("موعد اقدام قبلی دستور جلسه ردیف "+exp["no"]+" استخراج نشد.")
    return list(dict.fromkeys(issues))


def coverage_prompt(notes,task,directory):
    fields=[x["label"] for x in explicit_field_requirements(notes,task)]
    participants=participant_expectations(notes,directory)
    agenda=agenda_expectations(notes,directory)
    return {
        "explicit_fields":fields,
        "participant_count":len(participants["uids"]),
        "all_participants_member":participants["all_member"],
        "all_participants_required":participants["all_required"],
        "agenda_count":len(agenda),
        "agenda_rows":[{
            "row":x["no"],"has_presenter":bool(x["presenter_uid"]),"minutes":x["minutes"],
            "has_existing_action":x.get("has_existing_action",False),
            "has_existing_owner":bool(x.get("existing_owner_uid")),
            "existing_due":x.get("existing_due"),
        } for x in agenda],
    }
