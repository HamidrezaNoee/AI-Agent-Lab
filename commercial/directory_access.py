"""Hierarchy-aware meeting visibility for the isolated commercial lab.

Requires the verified OIDC subject to map to an ACTIVE, ENABLED PM directory
entry. Hierarchy is explicitly configured in DirectoryUser, not inferred from
ProcessMaker groups or names. GodAdmin alone NEVER grants tenant content access.
Regular experts see ONLY their own AND their subtree's involvement; Manager/SysAdmin
see all meetings of their tenant. No query ever omits tenant RLS or membership.
"""
from .security import Principal
from .sql_store import AccessDenied


def visible_directory_meetings(con, principal: Principal, *, before_id=None, limit=20) -> dict:
    if not 1 <= limit <= 50 or (before_id is not None and before_id <= 0):
        raise ValueError("Invalid page range")
    cur = con.cursor()
    cur.execute("""
        SELECT TOP (1) OrgRole,PMUserUID
        FROM AgentProduct.DirectoryUser
        WHERE TenantID=? AND SubjectID=? AND IsEnabled=1 AND PMStatus='ACTIVE'
    """,str(principal.tenant_id),principal.subject)
    viewer=cur.fetchone()
    if viewer is None:
        raise AccessDenied("Active linked ProcessMaker user required")
    role, uid=str(viewer[0]),str(viewer[1])
    if role not in {"Expert","Manager","SysAdmin"}:
        raise AccessDenied("Invalid directory role")
    # Role branch is determined by DATABASE lookup, NEVER a request parameter.
    # For Manager/SysAdmin the query still retains strict tenant RLS and ID bounds.
    params=[str(principal.tenant_id)]
    where="m.TenantID=?"
    if before_id is not None:
        where+=" AND m.MeetingID<?"
        params.append(before_id)
    if role=="Expert":
        query="""
        ;WITH Subtree(PMUserUID,Depth,Trail) AS (
            SELECT d.PMUserUID,CAST(0 AS int),
                   CAST(N'/' + d.PMUserUID + N'/' AS nvarchar(max))
            FROM AgentProduct.DirectoryUser d
            WHERE d.TenantID=? AND d.PMUserUID=?
              AND d.IsEnabled=1 AND d.PMStatus='ACTIVE'
            UNION ALL
            SELECT child.PMUserUID,parent.Depth+1,
                   CAST(parent.Trail + child.PMUserUID + N'/' AS nvarchar(max))
            FROM AgentProduct.DirectoryUser child
            JOIN Subtree parent
              ON child.ManagerPMUserUID=parent.PMUserUID
            WHERE child.TenantID=? AND child.IsEnabled=1
              AND child.PMStatus='ACTIVE' AND parent.Depth<32
              AND CHARINDEX(N'/' + child.PMUserUID + N'/',parent.Trail)=0
        )
        SELECT TOP (51) m.MeetingID,m.MeetingNo,m.MeetingTitle,m.MeetingStatus
        FROM AgentProduct.MeetingIndex m
        WHERE """+where+"""
          AND EXISTS(
            SELECT 1 FROM AgentProduct.MeetingActor a JOIN Subtree s
              ON s.PMUserUID=a.PMUserUID
            WHERE a.TenantID=m.TenantID AND a.MeetingID=m.MeetingID
          )
        ORDER BY m.MeetingID DESC
        OPTION (MAXRECURSION 32)
        """
        params=[str(principal.tenant_id),uid,str(principal.tenant_id),*params]
    else:
        query="""
        SELECT TOP (51) m.MeetingID,m.MeetingNo,m.MeetingTitle,m.MeetingStatus
        FROM AgentProduct.MeetingIndex m WHERE """+where+"""
        ORDER BY m.MeetingID DESC
        """
    cur.execute(query,*params)
    rows=cur.fetchall()
    page=rows[:limit]
    return {
        "role":role,"meetings":[{"meeting_id":int(r[0]),"meeting_no":str(r[1]),
                                "title":str(r[2]),"status":str(r[3])} for r in page],
        "returned":len(page),"has_more":len(rows)>limit,
        "next_cursor":int(page[-1][0]) if len(rows)>limit and page else None,
        "scope":"tenant" if role in ("Manager","SysAdmin") else "self-and-org-subtree",
    }


def directory_role(con, principal: Principal) -> str:
    cur=con.cursor()
    cur.execute("""
        SELECT TOP (1) OrgRole FROM AgentProduct.DirectoryUser
        WHERE TenantID=? AND SubjectID=? AND IsEnabled=1 AND PMStatus='ACTIVE'
    """,str(principal.tenant_id),principal.subject)
    row=cur.fetchone()
    if not row or str(row[0]) not in ("Expert","Manager","SysAdmin"):
        raise AccessDenied("Active identity-linked directory membership required")
    return str(row[0])


def visible_hierarchy_letters(con, principal: Principal, *, before_id=None, limit=20) -> dict:
    """Metadata-only letters: self, nonconfidential subtree, or explicit grant.

    Confidential subordinate letters are never disclosed by hierarchy alone.
    No letter rows are imported from actual office automation/ProcessMaker.
    """
    if not isinstance(limit, int) or not 1 <= limit <= 50:
        raise ValueError("Invalid letter page size")
    if before_id is not None and (
        not isinstance(before_id, str) or not 1 <= len(before_id) <= 100
    ):
        raise ValueError("Invalid letter cursor")
    cur=con.cursor()
    cur.execute("""
        SELECT TOP (1) PMUserUID
        FROM AgentProduct.DirectoryUser
        WHERE TenantID=? AND SubjectID=? AND IsEnabled=1 AND PMStatus='ACTIVE'
    """,str(principal.tenant_id),principal.subject)
    row=cur.fetchone()
    if row is None: raise AccessDenied("Active identity-linked PM user required")
    uid=str(row[0])
    params=[str(principal.tenant_id),uid,str(principal.tenant_id),
            str(principal.tenant_id),uid,principal.subject]
    where=""
    if before_id is not None:
        where=" AND l.LetterID<?"
        params.append(before_id)
    query="""
        ;WITH Subtree(PMUserUID,Depth,Trail) AS (
          SELECT d.PMUserUID,CAST(0 AS int),
                 CAST(N'/' + d.PMUserUID + N'/' AS nvarchar(max))
          FROM AgentProduct.DirectoryUser d
          WHERE d.TenantID=? AND d.PMUserUID=?
            AND d.IsEnabled=1 AND d.PMStatus='ACTIVE'
          UNION ALL
          SELECT child.PMUserUID,parent.Depth+1,
                 CAST(parent.Trail+child.PMUserUID+N'/' AS nvarchar(max))
          FROM AgentProduct.DirectoryUser child JOIN Subtree parent
            ON child.ManagerPMUserUID=parent.PMUserUID
          WHERE child.TenantID=? AND child.IsEnabled=1
            AND child.PMStatus='ACTIVE' AND parent.Depth<32
            AND CHARINDEX(N'/'+child.PMUserUID+N'/',parent.Trail)=0
        )
        SELECT TOP (51) l.LetterID,l.LetterTitle,l.OwnerPMUserUID,l.IsConfidential
        FROM AgentProduct.LetterIndex l
        WHERE l.TenantID=? AND (
          l.OwnerPMUserUID=?
          OR (l.IsConfidential=0 AND EXISTS(
             SELECT 1 FROM Subtree s WHERE s.PMUserUID=l.OwnerPMUserUID))
          OR EXISTS(SELECT 1 FROM AgentProduct.LetterGrant g
             WHERE g.TenantID=l.TenantID AND g.LetterID=l.LetterID
               AND g.SubjectID=?)
        )
    """+where+"""
        ORDER BY l.LetterID DESC OPTION (MAXRECURSION 32)
    """
    cur.execute(query,*params)
    rows=cur.fetchall()
    page=rows[:limit]
    return {"letters":[{"letter_id":str(r[0]),"title":str(r[1]),
                        "owner_pm_uid":str(r[2]),"confidential":bool(r[3])}
                       for r in page],
            "returned":len(page),"has_more":len(rows)>limit,
            "next_cursor":str(page[-1][0]) if len(rows)>limit and page else None,
            "scope":"self/nonconfidential-subtree/explicit-confidential-grants",
            "content_available":False,
            "source_status":"NO_REAL_LETTERS_IMPORTED"}


def directory_meeting_access(con, principal: Principal, meeting_id: int) -> dict | None:
    """Read meeting only when the verified user has a tenant or subtree grant.

    This authority check does NOT rely on the old v1 MeetingGrant-only view.
    It is deliberately SQL-side; does not cache permissions across requests.
    """
    if type(meeting_id) is not int or meeting_id <= 0:
        return None
    role=directory_role(con,principal)
    cur=con.cursor()
    if role in ("Manager","SysAdmin"):
        cur.execute("""
            SELECT TOP (1) MeetingID,MeetingNo,MeetingTitle,MeetingStatus
            FROM AgentProduct.MeetingIndex
            WHERE TenantID=? AND MeetingID=?
        """,str(principal.tenant_id),meeting_id)
    else:
        cur.execute("""
        ;WITH Subtree(PMUserUID,Depth,Trail) AS (
          SELECT d.PMUserUID,CAST(0 AS int),
                 CAST(N'/'+d.PMUserUID+N'/' AS nvarchar(max))
          FROM AgentProduct.DirectoryUser d
          WHERE d.TenantID=? AND d.SubjectID=?
                AND d.IsEnabled=1 AND d.PMStatus='ACTIVE'
          UNION ALL
          SELECT child.PMUserUID,parent.Depth+1,
                 CAST(parent.Trail+child.PMUserUID+N'/' AS nvarchar(max))
          FROM AgentProduct.DirectoryUser child JOIN Subtree parent
            ON child.ManagerPMUserUID=parent.PMUserUID
          WHERE child.TenantID=? AND child.IsEnabled=1 AND child.PMStatus='ACTIVE'
            AND parent.Depth<32
            AND CHARINDEX(N'/'+child.PMUserUID+N'/',parent.Trail)=0
        )
        SELECT TOP (1) m.MeetingID,m.MeetingNo,m.MeetingTitle,m.MeetingStatus
        FROM AgentProduct.MeetingIndex m
        WHERE m.TenantID=? AND m.MeetingID=?
          AND EXISTS(
            SELECT 1 FROM AgentProduct.MeetingActor a
            JOIN Subtree s ON s.PMUserUID=a.PMUserUID
            WHERE a.TenantID=m.TenantID AND a.MeetingID=m.MeetingID
          )
        OPTION (MAXRECURSION 32)
        """,str(principal.tenant_id),principal.subject,
            str(principal.tenant_id),str(principal.tenant_id),meeting_id)
    r=cur.fetchone()
    return ({"meeting_id":int(r[0]),"meeting_no":str(r[1]),
             "title":str(r[2]),"status":str(r[3])} if r else None)


def directory_action_report(con, principal: Principal, *,
                            overdue_only: bool = False, limit: int = 50) -> dict:
    """Authorized action rollup or overdue rows; exact user/scope each query."""
    role=directory_role(con,principal)
    if type(limit) is not int or not 1<=limit<=50:
        raise ValueError("Invalid action report limit")
    if role=="Expert":
        cte="""
        ;WITH Subtree(PMUserUID,Depth,Trail) AS (
          SELECT d.PMUserUID,CAST(0 AS int),
                 CAST(N'/'+d.PMUserUID+N'/' AS nvarchar(max))
          FROM AgentProduct.DirectoryUser d
          WHERE d.TenantID=? AND d.SubjectID=?
            AND d.IsEnabled=1 AND d.PMStatus='ACTIVE'
          UNION ALL
          SELECT child.PMUserUID,parent.Depth+1,
                 CAST(parent.Trail+child.PMUserUID+N'/' AS nvarchar(max))
          FROM AgentProduct.DirectoryUser child JOIN Subtree parent
            ON child.ManagerPMUserUID=parent.PMUserUID
          WHERE child.TenantID=? AND child.IsEnabled=1 AND child.PMStatus='ACTIVE'
            AND parent.Depth<32
            AND CHARINDEX(N'/'+child.PMUserUID+N'/',parent.Trail)=0
        )
        """
        inputs=[str(principal.tenant_id),principal.subject,str(principal.tenant_id)]
        acl="""
        AND EXISTS(SELECT 1 FROM AgentProduct.MeetingActor ma JOIN Subtree s
          ON s.PMUserUID=ma.PMUserUID
          WHERE ma.TenantID=a.TenantID AND ma.MeetingID=a.MeetingID)
        """
    else:
        cte=""
        inputs=[]
        acl=""
    base=" FROM AgentProduct.ActionIndex a WHERE a.TenantID=? "+acl
    params=inputs+[str(principal.tenant_id)]
    cursor=con.cursor()
    if overdue_only:
        sql=cte+"""
          SELECT TOP (50) a.MeetingID,a.ActionNo,a.ActionTitle,a.OwnerUnit,
                          a.DueAtUtc,a.ProgressPercent
        """+base+"""
        AND a.IsClosed=0 AND a.ProgressPercent<100
        AND a.DueAtUtc<SYSUTCDATETIME()
        ORDER BY a.DueAtUtc,a.MeetingID,a.ActionNo
        """+(" OPTION (MAXRECURSION 32)" if role=="Expert" else "")
        cursor.execute(sql,*params)
        rows=cursor.fetchall()[:limit]
        return {"scope":"tenant" if role!="Expert" else "self-and-org-subtree",
                "alerts":[{"meeting_id":int(r[0]),"action_no":str(r[1]),
                           "title":str(r[2]),"owner_unit":str(r[3]),
                           "due_at_utc":str(r[4]),
                           "progress_percent":int(r[5])} for r in rows],
                "returned":len(rows),"max_returned":limit}
    sql=cte+"""
      SELECT COUNT_BIG(*),
       COALESCE(SUM(CASE WHEN a.IsClosed=0 AND a.ProgressPercent<100 THEN
         CAST(1 AS bigint) ELSE CAST(0 AS bigint) END),0),
       COALESCE(SUM(CASE WHEN a.IsClosed=0 AND a.ProgressPercent<100
         AND a.DueAtUtc<SYSUTCDATETIME() THEN
         CAST(1 AS bigint) ELSE CAST(0 AS bigint) END),0)
    """+base+(" OPTION (MAXRECURSION 32)" if role=="Expert" else "")
    cursor.execute(sql,*params)
    r=cursor.fetchone()
    return {"scope":"tenant" if role!="Expert" else "self-and-org-subtree",
            "actions":{"total":int(r[0]),"open":int(r[1]),"overdue":int(r[2])},
            "data_scope":"only authorized test action indexes"}


def directory_meeting_status_report(con, principal: Principal) -> dict:
    """Counts ALL meetings visible via current tenant hierarchy, not TOP(20)."""
    role=directory_role(con,principal)
    if role=="Expert":
        sql="""
        ;WITH Subtree(PMUserUID,Depth,Trail) AS (
          SELECT d.PMUserUID,CAST(0 AS int),
                 CAST(N'/'+d.PMUserUID+N'/' AS nvarchar(max))
          FROM AgentProduct.DirectoryUser d
          WHERE d.TenantID=? AND d.SubjectID=?
            AND d.IsEnabled=1 AND d.PMStatus='ACTIVE'
          UNION ALL
          SELECT child.PMUserUID,parent.Depth+1,
                 CAST(parent.Trail+child.PMUserUID+N'/' AS nvarchar(max))
          FROM AgentProduct.DirectoryUser child JOIN Subtree parent
            ON child.ManagerPMUserUID=parent.PMUserUID
          WHERE child.TenantID=? AND child.IsEnabled=1 AND child.PMStatus='ACTIVE'
            AND parent.Depth<32
            AND CHARINDEX(N'/'+child.PMUserUID+N'/',parent.Trail)=0
        )
        SELECT m.MeetingStatus,COUNT_BIG(*) FROM AgentProduct.MeetingIndex m
        WHERE m.TenantID=?
        AND EXISTS(SELECT 1 FROM AgentProduct.MeetingActor a
          JOIN Subtree s ON s.PMUserUID=a.PMUserUID
          WHERE a.TenantID=m.TenantID AND a.MeetingID=m.MeetingID)
        GROUP BY m.MeetingStatus ORDER BY m.MeetingStatus
        OPTION (MAXRECURSION 32)
        """
        params=(str(principal.tenant_id),principal.subject,
                str(principal.tenant_id),str(principal.tenant_id))
    else:
        sql="""
          SELECT m.MeetingStatus,COUNT_BIG(*)
          FROM AgentProduct.MeetingIndex m
          WHERE m.TenantID=?
          GROUP BY m.MeetingStatus ORDER BY m.MeetingStatus
        """
        params=(str(principal.tenant_id),)
    cur=con.cursor()
    cur.execute(sql,*params)
    breakdown=[{"status":str(r[0]),"count":int(r[1])} for r in cur.fetchall()]
    return {"total_visible_meetings":sum(r["count"] for r in breakdown),
            "status_breakdown":breakdown,
            "scope":"tenant" if role!="Expert" else "self-and-org-subtree"}
