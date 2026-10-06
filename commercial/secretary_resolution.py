"""Deterministic conversation resolution for Smart Secretary follow-up turns.

This module sits between natural-language extraction and draft mutation. It resolves
short confirmations/corrections only when a concrete, reviewable pending proposal
exists. It never invents identities or business facts.
"""
from __future__ import annotations
import copy,re
from datetime import datetime,timedelta,timezone

AFFIRMATIVE={
    "بله","بلی","آره","اره","بله همان است","بله همونه","همان است","همونه",
    "مورد تایید است","مورد تأیید است","مورد تاییده","مورد تأییده","تاییده","تأییده","تایید","تأیید","تایید است","تأیید است",
    "اوکی","اوکیه","درسته","درست است","بله درست است","yes","ok","okay",
}
NEGATIVE={
    "نه","خیر","نخیر","نه این نیست","این نیست","اشتباه است","اشتباهه",
    "تایید نمی کنم","تأیید نمی کنم","تایید نمیکنم","تأیید نمیکنم","no",
}
CONFIRM_CUES=("تأیید کنید","تایید کنید","آیا","منظور","همان کاربر","همین کاربر","درسته","درست است")


def normalize_text(value):
    text=str(value or "").strip().casefold().replace("\u200c"," ").replace("ي","ی").replace("ك","ک")
    text=text.translate(str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩","01234567890123456789"))
    text=text.replace("'"," ")
    text=re.sub(r'[«»"\u060c,؟?!؛;:()\[\]{}]+'," ",text)
    # Preserve dots inside usernames such as mgr.sales, but drop sentence dots.
    text=re.sub(r"\.(?=\s|$)"," ",text)
    return re.sub(r"\s+"," ",text).strip()


def _compact_confirmation_text(value):
    text=normalize_text(value)
    for prefix in ("بله ","آره ","اره ","اوکی ","باشه ","تایید ","تأیید ","نه ","خیر "):
        if text.startswith(prefix) and len(text)>len(prefix):
            # Keep phrases such as "بله همان است" as affirmative, but expose
            # explicit corrections like "بله administrator" to identity lookup.
            tail=text[len(prefix):].strip()
            if tail not in ("همان است","همونه","درست است","درسته"):
                return tail
    return text


def is_affirmative(value):
    text=normalize_text(value)
    if text in AFFIRMATIVE:return True
    return bool(re.fullmatch(r"(?:بله|آره|اره|اوکی|باشه)(?:\s+(?:همان|همونه|درست|درسته|مورد\s+تایید|مورد\s+تأیید))?(?:\s+است)?",text))


def is_negative(value):
    text=normalize_text(value)
    if text in NEGATIVE:return True
    return text.startswith("نه ") or text.startswith("خیر ")


def _aliases(person):
    result=set()
    for key in ("username","avan_username","name","avan_name"):
        raw=str(person.get(key) or "").strip()
        if raw:result.add(normalize_text(raw))
    username=normalize_text(person.get("username") or person.get("avan_username") or "")
    if username=="administrator":
        result.update({"admin","ادمین","administrator","مدیر سیستم"})
    if username=="ceo":
        result.update({"ceo","مدیرعامل","مدیر عامل"})
    return {x for x in result if x}


def unique_person(raw,directory):
    """Return one active UID for an explicit identity, otherwise None."""
    needle=normalize_text(raw)
    if not needle:return None
    active={str(uid):p for uid,p in (directory or {}).items() if p.get("active")}
    if needle in active:return needle
    matches=[]
    for uid,person in active.items():
        aliases=_aliases(person)
        if needle in aliases:
            matches.append(uid)
    return matches[0] if len(matches)==1 else None


def person_display(uid,directory):
    person=(directory or {}).get(str(uid)) or {}
    return str(person.get("username") or person.get("avan_username") or person.get("name") or person.get("avan_name") or uid)


def get_path(values,path):
    parts=str(path or "").split(".")
    node=values
    for part in parts:
        if not isinstance(node,dict) or part not in node:return None
        node=node[part]
    return node


def set_path(values,path,value):
    parts=str(path or "").split(".")
    if not parts or any(not part for part in parts):raise ValueError("مسیر تأیید معتبر نیست.")
    result=copy.deepcopy(values)
    node=result
    for part in parts[:-1]:
        existing=node.get(part)
        if not isinstance(existing,dict):
            existing={}
            node[part]=existing
        node=existing
    node[parts[-1]]=value
    return result


def _select_missing_uid_path(gaps,reply):
    candidates=[]
    for item in gaps or []:
        field=str(item.get("field") or "")
        if field.endswith("UID"):
            candidates.append((field,str(item.get("question") or "")))
    if not candidates:return None,None
    if len(candidates)==1:return candidates[0]

    text=normalize_text(reply)
    row=None
    match=re.search(r"(?:اقدام|ردیف)\s*(\d+)",text)
    if not match:
        match=re.search(r"\ba\s*-?\s*0*(\d+)\b",text)
    if match:row=str(int(match.group(1)))
    if row:
        matched=[item for item in candidates if ("."+row+".") in item[0]]
        if len(matched)==1:return matched[0]
    # Multiple unresolved identity paths without a unique row reference are
    # intentionally left unresolved. Never bind a confirmation to "the first".
    return None,None


def _mentioned_people(text,directory):
    normalized=normalize_text(text)
    found=[]
    for uid,person in (directory or {}).items():
        if not person.get("active"):continue
        for alias in sorted(_aliases(person),key=len,reverse=True):
            if not alias:continue
            # Usernames/names must be present as a complete normalized phrase.
            if re.search(r"(?<![\w.])"+re.escape(alias)+r"(?![\w.])",normalized,re.UNICODE):
                found.append(str(uid));break
    return list(dict.fromkeys(found))


def propose_identity_confirmation(reply,current,gaps,directory):
    """Build a pending proposal only from a unique identity explicitly named by AVAN."""
    raw=str(reply or "")
    normalized=normalize_text(raw)
    if not raw or not any(normalize_text(cue) in normalized for cue in CONFIRM_CUES):
        return None
    path,question=_select_missing_uid_path(gaps,raw)
    if not path:return None
    candidates=_mentioned_people(raw,directory)
    if len(candidates)!=1:return None
    uid=candidates[0]
    now=datetime.now(timezone.utc)
    return {
        "version":1,
        "kind":"set_identity",
        "field_path":path,
        "value":uid,
        "display":person_display(uid,directory),
        "question":question,
        "expected_value":copy.deepcopy(get_path(current,path)),
        "created_at":now.isoformat(),
        "expires_at":(now+timedelta(hours=24)).isoformat(),
        "source":"assistant_confirmation",
    }


def _remove_resolved_questions(questions,pending):
    path=str((pending or {}).get("field_path") or "")
    question=str((pending or {}).get("question") or "")
    result=[]
    for item in questions or []:
        text=str(item)
        if question and text==question:continue
        if path and path in text:continue
        result.append(text)
    return result


def resolve_pending(text,current,questions,pending,directory):
    """Resolve an existing confirmation without invoking an LLM.

    Returns None when the message is not a deterministic answer to the pending
    proposal. Otherwise returns a dict with updated values/questions/reply.
    """
    if not isinstance(pending,dict) or pending.get("version")!=1:return None
    path=str(pending.get("field_path") or "")
    value=str(pending.get("value") or "")
    if not path or not value:return None

    # Never apply a proposal after its draft target changed or its confirmation
    # window expired. This prevents stale conversational context overwriting a
    # newer manual edit or a long-lived draft.
    expires_at=str(pending.get("expires_at") or "")
    if expires_at:
        try:
            if datetime.now(timezone.utc)>datetime.fromisoformat(expires_at):
                return {
                    "values":copy.deepcopy(current),"questions":list(questions),
                    "pending_confirmation":None,"intent":"question",
                    "reply":"پیشنهاد قبلی منقضی شده است؛ لطفاً انتخاب را دوباره مشخص کنید.",
                    "resolution":"expired",
                }
        except ValueError:
            return None
    if "expected_value" in pending and get_path(current,path)!=pending.get("expected_value"):
        return {
            "values":copy.deepcopy(current),"questions":list(questions),
            "pending_confirmation":None,"intent":"question",
            "reply":"اطلاعات این مورد بعد از پیشنهاد قبلی تغییر کرده است؛ برای جلوگیری از بازنویسی، لطفاً انتخاب فعلی را دوباره مشخص کنید.",
            "resolution":"stale_draft",
        }

    raw=normalize_text(text)
    compact=_compact_confirmation_text(text)

    # Explicit correction takes precedence over "yes/no" prefixes.
    candidate=unique_person(compact,directory)
    if candidate and candidate!=value:
        updated=set_path(current,path,candidate)
        remaining=_remove_resolved_questions(questions,pending)
        display=person_display(candidate,directory)
        return {
            "values":updated,"questions":remaining,"pending_confirmation":None,
            "intent":"resolved",
            "reply":"اصلاح شما ثبت شد؛ این مورد روی «"+display+"» تنظیم شد.",
            "resolution":"correction",
        }

    if is_affirmative(raw):
        # Revalidate the candidate against the current active directory. A stale
        # proposal cannot be confirmed after a user is disabled/removed.
        if unique_person(value,directory)!=value:
            return {
                "values":copy.deepcopy(current),"questions":list(questions),
                "pending_confirmation":None,"intent":"question",
                "reply":"پیشنهاد قبلی دیگر در فهرست کاربران فعال معتبر نیست؛ لطفاً شخص را دوباره مشخص کنید.",
                "resolution":"stale",
            }
        updated=set_path(current,path,value)
        remaining=_remove_resolved_questions(questions,pending)
        return {
            "values":updated,"questions":remaining,"pending_confirmation":None,
            "intent":"resolved",
            "reply":"تأیید شد؛ این مورد روی «"+str(pending.get("display") or person_display(value,directory))+"» تنظیم شد.",
            "resolution":"confirmed",
        }

    if is_negative(raw):
        return {
            "values":copy.deepcopy(current),"questions":list(questions),
            "pending_confirmation":None,"intent":"question",
            "reply":"باشه؛ پیشنهاد قبلی ثبت نشد. لطفاً شخص درست را با نام یا نام کاربری دقیق مشخص کنید.",
            "resolution":"rejected",
        }

    # A direct identity response ("administrator", "ادمین", "mgr.sales") can
    # resolve the same pending field without round-tripping through the model.
    candidate=unique_person(raw,directory)
    if candidate:
        updated=set_path(current,path,candidate)
        remaining=_remove_resolved_questions(questions,pending)
        display=person_display(candidate,directory)
        return {
            "values":updated,"questions":remaining,"pending_confirmation":None,
            "intent":"resolved",
            "reply":"مسئول مشخص شد و روی «"+display+"» تنظیم شد.",
            "resolution":"direct_identity",
        }
    return None


def safe_public_pending(pending):
    """Expose no more than review-safe confirmation metadata."""
    if not isinstance(pending,dict):return None
    return {k:pending.get(k) for k in ("version","kind","field_path","display","question","created_at") if k in pending}
