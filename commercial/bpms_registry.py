"""GodAdmin-managed, read-only BPMS adapters; no PM data is mirrored here.

External systems expose the AVAN REST v1 contract through their own adapter.
The connector authenticates as a dedicated read-only integration identity.
"""
from __future__ import annotations

from datetime import date,datetime
import hashlib
from ipaddress import ip_address
from typing import Literal
from urllib.parse import urlsplit
import re
import secrets
import json

import httpx
from pydantic import BaseModel,ConfigDict,Field,ValidationError,model_validator

from . import setup_console as setup

MAX_SOURCES=12
MAX_BODY=512*1024


class BPMSUnavailable(Exception):pass


class SourceConfig(BaseModel):
    model_config=ConfigDict(extra="forbid")
    id:str|None=Field(None,pattern=r"^[0-9a-f]{24}$")
    name:str=Field(min_length=2,max_length=100)
    kind:Literal["avan-rest-v1"]="avan-rest-v1"
    engine:Literal["camunda","appian","uipath","servicenow","other"]="other"
    base_url:str=Field(min_length=12,max_length=255)
    bearer_token:str=Field(default="",max_length=8192)
    enabled:bool=True

    @model_validator(mode="after")
    def validate_source(self):
        parsed=urlsplit(self.base_url)
        host=(parsed.hostname or "").lower()
        if (parsed.scheme!="https" or not host or parsed.port not in (None,443,8443)
            or parsed.username or parsed.password or parsed.query or parsed.fragment
            or not re.fullmatch(r"(?:/[A-Za-z0-9_-]+){0,4}/?",parsed.path)
            or host in ("localhost","host.docker.internal") or host.endswith(".localhost")):
            raise ValueError("Read-only adapter requires an HTTPS endpoint without credentials or query")
        try:address=ip_address(host)
        except ValueError:address=None
        if address and (address.is_loopback or address.is_link_local or
                        address.is_multicast or address.is_unspecified):
            raise ValueError("Local or link-local adapter addresses are not supported")
        if self.base_url.endswith("/"):
            self.base_url=self.base_url.rstrip("/")
        if any(x in self.bearer_token for x in ("\r","\n","\x00")):
            raise ValueError("Invalid integration token")
        return self


class BIFilter(BaseModel):
    model_config=ConfigDict(extra="forbid")
    period:Literal["all","this_month","last_month","last_30_days","last_7_days"]="last_30_days"
    status:Literal["all","DRAFT","TO_DO","COMPLETED","CANCELLED","PAUSED"]="all"
    process_uid:str|None=Field(None,pattern=r"^[A-Za-z0-9_.:-]{1,80}$")
    start:date|None=None
    end:date|None=None
    offset:int=Field(0,ge=0,le=20000)
    limit:int=Field(30,ge=1,le=100)

    @model_validator(mode="after")
    def dates(self):
        if bool(self.start)!=bool(self.end) or (self.start and self.end<=self.start):
            raise ValueError("Start and exclusive end must both be present and ordered")
        return self


class BIRequest(BIFilter):
    source_id:str=Field(pattern=r"^[0-9a-f]{24}$")


class Metrics(BaseModel):
    model_config=ConfigDict(extra="forbid")
    cases:int=Field(ge=0,le=1000000000)
    open_cases:int=Field(ge=0,le=1000000000)
    completed_cases:int=Field(ge=0,le=1000000000)
    open_tasks:int=Field(ge=0,le=1000000000)
    overdue_tasks:int=Field(ge=0,le=1000000000)


class ProcessRow(BaseModel):
    model_config=ConfigDict(extra="forbid")
    process_uid:str=Field(min_length=1,max_length=80)
    title:str=Field(min_length=1,max_length=200)
    total:int=Field(ge=0,le=1000000000)
    open:int=Field(ge=0,le=1000000000)
    completed:int=Field(ge=0,le=1000000000)
    overdue_tasks:int=Field(ge=0,le=1000000000)


class CaseRow(BaseModel):
    model_config=ConfigDict(extra="forbid")
    case_uid:str=Field(min_length=1,max_length=128)
    case_number:str=Field(min_length=1,max_length=80)
    process_uid:str=Field(min_length=1,max_length=80)
    process_title:str=Field(min_length=1,max_length=200)
    status:str=Field(min_length=1,max_length=40)
    created_at:datetime|None=None
    finished_at:datetime|None=None


class BIResponse(BaseModel):
    model_config=ConfigDict(extra="forbid")
    schema_version:Literal[1]
    tenant_id:str=Field(min_length=1,max_length=80)
    as_of_utc:datetime
    coverage_complete:bool
    metrics:Metrics
    processes:list[ProcessRow]=Field(max_length=200)
    rows:list[CaseRow]=Field(max_length=100)
    statuses:dict[str,int]=Field(default_factory=dict,max_length=20)
    has_more:bool=False


class DirectoryUser(BaseModel):
    model_config=ConfigDict(extra="forbid")
    external_user_id:str=Field(min_length=1,max_length=128)
    username:str=Field(min_length=1,max_length=120)
    display_name:str=Field(min_length=1,max_length=240)
    email:str|None=Field(default=None,max_length=240)
    status:str=Field(default="ACTIVE",min_length=1,max_length=32)
    active:bool
    unit:str=Field(default="",max_length=160)


class DirectoryResponse(BaseModel):
    model_config=ConfigDict(extra="forbid")
    schema_version:Literal[1]
    tenant_id:str=Field(min_length=1,max_length=80)
    as_of_utc:datetime
    users:list[DirectoryUser]=Field(max_length=5000)


def _all():
    return list((setup.get_setting("bpms_connections") or {}).get("sources",[]))


def sources():
    return [{k:v for k,v in row.items() if k!="bearer_token"}
            | {"engine":row.get("engine","other"),"has_token":bool(row.get("bearer_token"))}
            for row in _all()]


def signature():
    return hashlib.sha256(json.dumps(_all(),sort_keys=True).encode()).hexdigest()


def _source(identifier:str):
    return next((s for s in _all() if s["id"]==identifier and s.get("enabled")),None)


def _candidate(candidate:SourceConfig):
    stored=_all()
    previous=next((s for s in stored if s["id"]==candidate.id),None) if candidate.id else None
    if candidate.id and not previous:raise BPMSUnavailable("Connection does not exist")
    if not previous and len(stored)>=MAX_SOURCES:raise BPMSUnavailable("Connection limit reached")
    if (previous and candidate.base_url!=previous.get("base_url") and
        not candidate.bearer_token):
        raise BPMSUnavailable("برای تغییر نشانی آداپتر، توکن خواندنی جدید را وارد کنید.")
    data=candidate.model_dump()
    data["id"]=candidate.id or secrets.token_hex(12)
    data["name"]=candidate.name.strip()
    data["bearer_token"]=candidate.bearer_token or (previous or {}).get("bearer_token","")
    if len(data["bearer_token"])<16:raise BPMSUnavailable("Read-only integration token is required")
    return stored,data


def check(candidate:SourceConfig):
    _,data=_candidate(candidate)
    return identity(data)

def check_saved(identifier:str):
    source=next((s for s in _all() if s["id"]==identifier),None)
    if not source:raise BPMSUnavailable("Connection does not exist")
    return identity(source)


def copy_source(identifier:str,name:str|None=None):
    stored=_all()
    source=next((s for s in stored if s["id"]==identifier),None)
    if not source:raise BPMSUnavailable("Connection does not exist")
    if len(stored)>=MAX_SOURCES:raise BPMSUnavailable("Connection limit reached")
    copied={**source,
            "id":secrets.token_hex(12),
            "name":(name or (source["name"]+" - کپی")).strip(),
            "enabled":False}
    if not 2<=len(copied["name"])<=100:
        raise BPMSUnavailable("Connection name is invalid")
    setup.put_setting("bpms_connections",{"sources":stored+[copied]})
    return {"id":copied["id"],"saved":True,"copied_from":identifier,"enabled":False}


def save(candidate:SourceConfig):
    stored,data=_candidate(candidate)
    # Test the exact candidate before it can become an active source.
    if data["enabled"]:identity(data)
    setup.put_setting("bpms_connections",{"sources":[s for s in stored if s["id"]!=data["id"]]+[data]})
    return {"id":data["id"],"saved":True}


def delete(identifier:str):
    stored=_all()
    filtered=[s for s in stored if s["id"]!=identifier]
    if len(filtered)==len(stored):raise BPMSUnavailable("Connection does not exist")
    setup.put_setting("bpms_connections",{"sources":filtered})
    return {"deleted":True}


def set_enabled(identifier:str,enabled:bool):
    """Change one source without sending its saved integration token to the UI."""
    stored=_all()
    source=next((s for s in stored if s["id"]==identifier),None)
    if not source:raise BPMSUnavailable("Connection does not exist")
    if bool(source.get("enabled"))==enabled:
        return {"id":identifier,"enabled":enabled}
    if enabled:identity(source)
    updated=[{**s,"enabled":enabled} if s["id"]==identifier else s for s in stored]
    setup.put_setting("bpms_connections",{"sources":updated})
    return {"id":identifier,"enabled":enabled}


def _request(source,path,params=None,max_body=MAX_BODY):
    token=source["bearer_token"]
    try:
        with httpx.Client(timeout=8,follow_redirects=False,trust_env=False,verify=True) as client:
            with client.stream("GET",source["base_url"]+path,
                params=params,headers={"Authorization":"Bearer "+token,
                                       "Accept":"application/json"}) as response:
                if (response.status_code!=200 or
                    "application/json" not in response.headers.get("content-type","").lower()):
                    raise BPMSUnavailable("BPMS adapter rejected the read-only request")
                body=bytearray()
                for chunk in response.iter_bytes():
                    body.extend(chunk)
                    if len(body)>max_body:
                        raise BPMSUnavailable("BPMS adapter response is too large")
        return json.loads(body)
    except (httpx.HTTPError,ValueError) as exc:
        raise BPMSUnavailable("BPMS adapter is unavailable or returned invalid JSON") from exc


def identity(source):
    company=setup.get_setting("company") or {}
    if not company.get("tenant_id"):
        raise BPMSUnavailable("Company must be configured first")
    body=_request(source,"/avan/v1/identity")
    if (not isinstance(body,dict) or body.get("schema_version")!=1 or
        body.get("tenant_id")!=company["tenant_id"]):
        raise BPMSUnavailable("BPMS adapter tenant or contract does not match")
    return {"connected":True,"tenant_id":company["tenant_id"],"schema_version":1}


def directory_users(identifier:str)->list[dict]:
    source=_source(identifier)
    if not source:raise BPMSUnavailable("Connection is disabled or missing")
    company=setup.get_setting("company") or {}
    try:
        payload=DirectoryResponse.model_validate(
            _request(source,"/avan/v1/directory/users",max_body=2*1024*1024)
        )
    except ValidationError as exc:
        raise BPMSUnavailable("BPMS adapter directory does not match the AVAN v1 contract") from exc
    if payload.tenant_id!=company.get("tenant_id"):
        raise BPMSUnavailable("BPMS adapter directory belongs to another organization")
    seen=set();result=[]
    for user in payload.users:
        if user.external_user_id in seen:
            raise BPMSUnavailable("BPMS adapter directory contains duplicate user IDs")
        seen.add(user.external_user_id)
        result.append(user.model_dump(mode="json"))
    return result


def report(args:BIRequest):
    source=_source(args.source_id)
    if not source:raise BPMSUnavailable("Connection is disabled or missing")
    company=setup.get_setting("company") or {}
    data=args.model_dump(mode="json",exclude={"source_id"},exclude_none=True)
    try:
        payload=BIResponse.model_validate(_request(source,"/avan/v1/bi/processes",data))
    except ValidationError as exc:
        raise BPMSUnavailable("BPMS adapter report does not match the AVAN v1 contract") from exc
    if payload.tenant_id!=company.get("tenant_id") or len(payload.rows)>args.limit:
        raise BPMSUnavailable("BPMS adapter report is outside the allowed organization or page")
    result=payload.model_dump(mode="json")
    result.update({"source_id":source["id"],"source_name":source["name"],"kind":source["kind"]})
    return result
