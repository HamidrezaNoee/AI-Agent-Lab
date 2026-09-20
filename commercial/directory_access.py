"""Hierarchy-aware meeting visibility for the isolated commercial lab.

Requires the verified OIDC subject to map to an ACTIVE, ENABLED PM directory
entry. Hierarchy is explicitly configured in DirectoryUser, not inferred from
ProcessMaker groups or names. GodAdmin alone NEVER grants tenant content access.
Regular experts see their own AND their subtree's involvement; Manager/SysAdmin
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
            WHERE child.TenantID=? AND parent.Depth<32
              AND CHARINDEX(N'/' + child.PMUserUID + N'/',parent.Trail)=0
        )
        SELECT TOP (51) m.MeetingID,m.MeetingNo,m.MeetingTitle,m.MeetingStatus
        FROM AgentProduct.MeetingIndex m
        WHERE """+where+"""
          AND (
           EXISTS(SELECT 1 FROM AgentProduct.MeetingGrant g
                  WHERE g.TenantID=m.TenantID AND g.MeetingID=m.MeetingID AND g.SubjectID=?)
           OR EXISTS(
             SELECT 1 FROM AgentProduct.MeetingActor a JOIN Subtree s
               ON s.PMUserUID=a.PMUserUID
             WHERE a.TenantID=m.TenantID AND a.MeetingID=m.MeetingID
           )
          )
        ORDER BY m.MeetingID DESC
        OPTION (MAXRECURSION 32)
        """
        params=[str(principal.tenant_id),uid,str(principal.tenant_id),*params,principal.subject]
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
