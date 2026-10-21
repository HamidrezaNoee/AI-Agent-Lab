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


def is_compound_minutes(notes,task):
    """True when a minutes turn contains status plus substantive minutes content."""
    if (task or {}).get("stage")!="minutes":return False
    raw=_norm(notes)
    score=0
    signals=(
        ("status",("جلسه تشکیل شد","جلسه تشکیل نشد","جلسه برگزار شد","جلسه برگزار نشد")),
        ("discussion",("شرح مذاکرات","شرح و جمع بندی","شرح و جمع‌بندی","جمع بندی مذاکرات","جمع‌بندی مذاکرات")),
        ("parking",("موضوعات خارج از دستور","موضوعات خارچ از دستور","خارج از دستور","خارچ از دستور","parking lot")),
        ("decisions",("مصوبات","مصوبه")),
        ("actions",("اقدامات","اثدامات","اقدام‌ها","اقدام ها")),
        ("priority",("اولویت همه اقدامات","اوليت همه اقدامات","اولیت همه اقدامات")),
    )
    for _,tokens in signals:
        if any(_norm(token) in raw for token in tokens):score+=1
    return score>=2 or (
        any(x in raw for x in ("مصوبات","مصوبه"))
        and any(x in raw for x in ("اقدامات","اثدامات","اقدام‌ها","اقدام ها"))
    )


def is_compound_turn(notes,task):
    if is_compound_invitation(notes,task) or is_compound_minutes(notes,task):
        return True
    # All remaining stages use the same invariant: when one user message carries
    # two or more independently writable facts, no fast-path tool may terminate
    # the turn before exhaustive extraction has seen the whole message.
    requirements=explicit_field_requirements(notes,task)
    if len(requirements)>=2:return True
    # Headed/multiline operational reports often express one field by label and
    # another by value-only continuation. Treat them as dense once one writable
    # field is explicit.
    return len(requirements)>=1 and str(notes or "").count("\n")>=2


def explicit_field_requirements(notes,task):
    stage=(task or {}).get("stage")
    raw=_norm(notes)
    result=[]
    def add(field,label,condition):
        if condition and field not in {x["field"] for x in result}:
            result.append({"field":field,"label":label})
    if stage=="invitation":
        add("MTG_MeetingTitle","عنوان جلسه",any(x in raw for x in ("با عنوان","عنوان جلسه")))
        add("MTG_Objective","هدف جلسه","هدف جلسه" in raw)
        add("MTG_Location","مکان جلسه",("برگزار" in raw and " در " in " "+raw+" ") or "مکان جلسه" in raw or "اتاق جلسات" in raw)
        add("MTG_MeetingStartDateTime","تاریخ جلسه",any(x in raw for x in ("برای تاریخ","تاریخ برگزاری")))
        add("MTG_MeetingStartTime","ساعت شروع جلسه",bool(re.search(r'(?:برای تاریخ|تاریخ برگزاری).{0,100}\bساعت\b',raw,re.S)))
        add("MTG_ChairUserUID","رئیس جلسه",any(x in raw for x in ("رئیس جلسه","رییس جلسه")))
        add("MTG_SecretaryUserUID","دبیر جلسه","دبیر جلسه" in raw)
        add("MTG_Participants","شرکت‌کنندگان",any(x in raw for x in ("شرکت کنندگان","شرکت‌کنندگان","مدعوین")))
        add("MTG_Agenda","دستور جلسه",any(x in raw for x in ("دستور جلسه","محورهای جلسه")))
    elif stage=="minutes":
        add("MTG_MeetingHeld","وضعیت تشکیل جلسه",any(x in raw for x in ("جلسه تشکیل شد","جلسه تشکیل نشد","جلسه برگزار شد","جلسه برگزار نشد")))
        add("MTG_MeetingDiscussionSummary","شرح مذاکرات",any(x in raw for x in ("شرح مذاکرات","شرح و جمع بندی","شرح و جمع‌بندی","جمع بندی مذاکرات","جمع‌بندی مذاکرات")))
        add("MTG_ParkingLot","موضوعات خارج از دستور",any(x in raw for x in ("موضوعات خارج از دستور","موضوعات خارچ از دستور","خارج از دستور","خارچ از دستور","parking lot")))
        add("MTG_Decisions","مصوبات",any(x in raw for x in ("مصوبات","مصوبه")))
        add("MTG_Actions","اقدامات",any(x in raw for x in ("اقدامات","اثدامات","اقدام‌ها","اقدام ها")))
    elif stage=="invitation_approval":
        add("MTG_InvitationApproval","تصمیم تأیید دعوت‌نامه",any(x in raw for x in ("تایید دعوت","تأیید دعوت","دعوت نامه تایید","دعوت‌نامه تایید","دعوت‌نامه تأیید","تایید می کنم","تأیید می کنم","تایید میکنم","تأیید میکنم","مورد تایید","مورد تأیید","نیاز به اصلاح","برای اصلاح برگرد")))
        add("MTG_InvitationChairComment","توضیحات رئیس برای دعوت‌نامه",any(x in raw for x in ("توضیح رئیس","توضیحات رئیس","اصلاحات موردنظر","اصلاحات مورد نظر","نظر رئیس")))
        add("MTG_MeetingTitle","عنوان جلسه",any(x in raw for x in ("عنوان جلسه","عنوان را")))
        add("MTG_Objective","هدف جلسه","هدف جلسه" in raw)
        add("MTG_Location","مکان جلسه",any(x in raw for x in ("مکان جلسه","محل جلسه","لینک جلسه")))
        add("MTG_MeetingStartDateTime","تاریخ جلسه",any(x in raw for x in ("تاریخ جلسه","تاریخ برگزاری")))
        add("MTG_MeetingStartTime","ساعت شروع جلسه",any(x in raw for x in ("ساعت شروع","ساعت برگزاری")))
        add("MTG_MeetingEndDateTime","تاریخ پایان برنامه‌ریزی‌شده","تاریخ پایان برنامه" in raw)
        add("MTG_PlannedActionEndTime","ساعت پایان برنامه‌ریزی‌شده","ساعت پایان برنامه" in raw)
    elif stage=="minutes_approval":
        add("MTG_MinutesApproval","تصمیم تأیید صورت‌جلسه",any(x in raw for x in ("تایید صورت جلسه","تأیید صورت جلسه","تایید صورت‌جلسه","تأیید صورت‌جلسه","صورت جلسه تایید","صورت‌جلسه تأیید","تایید می کنم","تأیید می کنم","تایید میکنم","تأیید میکنم","مورد تایید","مورد تأیید","نیاز به اصلاح","برای اصلاح برگرد")))
        add("MTG_ChairComment","توضیحات رئیس جلسه",any(x in raw for x in ("توضیح رئیس","توضیحات رئیس","نظر رئیس","اصلاحات موردنظر","اصلاحات مورد نظر")))
        add("MTG_MeetingDiscussionSummary","شرح مذاکرات",any(x in raw for x in ("شرح مذاکرات","شرح و جمع بندی","شرح و جمع‌بندی")))
        add("MTG_ParkingLot","موضوعات خارج از دستور",any(x in raw for x in ("موضوعات خارج از دستور","خارج از دستور")))
        add("MTG_ApprovalSummary","خلاصه مصوبات و اقدامات",any(x in raw for x in ("خلاصه مصوبات","خلاصه اقدامات","خلاصه مصوبات و اقدامات")))
        add("MTG_Decisions","مصوبات",any(x in raw for x in ("مصوبات","مصوبه")))
        add("MTG_Actions","اقدامات",any(x in raw for x in ("اقدامات","اقدام ها","اقدام‌ها")) or bool(re.search(r'\bاقدام\s+(?:a\s*-?\s*)?[0-9]+',raw)))
    elif stage=="action_execution":
        add("MTGA_SubmissionType","نوع ارسال",any(x in raw for x in ("گزارش پیشرفت","اعلام تکمیل","تکمیل اقدام","اقدام تکمیل","کار تمام","کار تموم")))
        add("MTGA_ProgressPercent","درصد پیشرفت",bool(re.search(r'(?:پیشرفت|درصد).{0,30}(?:%|درصد|[0-9])',raw)))
        add("MTGA_ExecutionDescription","شرح اجرای اقدام",any(x in raw for x in ("شرح اجرا","شرح اقدام انجام","گزارش اجرا","گزارش پیشرفت","انجام دادم","انجام شده","انجام شد")))
        add("MTGA_ActualCompletionDateTime","تاریخ واقعی انجام",any(x in raw for x in ("تاریخ انجام","تاریخ تکمیل","تاریخ واقعی انجام")) or bool(re.search(r'در تاریخ.{0,50}(?:انجام|تکمیل)',raw)))
        add("MTGA_ActualCompletionTime","ساعت واقعی انجام",any(x in raw for x in ("ساعت انجام","ساعت تکمیل","ساعت واقعی انجام")) or bool(re.search(r'در ساعت.{0,40}(?:انجام|تکمیل)',raw)))
        add("MTGA_ActualEffortMinutes","زمان واقعی صرف‌شده",any(x in raw for x in ("زمان صرف","زمان واقعی","دقیقه وقت","دقیقه زمان","ساعت کار")))
    elif stage=="action_review":
        add("MTGA_ReviewStatus2","نتیجه بررسی اقدام",any(x in raw for x in ("تایید و بستن","تأیید و بستن","بسته شود","بستن اقدام","بازگشت برای اصلاح","نیاز به اصلاح","ادامه اقدام","rework")))
        add("MTGA_SecretaryProgressPercent2","درصد پیشرفت تأییدشده",bool(re.search(r'(?:پیشرفت|درصد).{0,40}(?:تایید|تأیید|%|درصد|[0-9])',raw)))
        add("MTGA_SecretaryActualCompletionDateTime2","تاریخ واقعی تأییدشده",any(x in raw for x in ("تاریخ واقعی","تاریخ انجام","تاریخ تکمیل")))
        add("MTGA_SecretaryActualCompletionTime2","ساعت واقعی تأییدشده",any(x in raw for x in ("ساعت واقعی","ساعت انجام","ساعت تکمیل")))
        add("MTGA_SecretaryActualEffortMinutes2","زمان واقعی تأییدشده",any(x in raw for x in ("زمان واقعی","زمان صرف","دقیقه")))
        add("MTGA_SecretaryComment1","نظر دبیر",any(x in raw for x in ("نظر دبیر","توضیح دبیر","توضیحات دبیر","کامنت","نظر من")))
    elif stage=="monitoring":
        add("MTG_ClosingNote","جمع‌بندی اختتام",any(x in raw for x in ("جمع بندی اختتام","جمع‌بندی اختتام","جمع بندی نهایی","جمع‌بندی نهایی","توضیح اختتام","اختتام")))
        add("MTG_ActionSummary","بررسی نهایی اقدامات",bool(re.search(r'(?:اقدام|a\s*-?\s*0*[0-9]+).{0,80}(?:بسته|اصلاح|بازگشت|پیشرفت|درصد|تایید|تأیید|نظر)',raw,re.S)))
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


_DECISION_WORDS={
    "یک":"1","اول":"1","دو":"2","دوم":"2","سه":"3","سوم":"3",
    "چهار":"4","چهارم":"4","پنج":"5","پنجم":"5","شش":"6","ششم":"6",
    "هفت":"7","هفتم":"7","هشت":"8","هشتم":"8","نه":"9","نهم":"9","ده":"10","دهم":"10",
}


def decision_expectations(notes):
    block=_section(notes,("مصوبات","مصوبات جلسه"),("اقدامات","اثدامات","اقدام‌ها","اقدام ها","اولویت","اوليت","اولیت"))
    result=[]
    for raw_no,body in _NUMBERED.findall(block):
        no=str(int(str(raw_no).translate(_DIGITS)))
        result.append({"index":no,"text":body.strip()})
    return result


def _decision_ref(text,decision_count=None):
    normalized=_norm(text)
    match=re.search(r'مصوبه\s*([0-9]+|یک|اول|دو|دوم|سه|سوم|چهار|چهارم|پنج|پنجم|شش|ششم|هفت|هفتم|هشت|هشتم|نه|نهم|ده|دهم)\b',normalized)
    if match:
        token=match.group(1)
        return str(int(token)) if token.isdigit() else _DECISION_WORDS.get(token)
    # Common speech-to-text typo in the owner's real minutes: «مصوبه کار» for
    # «مصوبه چهار». Apply only when the message itself has exactly four
    # numbered decisions; otherwise leave it ambiguous.
    if decision_count==4 and re.search(r'\bمصوبه\s+کار\b',normalized):
        return "4"
    return None


def _action_lines(notes):
    block=_section(notes,("اقدامات","اثدامات","اقدام‌ها","اقدام ها"),("اولویت","اوليت","اولیت"))
    if not block:return []
    lines=[];current=""
    for raw in block.splitlines():
        line=raw.strip()
        if not line:continue
        normalized=_norm(line)
        starts=normalized.startswith("مصوبه") or normalized.startswith("اقدام")
        if starts:
            if current:lines.append(current)
            current=line
        elif current:
            current+=" "+line
        else:
            current=line
    if current:lines.append(current)
    return lines


def action_expectations(notes,directory):
    result=[]
    decision_count=len(decision_expectations(notes))
    for index,line in enumerate(_action_lines(notes),1):
        people=resolution.strict_identity_mentions(line,directory)
        normalized=_norm(line)
        result.append({
            "row":str(index),
            "decision_index":_decision_ref(line,decision_count),
            "owner_uid":people[0] if len(people)==1 else None,
            "has_owner_phrase":("مدیر" in normalized or bool(people)),
            "has_due":bool(re.search(r'(?:تا\s+تاریخ|موعد|مهلت).{0,60}(?:مهر|آبان|آذر|دی|بهمن|اسفند|فروردین|اردیبهشت|خرداد|تیر|مرداد|شهریور|[0-9]{4}[/\-])',normalized)),
            "text":line,
        })
    return result


def monitoring_expectations(notes):
    """Rows explicitly referenced during final monitoring/review."""
    raw=str(notes or "").replace("\r\n","\n")
    refs=[]
    # Prefer line-local action references so field requirements remain scoped.
    for line in raw.split("\n"):
        normalized=_norm(line)
        match=re.search(r'(?:اقدام\s*)?(?:a\s*-?\s*0*)?([0-9]+)\b',normalized)
        if not match or not any(x in normalized for x in ("اقدام","a-","a ","بسته","اصلاح","بازگشت","پیشرفت","درصد","نظر","تایید","تأیید")):
            continue
        number=int(match.group(1));action_no=f"A-{number:03d}"
        refs.append({
            "action_no":action_no,
            "needs_status":any(x in normalized for x in ("بسته","بستن","اصلاح","بازگشت","rework","تایید","تأیید")),
            "needs_progress":("پیشرفت" in normalized or "درصد" in normalized),
            "needs_comment":any(x in normalized for x in ("نظر","توضیح","کامنت","علت")),
            "needs_actual_date":any(x in normalized for x in ("تاریخ واقعی","تاریخ انجام","تاریخ تکمیل")),
            "needs_actual_time":any(x in normalized for x in ("ساعت واقعی","ساعت انجام","ساعت تکمیل")),
            "needs_effort":any(x in normalized for x in ("زمان صرف","دقیقه","زمان واقعی")),
        })
    unique={}
    for item in refs:unique[item["action_no"]]=item
    return list(unique.values())


def all_actions_priority(notes):
    raw=_norm(notes)
    if re.search(r'(?:اولویت|اوليت|اولیت)\s+همه\s+اقدام(?:ات|ها| ها)?.{0,20}(?:بالا|زیاد)',raw):
        return "High"
    return None


def apply_system_defaults(notes,task,values,directory):
    """Fill identifiers/global flags that are deterministic, never business facts."""
    if (task or {}).get("stage")!="minutes":return values
    result=values
    decisions=[row for _,row in _rows(result.get("MTG_Decisions"))]
    for index,row in enumerate(decisions,1):
        if not row.get("MTG_DecisionNo"):
            row["MTG_DecisionNo"]=f"D-{index:03d}"
    decision_by_index={str(i):str(row.get("MTG_DecisionNo") or f"D-{i:03d}") for i,row in enumerate(decisions,1)}
    actions=[row for _,row in _rows(result.get("MTG_Actions"))]
    expected=action_expectations(notes,directory)
    priority=all_actions_priority(notes)
    for index,row in enumerate(actions,1):
        if not row.get("MTG_ActionNo"):
            row["MTG_ActionNo"]=f"A-{index:03d}"
        exp=expected[index-1] if index<=len(expected) else {}
        ref=exp.get("decision_index")
        if ref and not row.get("MTG_ActionDecisionNo") and ref in decision_by_index:
            row["MTG_ActionDecisionNo"]=decision_by_index[ref]
        if exp.get("owner_uid") and not row.get("MTG_ActionOwnerUID"):
            row["MTG_ActionOwnerUID"]=exp["owner_uid"]
        if priority and not row.get("MTG_ActionPriority"):
            row["MTG_ActionPriority"]=priority
    return result


def _rows(value):
    if not isinstance(value,dict):return []
    return [(str(k),v) for k,v in value.items() if isinstance(v,dict)]


def coverage_issues(notes,task,values,assignments,directory):
    """Return precise omissions. Empty means all explicitly detectable facts were covered."""
    issues=[];assigned={str(a.field) for a in assignments}
    from .secretary_runtime import form
    allowed=set(form(task))  # Match typed aliases and writable fields used by extraction.
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
    if (task or {}).get("stage") in ("minutes","minutes_approval"):
        decisions_expected=decision_expectations(notes)
        if decisions_expected and "MTG_Decisions" in allowed:
            rows=[row for _,row in _rows(values.get("MTG_Decisions"))]
            if len(rows)<len(decisions_expected):
                issues.append("همه مصوبات شماره‌دار پیام استخراج نشدند.")
            for index,exp in enumerate(decisions_expected,1):
                if index>len(rows):break
                row=rows[index-1]
                if not str(row.get("MTG_DecisionNo") or "").strip():
                    issues.append("شماره مصوبه ردیف "+exp["index"]+" تعیین نشد.")
                if not str(row.get("MTG_DecisionText") or "").strip():
                    issues.append("متن مصوبه ردیف "+exp["index"]+" استخراج نشد.")

        actions_expected=action_expectations(notes,directory)
        if actions_expected and "MTG_Actions" in allowed:
            rows=[row for _,row in _rows(values.get("MTG_Actions"))]
            if len(rows)<len(actions_expected):
                issues.append("همه اقدامات صریح پیام استخراج نشدند.")
            decision_rows=[row for _,row in _rows(values.get("MTG_Decisions"))]
            decision_by_index={str(i):str(row.get("MTG_DecisionNo") or "") for i,row in enumerate(decision_rows,1)}
            global_priority=all_actions_priority(notes)
            for index,exp in enumerate(actions_expected,1):
                if index>len(rows):break
                row=rows[index-1]
                label=str(row.get("MTG_ActionNo") or ("ردیف "+str(index)))
                if not str(row.get("MTG_ActionNo") or "").strip():
                    issues.append("شماره اقدام ردیف "+str(index)+" تعیین نشد.")
                if not str(row.get("MTG_ActionDescription") or "").strip():
                    issues.append("شرح اقدام "+label+" استخراج نشد.")
                if exp.get("owner_uid") and str(row.get("MTG_ActionOwnerUID") or "")!=exp["owner_uid"]:
                    issues.append("مسئول اقدام "+label+" از متن صریح تشخیص داده شد ولی ثبت نشد.")
                elif exp.get("has_owner_phrase") and not str(row.get("MTG_ActionOwnerUID") or "").strip():
                    issues.append("مسئول اقدام "+label+" استخراج نشد یا در کاربران فعال یکتا نبود.")
                if exp.get("has_due") and not str(row.get("MTG_persiandate_ActionDueDateTime") or "").strip():
                    issues.append("مهلت اقدام "+label+" استخراج نشد.")
                ref=exp.get("decision_index")
                if ref and decision_by_index.get(ref) and str(row.get("MTG_ActionDecisionNo") or "")!=decision_by_index[ref]:
                    issues.append("ارتباط اقدام "+label+" با مصوبه "+ref+" ثبت نشد.")
                if global_priority and str(row.get("MTG_ActionPriority") or "")!=global_priority:
                    issues.append("اولویت بالای اعلام‌شده روی اقدام "+label+" اعمال نشد.")
    if (task or {}).get("stage")=="monitoring":
        expected=monitoring_expectations(notes)
        if expected and "MTG_ActionSummary" in allowed:
            rows=[row for _,row in _rows(values.get("MTG_ActionSummary"))]
            by_no={str(row.get("MTG_MonActionNo") or "").strip().upper():row for row in rows}
            for exp in expected:
                row=by_no.get(exp["action_no"])
                if row is None:
                    issues.append("اقدام "+exp["action_no"]+" که در پیام بررسی شده بود در خلاصه پایش جا افتاده است.")
                    continue
                if exp["needs_status"] and not str(row.get("MTG_MonSecReviewStatus") or "").strip():
                    issues.append("نتیجه بررسی "+exp["action_no"]+" ثبت نشد.")
                if exp["needs_progress"] and not str(row.get("MTG_MonSecProgress") or "").strip():
                    issues.append("درصد تأییدشده "+exp["action_no"]+" ثبت نشد.")
                if exp["needs_comment"] and not str(row.get("MTG_MonSecComment") or "").strip():
                    issues.append("نظر دبیر برای "+exp["action_no"]+" ثبت نشد.")
                if exp["needs_actual_date"] and not str(row.get("MTG_MonSecActualDate") or "").strip():
                    issues.append("تاریخ واقعی تأییدشده "+exp["action_no"]+" ثبت نشد.")
                if exp["needs_actual_time"] and not str(row.get("MTG_MonSecActualTime") or "").strip():
                    issues.append("ساعت واقعی تأییدشده "+exp["action_no"]+" ثبت نشد.")
                if exp["needs_effort"] and not str(row.get("MTG_MonSecEffort") or "").strip():
                    issues.append("زمان تأییدشده "+exp["action_no"]+" ثبت نشد.")
    return list(dict.fromkeys(issues))


def coverage_prompt(notes,task,directory):
    fields=[x["label"] for x in explicit_field_requirements(notes,task)]
    participants=participant_expectations(notes,directory)
    agenda=agenda_expectations(notes,directory)
    decisions=decision_expectations(notes)
    actions=action_expectations(notes,directory)
    return {
        "stage":(task or {}).get("stage"),
        "explicit_fact_count":len(fields),
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
        "decision_count":len(decisions),
        "action_count":len(actions),
        "actions":[{
            "row":x["row"],"decision_index":x["decision_index"],
            "has_unique_owner":bool(x["owner_uid"]),"has_due":x["has_due"],
        } for x in actions],
        "all_actions_priority":all_actions_priority(notes),
        "monitoring_action_count":len(monitoring_expectations(notes)),
        "monitoring_actions":monitoring_expectations(notes),
    }

