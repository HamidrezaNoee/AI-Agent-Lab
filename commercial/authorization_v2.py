"""Authorization v2: application roles + participant and reporting-tree meeting scope.

GodAdmin is intentionally NOT a tenant-content super-reader. It is the product
manufacturer/operator role. SysAdmin is the customer's technical/admin role.
Manager gets hierarchy scope; Expert gets direct involvement only.
"""
from .security import Principal
from .sql_store import AccessDenied

ROLES = frozenset({"GodAdmin", "SysAdmin", "Manager", "Expert"})


def user_context(con, principal: Principal) -> dict:
    cur = con.cursor()
    cur.execute("""
      SELECT m.RoleCode,u.DisplayName,u.ProcessMakerUserUID,u.ProcessMakerUsername,u.IsEnabled
      FROM AgentProduct.Membership m
      LEFT JOIN AgentProduct.UserDirectory u
        ON u.TenantID=m.TenantID AND u.SubjectID=m.SubjectID
      WHERE m.TenantID=? AND m.SubjectID=? AND m.IsEnabled=1
    """, str(principal.tenant_id), principal.subject)
    row = cur.fetchone()
    if not row or row[0] not in ROLES:
        raise AccessDenied("Active application membership is required")
    return {"role": row[0], "display_name": row[1] or principal.subject,
            "processmaker_user_uid": row[2], "processmaker_username": row[3],
            "directory_enabled": bool(row[4]) if row[4] is not None else False}


def can_administer_system(role: str) -> bool:
    return role in {"SysAdmin"}


def can_manage_manufacturer(role: str) -> bool:
    return role == "GodAdmin"


def can_view_all_tenant_meetings(role: str) -> bool:
    return role == "SysAdmin"


def visible_meetings_v2(con, principal: Principal, *, before_id=None, limit=20) -> dict:
    if not isinstance(limit, int) or not 1 <= limit <= 50:
        raise ValueError("Invalid page size")
    if before_id is not None and (not isinstance(before_id, int) or before_id <= 0):
        raise ValueError("Invalid meeting cursor")
    ctx = user_context(con, principal)
    # GodAdmin manages product/license. It does not silently gain confidential
    # customer meeting access. If a customer wants GodAdmin to see a meeting,
    # grant it explicitly just like any other named subject.
    sql = """
      SELECT TOP (51) m.MeetingID,m.MeetingNo,m.MeetingTitle,m.MeetingStatus
      FROM AgentProduct.MeetingIndex m
      WHERE m.TenantID=?
    """
    params = [str(principal.tenant_id)]
    if before_id is not None:
        sql += " AND m.MeetingID<?"
        params.append(before_id)
    if ctx["role"] == "SysAdmin":
        pass
    elif ctx["role"] == "GodAdmin":
        sql += """ AND EXISTS(
          SELECT 1 FROM AgentProduct.MeetingGrant g
          WHERE g.TenantID=m.TenantID AND g.MeetingID=m.MeetingID AND g.SubjectID=?
        )"""
        params.append(principal.subject)
    else:
        sql += """ AND EXISTS(
          SELECT 1 FROM AgentProduct.fn_can_view_meeting(?,?,m.MeetingID) x
          WHERE x.Allowed=1
        )"""
        params.extend([str(principal.tenant_id), principal.subject])
    sql += " ORDER BY m.MeetingID DESC"
    cur = con.cursor();cur.execute(sql,*params);rows=cur.fetchall()
    more=len(rows)>limit;page=rows[:limit]
    result=[{"meeting_id":int(r[0]),"meeting_no":r[1],"title":r[2],"status":r[3]} for r in page]
    return {"role":ctx["role"],"meetings":result,"returned":len(result),"has_more":more,
            "next_cursor":result[-1]["meeting_id"] if more and result else None}


def hierarchy_snapshot(con, principal: Principal) -> dict:
    ctx=user_context(con,principal)
    cur=con.cursor()
    cur.execute("""
      SELECT n.NodeID,n.ParentNodeID,n.NodeCode,n.NodeName,n.NodeType,
             u.SubjectID,u.DisplayName,u.UserKind
      FROM AgentProduct.OrganizationNode n
      LEFT JOIN AgentProduct.UserOrganizationAssignment a
        ON a.TenantID=n.TenantID AND a.NodeID=n.NodeID AND a.EffectiveToUtc IS NULL
      LEFT JOIN AgentProduct.UserDirectory u
        ON u.TenantID=a.TenantID AND u.SubjectID=a.SubjectID AND u.IsEnabled=1
      WHERE n.TenantID=? AND n.IsEnabled=1 ORDER BY n.NodeID,u.DisplayName
    """,str(principal.tenant_id))
    rows=cur.fetchall()
    # Experts only need their own node context. Managers may inspect their
    # reporting subtree; SysAdmin may configure the full tree.
    allowed_nodes=None
    if ctx["role"] in {"Expert","Manager"}:
        cur.execute("""
          SELECT DISTINCT d.NodeID
          FROM AgentProduct.UserOrganizationAssignment me
          CROSS APPLY AgentProduct.fn_descendant_nodes(?,me.NodeID) d
          WHERE me.TenantID=? AND me.SubjectID=? AND me.EffectiveToUtc IS NULL
        """,str(principal.tenant_id),str(principal.tenant_id),principal.subject)
        allowed_nodes={int(x[0]) for x in cur.fetchall()}
        if ctx["role"]=="Expert":
            cur.execute("""SELECT NodeID FROM AgentProduct.UserOrganizationAssignment
              WHERE TenantID=? AND SubjectID=? AND EffectiveToUtc IS NULL""",
              str(principal.tenant_id),principal.subject)
            allowed_nodes={int(x[0]) for x in cur.fetchall()}
    if ctx["role"]=="GodAdmin":
        allowed_nodes=set()  # manufacturer role has no customer-org browsing by default
    items=[]
    for r in rows:
        if allowed_nodes is not None and int(r[0]) not in allowed_nodes: continue
        items.append({"node_id":int(r[0]),"parent_node_id":int(r[1]) if r[1] else None,
          "code":r[2],"name":r[3],"type":r[4],"subject":r[5],
          "display_name":r[6],"user_kind":r[7]})
    return {"role":ctx["role"],"nodes":items}
