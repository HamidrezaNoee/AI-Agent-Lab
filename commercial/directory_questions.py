"""Fetch ONLY the linked user's authorized v2 meeting indexes for Q&A.

The v2 subject/tenant/subtree check runs before any action retrieval. Action
ids are derived server-side from those previously authorized meeting records,
not from the user prompt. A bounded, read-only snapshot supports deterministic
responses and declares truncation or unavailable PM projection fields.
"""
from .directory_access import visible_directory_meetings
from .security import Principal
from .sql_store import AccessDenied

MAX_MEETINGS=2000
PAGE=50
ACTION_BATCH=40


def authorized_question_snapshot(con, principal: Principal):
    meetings=[]
    seen=set()
    cursor=None
    complete=True

    for _ in range(MAX_MEETINGS//PAGE):
        page=visible_directory_meetings(con, principal, before_id=cursor, limit=PAGE)
        rows=page["meetings"]
        for m in rows:
            identifier=int(m["meeting_id"])
            if identifier in seen:
                raise AccessDenied("Unstable authorized meeting pagination")
            seen.add(identifier)
            meetings.append({
                "meeting_id":identifier,
                "meeting_no":str(m["meeting_no"]),
                "title":str(m["title"]),
                "meeting_status":str(m["status"]),
                # The present commercial MeetingIndex has NO HeldAtUtc/risk
                # columns. Never copy raw unscoped PM records or invent dates.
                "meeting_date_utc":None,
                "risk":None,
                "actions":[],
            })
        if not page["has_more"]:
            break
        candidate=page["next_cursor"]
        if not isinstance(candidate,int) or candidate<=0 or candidate==cursor:
            raise AccessDenied("Invalid authorized meeting cursor")
        cursor=candidate
    else:
        complete=False

    by_id={m["meeting_id"]:m for m in meetings}
    ids=list(by_id)
    for start in range(0,len(ids),ACTION_BATCH):
        batch=ids[start:start+ACTION_BATCH]
        placeholders=",".join("?" for _ in batch)
        sql=(
            "SELECT a.MeetingID,a.ActionNo,a.ActionTitle,a.OwnerUnit,"
            "a.DueAtUtc,a.ProgressPercent,a.IsClosed "
            "FROM AgentProduct.ActionIndex a WHERE a.TenantID=? "
            "AND a.MeetingID IN ("+placeholders+") "
            "ORDER BY a.MeetingID,a.DueAtUtc,a.ActionNo"
        )
        cur=con.cursor()
        cur.execute(sql,str(principal.tenant_id),*batch)
        for r in cur.fetchall():
            identifier=int(r[0])
            if identifier not in by_id or identifier not in batch:
                raise AccessDenied("Action returned outside authorized meeting scope")
            by_id[identifier]["actions"].append({
                "action_no":str(r[1]),"description":str(r[2]),
                "owner_unit":str(r[3]),"due_at_utc":str(r[4]),
                "progress_percent":int(r[5]),"is_closed":bool(r[6])
            })
    return meetings,complete
