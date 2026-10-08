"""Verified Agent identity mappings in its dedicated SQL Server; PM data is read-only."""

from contextlib import contextmanager
from . import agent_storage

EMPTY = {"tenant_id": None, "company_name": None, "users": []}


def read():
    with agent_storage.transaction() as tx:
        return tx.get("organization_access", dict(EMPTY))


@contextmanager
def edit():
    with agent_storage.transaction() as tx:
        data = tx.get(
            "organization_access",
            {"tenant_id": None, "company_name": None, "users": []},
            lock=True,
        )
        yield data
        tx.put("organization_access", data)
        tx.audit(
            data.get("tenant_id") or "", "GodAdmin", "ORGANIZATION_ACCESS_UPDATED", {}
        )


def ensure_godadmin_user(*,subject,tenant_id,company_name,username=None,name=None):
    """Idempotently project the bound platform GodAdmin into AVAN authorization.

    GodAdmin remains a distinct platform role. A null module_permissions value
    intentionally means "all modules allowed by the organization license".
    """
    if not subject or not tenant_id:
        return None
    with agent_storage.transaction() as tx:
        data=tx.get(
            "organization_access",
            {"tenant_id":str(tenant_id),"company_name":company_name,"users":[]},
            lock=True,
        )
        if data.get("tenant_id") not in (None,str(tenant_id)):
            return None
        data["tenant_id"]=str(tenant_id)
        if company_name:
            data["company_name"]=company_name
        users=data.setdefault("users",[])
        user=next((u for u in users if u.get("subject")==subject),None)
        if user is None:
            user={
                "subject":subject,
                "username":username or "godadmin",
                "email":None,
                "name":name or "GodAdmin",
                "role":"GodAdmin",
                "department_name":"مدیریت سامانه",
                "manager_subject":None,
                "module_permissions":None,
                "enabled":True,
            }
            users.append(user)
        else:
            user["role"]="GodAdmin"
            user["enabled"]=True
            user["module_permissions"]=None
            user.setdefault("department_name","مدیریت سامانه")
            if username:user["username"]=username
            if name:user["name"]=name
        tx.put("organization_access",data)
        tx.audit(str(tenant_id),subject,"GODADMIN_ACCESS_ENSURED",{})
        return dict(user)


def seats(tenant_id):
    data = read()
    if data["tenant_id"] != tenant_id:
        return 0
    # AVAN licensing counts active AVAN accounts, independently of BPMS bindings.
    return sum(u.get("enabled") is True for u in data["users"])


def effective_modules(user,licensed_modules):
    """AVAN user grants are independent from BPMS bindings and bounded by license.

    Legacy users without an explicit grant retain licensed modules until edited.
    New/edited users store an explicit module_permissions list.
    """
    licensed={int(x) for x in licensed_modules if int(x) in (1,2,3,4)}
    raw=user.get("module_permissions")
    if raw is None:
        return frozenset(licensed)
    if not isinstance(raw,list):
        return frozenset()
    granted={int(x) for x in raw if isinstance(x,int) and x in (1,2,3,4)}
    return frozenset(licensed & granted)
