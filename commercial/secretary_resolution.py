"""Deterministic conversation resolution for Smart Secretary follow-up turns.

This module sits between natural-language extraction and draft mutation. It resolves
short confirmations/corrections only when a concrete, reviewable pending proposal
exists. It never invents identities or business facts.
"""
from __future__ import annotations
import copy,re
from difflib import SequenceMatcher
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
    # Normalize human-typed dotted usernames: "mgr .licensing",
    # "mgr. licensing" and "mgr . licensing" all become "mgr.licensing".
    text=re.sub(r"(?<=[A-Za-z0-9_])\s*\.\s*(?=[A-Za-z0-9_])",".",text)
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


def _identity_forms(value):
    """Exact human forms for identity matching; never fuzzy-match different people."""
    normalized=normalize_text(value)
    if not normalized:return set()
    result={normalized}
    # Persian speech/text frequently joins role words ("مدیرمالی"). Keep this
    # as an exact alias only; uniqueness is still required across the directory.
    if re.search(r"[\u0600-\u06FF]",normalized) and " " in normalized:
        compact=normalized.replace(" ","")
        if len(compact)>=4:result.add(compact)
    return result


def _aliases(person):
    result=set()
    for key in (
        "username","avan_username","name","avan_name",
        "position","title","unit","department","department_name",
    ):
        result.update(_identity_forms(person.get(key) or ""))
    username=normalize_text(person.get("username") or person.get("avan_username") or "")
    if "." in username:
        # Human speech/text often drops punctuation from usernames.
        result.add(username.replace("."," "))
    # A manager account bound to an organizational unit can safely expose the
    # natural Persian role alias "مدیر <واحد>" without guessing a random user.
    unit=normalize_text(
        person.get("unit") or person.get("department") or person.get("department_name") or ""
    )
    if username.startswith("mgr.") and unit:
        unit_forms={unit}
        cleaned=re.sub(r"^(?:واحد|مدیریت|اداره|دپارتمان|امور)\s+","",unit).strip()
        if cleaned:unit_forms.add(cleaned)
        compact_tokens=[x for x in unit.split() if x not in {"واحد","مدیریت","اداره","دپارتمان","امور"}]
        if compact_tokens:unit_forms.add(" ".join(compact_tokens))
        for unit_form in unit_forms:
            result.update(_identity_forms("مدیر "+unit_form))
    if username=="administrator":
        result.update({"admin","ادمین","administrator","مدیر سیستم","مدیرسیستم"})
    if username=="ceo":
        result.update({"ceo","مدیرعامل","مدیر عامل"})
    return {x for x in result if x}


_ROLE_WORDS={"مدیر","کارشناس","رئیس","رییس","سرپرست","معاون","دبیر","مسئول","مدیریت"}
_ROLE_STOPWORDS={"و","واحد","اداره","دپارتمان","امور","بخش","سمت"}


def _role_tokens(value):
    normalized=normalize_text(value).replace("رییس","رئیس")
    return [x for x in normalized.split() if x and x not in _ROLE_STOPWORDS]


def _role_aliases(person):
    """Role-bearing aliases only; unit-only aliases are not enough for a role query."""
    result=set()
    for key in ("name","avan_name","position","title"):
        result.update(_identity_forms(person.get(key) or ""))
    username=normalize_text(person.get("username") or person.get("avan_username") or "")
    if username:
        result.update(_identity_forms(username))
        if "." in username:result.add(username.replace("."," "))
    unit=normalize_text(
        person.get("unit") or person.get("department") or person.get("department_name") or ""
    )
    if username.startswith("mgr.") and unit:
        cleaned=re.sub(r"^(?:واحد|مدیریت|اداره|دپارتمان|امور)\s+","",unit).strip()
        for value in {unit,cleaned}:
            if value:result.update(_identity_forms("مدیر "+value))
    if username=="administrator":result.update({"admin","ادمین","administrator","مدیر سیستم","مدیرسیستم"})
    if username=="ceo":result.update({"ceo","مدیرعامل","مدیر عامل"})
    return {x for x in result if x}


def _role_score(query,alias):
    q=normalize_text(query).replace("رییس","رئیس")
    a=normalize_text(alias).replace("رییس","رئیس")
    if not q or not a:return 0.0
    if q==a:return 1.0
    if q.replace(" ","")==a.replace(" ",""):return .995

    qt=_role_tokens(q);at=_role_tokens(a)
    if not qt or not at:return 0.0
    qset=set(qt);aset=set(at)

    qroles={x for x in qset if x in _ROLE_WORDS}
    aroles={x for x in aset if x in _ROLE_WORDS}
    # A manager request must never silently become an expert/chief/etc.
    if qroles and aroles and qroles.isdisjoint(aroles):
        return 0.0

    overlap=len(qset & aset)
    if overlap==0:return 0.0
    coverage=overlap/len(qset)
    precision=overlap/len(aset)
    ratio=SequenceMatcher(None,q,a).ratio()

    # "مدیر فروش" -> "مدیر فروش و بازاریابی" is intentionally strong,
    # while "مدیر فروش" -> "کارشناس فروش" is rejected above.
    if qset <= aset:
        subset=.94-max(0,len(aset)-len(qset))*.015
    elif aset <= qset:
        subset=.90-max(0,len(qset)-len(aset))*.02
    else:
        subset=0.0
    return max(subset,.55*coverage+.20*precision+.25*ratio)


def best_person_match(raw,directory,*,min_score=.82,min_margin=.07):
    """Resolve a human identity query to one real active ProcessMaker user.

    Exact UID/username/name/position aliases win first. Fuzzy matching is only
    enabled for role-bearing phrases and requires both a high score and a clear
    margin over the runner-up. The returned value is always a real directory UID.
    """
    text=normalize_text(raw)
    if not text:return {"uid":None,"score":0.0,"reason":"empty","candidates":[]}
    active={str(uid):p for uid,p in (directory or {}).items() if p.get("active")}

    # A real PM UID is accepted only when it exists and is active.
    for uid in active:
        if text==uid.casefold():
            return {"uid":uid,"score":1.0,"reason":"uid_exact","candidates":[uid]}

    needles=_identity_forms(text)
    exact=[]
    for uid,person in active.items():
        if needles & _aliases(person):exact.append(uid)
    exact=list(dict.fromkeys(exact))
    if len(exact)==1:
        return {"uid":exact[0],"score":1.0,"reason":"alias_exact","candidates":exact}
    if len(exact)>1:
        return {"uid":None,"score":1.0,"reason":"ambiguous_exact","candidates":exact[:8]}

    tokens=set(_role_tokens(text))
    if not (tokens & _ROLE_WORDS):
        return {"uid":None,"score":0.0,"reason":"no_exact_non_role","candidates":[]}

    scored=[]
    for uid,person in active.items():
        best=0.0;best_alias=""
        for alias in _role_aliases(person):
            score=_role_score(text,alias)
            if score>best:
                best=score;best_alias=alias
        if best>0:
            scored.append((best,uid,best_alias))
    scored.sort(key=lambda x:(-x[0],str(x[1])))
    if not scored or scored[0][0]<min_score:
        return {"uid":None,"score":scored[0][0] if scored else 0.0,
                "reason":"below_threshold","candidates":[x[1] for x in scored[:5]]}

    top=scored[0];second=scored[1][0] if len(scored)>1 else 0.0
    if len(scored)>1 and top[0]-second<min_margin:
        return {"uid":None,"score":top[0],"reason":"ambiguous_fuzzy",
                "candidates":[x[1] for x in scored[:5]]}
    return {"uid":top[1],"score":top[0],"reason":"role_fuzzy",
            "matched_alias":top[2],"candidates":[x[1] for x in scored[:5]]}


def unique_person(raw,directory):
    """Return exactly one real active PM UID for a name/username/role query."""
    return best_person_match(raw,directory).get("uid")


def strict_identity_mentions(text,directory):
    """People explicitly evidenced by username/name/title/position in this text.

    Unit-only overlap is deliberately insufficient: «کارشناس بازرگانی» must not
    silently resolve to a «مدیر بازرگانی» merely because both belong to the
    commercial unit.
    """
    normalized=normalize_text(text)
    if not normalized:return []
    found=[]
    for uid,person in (directory or {}).items():
        if not person.get("active"):continue
        aliases=set()
        for key in ("username","avan_username","name","avan_name","position","title"):
            aliases.update(_identity_forms(person.get(key) or ""))
        username=normalize_text(person.get("username") or person.get("avan_username") or "")
        unit=normalize_text(person.get("unit") or person.get("department") or person.get("department_name") or "")
        if username.startswith("mgr.") and unit:
            cleaned=re.sub(r"^(?:واحد|مدیریت|اداره|دپارتمان|امور)\s+","",unit).strip()
            for value in {unit,cleaned}:
                if value:aliases.update(_identity_forms("مدیر "+value))
        if username=="administrator":aliases.update({"admin","ادمین","administrator","مدیر سیستم","مدیرسیستم"})
        if username=="ceo":aliases.update({"ceo","مدیرعامل","مدیر عامل"})
        for alias in sorted((x for x in aliases if x),key=len,reverse=True):
            if re.search(r"(?<![\w.])"+re.escape(alias)+r"(?![\w.])",normalized,re.UNICODE):
                found.append(str(uid));break
    return list(dict.fromkeys(found))


def person_display(uid,directory):
    person=(directory or {}).get(str(uid)) or {}
    return str(person.get("name") or person.get("avan_name") or person.get("username") or person.get("avan_username") or uid).strip()


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


def _row_reference(text):
    normalized=normalize_text(text)
    match=re.search(r"(?:اقدام|ردیف)\s*(?:a\s*-?\s*)?0*(\d+)\b",normalized)
    if not match:
        match=re.search(r"\ba\s*-?\s*0*(\d+)\b",normalized)
    return str(int(match.group(1))) if match else None


def _last_assistant_target(history):
    """Return a unique row explicitly asked for in the latest assistant turn."""
    for item in reversed(list(history or [])):
        if not isinstance(item,dict) or item.get("role")!="assistant":continue
        text=str(item.get("text") or "")
        if not text:continue
        row=_row_reference(text)
        if row:return row
        # Stop at the latest assistant message; older context must never silently
        # redirect a new answer to a stale action row.
        return None
    return None


def _select_missing_uid_path(gaps,reply,history=()):
    candidates=[]
    for item in gaps or []:
        field=str(item.get("field") or "")
        if field.endswith("UID"):
            candidates.append((field,str(item.get("question") or "")))
    if not candidates:return None,None
    if len(candidates)==1:return candidates[0]

    row=_row_reference(reply) or _last_assistant_target(history)
    if row:
        matched=[item for item in candidates if ("."+row+".") in item[0]]
        if len(matched)==1:return matched[0]
    # Multiple unresolved identity paths without an explicit current-row context
    # are intentionally left unresolved. Never bind to "the first" gap.
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


def resolve_direct_identity(text,current,questions,gaps,directory,history=()):
    """Resolve an explicit person answer for one unambiguous missing UID path.

    This intentionally rejects questions and negations; those continue through
    normal conversation handling instead of being treated as edits.
    """
    original=str(text or "")
    raw=normalize_text(original)
    if not raw or is_affirmative(raw) or is_negative(raw):return None
    if "؟" in original or "?" in original:return None
    if any(token in raw for token in ("آیا","کیه","کی هست","چه کسی","کدام کاربر","کدوم کاربر","نیست","نباشد")):
        return None
    path,question=_select_missing_uid_path(gaps,text,history)
    if not path:return None
    candidates=_mentioned_people(text,directory)
    if len(candidates)!=1:
        # Short aliases such as "ادمین" may not appear as a canonical directory
        # phrase but can still be a deterministic unique alias.
        candidate=unique_person(raw,directory) if len(raw)<=120 else None
        candidates=[candidate] if candidate else []
    if len(candidates)!=1:return None
    uid=candidates[0]
    updated=set_path(current,path,uid)
    pending={"field_path":path,"question":question}
    return {
        "values":updated,
        "questions":_remove_resolved_questions(questions,pending),
        "pending_confirmation":None,
        "intent":"resolved",
        "reply":"شخص مشخص شد و این مورد روی «"+person_display(uid,directory)+"» تنظیم شد.",
        "resolution":"direct_identity",
    }


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


def _question_targets_path(text,path):
    normalized=normalize_text(text)
    path=str(path or "")
    if not normalized or not path:return False
    if path in str(text):return True
    action=re.fullmatch(r"MTG_Actions\.(\d+)\.MTG_ActionOwnerUID",path)
    if action:
        row=action.group(1)
        has_row=bool(
            re.search(r"(?:اقدام|ردیف)\s*(?:a\s*-?\s*)?0*"+re.escape(row)+r"\b",normalized)
            or re.search(r"/\s*0*"+re.escape(row)+r"\s*/",normalized)
        )
        has_owner=any(word in normalized for word in ("مسئول","اقدام کننده","اقدام‌کننده","owner"))
        return has_row and has_owner
    agenda=re.fullmatch(r"MTG_Agenda\.(\d+)\.MTG_AgendaPresenterUID",path)
    if agenda:
        row=agenda.group(1)
        has_row=bool(
            re.search(r"(?:دستور جلسه|ردیف)\s*0*"+re.escape(row)+r"\b",normalized)
            or re.search(r"/\s*0*"+re.escape(row)+r"\s*/",normalized)
        )
        return has_row and "ارائه" in normalized
    if path=="MTG_ChairUserUID":
        return "رئیس" in normalized or "رییس" in normalized
    if path=="MTG_SecretaryUserUID":
        return "دبیر" in normalized
    return False


def _remove_resolved_questions(questions,pending):
    path=str((pending or {}).get("field_path") or "")
    question=str((pending or {}).get("question") or "")
    result=[]
    for item in questions or []:
        text=str(item)
        if question and text==question:continue
        if _question_targets_path(text,path):continue
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
    if candidate:
        updated=set_path(current,path,candidate)
        remaining=_remove_resolved_questions(questions,pending)
        display=person_display(candidate,directory)
        if candidate==value:
            return {
                "values":updated,"questions":remaining,"pending_confirmation":None,
                "intent":"resolved",
                "reply":"تأیید شد؛ این مورد روی «"+display+"» تنظیم شد.",
                "resolution":"confirmed_explicit_identity",
            }
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
