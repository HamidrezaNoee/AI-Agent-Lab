"""Bounded analytical tools over a freshly authorized snapshot. No SQL execution."""
from __future__ import annotations
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from typing import Literal
import re
from pydantic import BaseModel, ConfigDict, Field


def normal(text):
    return str(text or '').translate(str.maketrans('يكى۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩','یکی01234567890123456789')).replace('\u200c',' ').strip().casefold()


def instant(value):
    if not value:return None
    try:
        value=datetime.fromisoformat(str(value).replace('Z','+00:00')) if not isinstance(value,datetime) else value
        return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)
    except (ValueError,TypeError):return None


class Arguments(BaseModel):
    model_config=ConfigDict(extra='forbid')


class ActionQuery(Arguments):
    meeting_no: str | None = Field(None,max_length=80)
    text: str | None = Field(None,max_length=200)
    unit: str | None = Field(None,max_length=120)
    owner: str | None = Field(None,max_length=120)
    status: Literal['all','open','closed','overdue','due_soon']='all'
    period: Literal['all','this_month','last_month','last_30_days','last_7_days']='all'
    date_field: Literal['meeting','due']='meeting'
    start: str | None = Field(None,max_length=40,description='Inclusive canonical ISO timestamp with timezone; prefer named periods, which follow the AVAN global calendar setting.')
    end: str | None = Field(None,max_length=40,description='Exclusive Gregorian ISO timestamp with timezone.')
    group_by: Literal['none','unit','owner','meeting','month']='none'
    limit: int = Field(15,ge=1,le=30)
    offset: int = Field(0,ge=0,le=20000)


class MeetingQuery(Arguments):
    match: Literal['ranked','substring']='ranked'
    text: str = Field('',max_length=200)
    meeting_no: str | None = Field(None,max_length=80)
    meeting_held: Literal['all','Held','NotHeld','unknown'] = 'all'
    period: Literal['all','this_month','last_month','last_30_days','last_7_days']='all'
    limit: int = Field(10,ge=1,le=20)
    offset: int = Field(0,ge=0,le=2000)


class MonitorQuery(Arguments):
    due_days: int = Field(3,ge=1,le=30)
    stale_days: int = Field(7,ge=1,le=90)


def calendar_mode():
    from .setup_console import get_setting
    value=str((get_setting('ui') or {}).get('calendar','jalali')).lower()
    return value if value in ('jalali','gregorian') else 'jalali'


def period_bounds(period,now):
    from zoneinfo import ZoneInfo
    import os
    tz=ZoneInfo(os.getenv('AVAN_DATA_TIMEZONE','Asia/Tehran'))
    if period=='all':return None,None
    if period.startswith('last_') and period.endswith('_days'):
        return now-timedelta(days=int(period.split('_')[1])),now
    local=now.astimezone(tz)
    mode=calendar_mode()
    if mode=='gregorian':
        year,month=local.year,local.month
        start=date(year,month,1)
        end=now
        if period=='last_month':
            end=datetime.combine(start,datetime.min.time(),tzinfo=tz).astimezone(timezone.utc)
            year,month=(year-1,12) if month==1 else (year,month-1)
            start=date(year,month,1)
    else:
        import jdatetime
        jalali=jdatetime.date.fromgregorian(date=local.date())
        year,month=jalali.year,jalali.month
        start=jdatetime.date(year,month,1).togregorian()
        end=now
        if period=='last_month':
            end=datetime.combine(start,datetime.min.time(),tzinfo=tz).astimezone(timezone.utc)
            year,month=(year-1,12) if month==1 else (year,month-1)
            start=jdatetime.date(year,month,1).togregorian()
    return datetime.combine(start,datetime.min.time(),tzinfo=tz).astimezone(timezone.utc),end


def source(m,a=None):
    key=f"M:{m['meeting_id']}"
    if a is not None:key+=f":A:{a.get('action_id',a['action_no'])}"
    return {'id':key,'meeting_id':m['meeting_id'],'meeting_no':m['meeting_no'],
            'action_no':a['action_no'] if a else None,'title':m['title']}


def action_record(m,a,now):
    due=instant(a.get('due_at_utc'))
    progress=a.get('progress_percent')
    return {'source':source(m,a),'description':str(a.get('description') or '')[:1800],
            'owner_uid':a.get('owner_uid'),'owner_name':a.get('owner_name'),
            'unit':a.get('owner_unit'),'owner_position':a.get('owner_position'),'status':a.get('status'),
            'is_closed':bool(a.get('is_closed')),'progress_percent':progress,
            'due_at_utc':due.isoformat() if due else None,
            'overdue_days':round((now-due).total_seconds()/86400,1) if due and due<now and not a.get('is_closed') else 0}


class MeetingTools:
    def __init__(self,meetings,*,now=None,complete=True,modules=(1,2,3,4),observations=None):
        if len(meetings)>2000 or sum(len(m.get('actions',[])) for m in meetings)>20000:
            raise ValueError('Snapshot bounds exceeded')
        self.meetings=meetings
        self.now=now or datetime.now(timezone.utc)
        self.complete=complete
        self.calendar=calendar_mode()
        self.modules=set(modules)
        self.observations=observations or {}
        self.evidence={}
        self.trace=[]

    def definitions(self):
        calendar_name='Jalali' if self.calendar=='jalali' else 'Gregorian'
        specs=[('search_meetings',f'Search authorized meeting titles, discussion and parking-lot text. Default ranked mode matches all normalized query tokens in any order and ranks lexical relevance, including action descriptions. Use match=substring for exact phrases. This is lexical, not semantic search. Named month periods use {calendar_name} months.',MeetingQuery,1),
               ('analyze_actions','Filter and calculate action totals, progress, delays and grouped unit/person/meeting/month performance. Counts cover ALL matching snapshot rows, even if displayed rows/groups are paginated. Missing dates/progress are explicit.',ActionQuery,3),
               ('monitor_actions','Detect overdue, approaching due dates, missing deadlines/owners, unclosed 100% submissions, and progress stalls observed by AVAN. Returns risk signals, not proven business causes.',MonitorQuery,4)]
        return [{'type':'function','name':name,'description':description,'parameters':cls.model_json_schema(),'strict':False}
                for name,description,cls,module in specs if module in self.modules]

    def execute(self,name,raw):
        specs={'search_meetings':(MeetingQuery,1,self.search),
               'analyze_actions':(ActionQuery,3,self.actions),
               'monitor_actions':(MonitorQuery,4,self.monitor)}
        if name not in specs:raise ValueError('Unknown tool')
        cls,module,method=specs[name]
        if module not in self.modules:raise PermissionError('Module not licensed')
        args=cls.model_validate(raw)
        data=method(args)
        key=f"T:{len(self.trace)+1}"
        result={'source_id':key,'as_of_utc':self.now.isoformat(),'coverage_complete':self.complete,**data}
        self.evidence[key]={'id':key,'title':name,'filters':args.model_dump(),'result':result}
        def register(value):
            if isinstance(value,dict):
                ref=value.get('source')
                if isinstance(ref,dict) and 'id' in ref:self.evidence[ref['id']]=ref
                for v in value.values():register(v)
            elif isinstance(value,list):
                for v in value:register(v)
        register(result)
        self.trace.append({'tool':name,'source_id':key,'filters':args.model_dump()})
        return result

    def search(self,q):
        start,end=period_bounds(q.period,self.now)
        found=[]
        for m in self.meetings:
            if q.meeting_no and normal(q.meeting_no)!=normal(m['meeting_no']):continue
            if q.meeting_held != 'all' and (m.get('meeting_held') or 'unknown') != q.meeting_held:continue
            if q.match=='substring' and q.text and normal(q.text) not in normal(' '.join(str(m.get(k) or '') for k in ('title','discussion','parking_lot','not_held_reason'))):continue
            date=instant(m.get('meeting_date_utc'))
            if start and (not date or not start<=date<=end):continue
            found.append(m)
        if q.text and q.match=='ranked':
            from .retrieval import ranked_indices
            documents=[' '.join([str(m.get('title') or '')]*3 + [str(m.get(k) or '') for k in ('discussion','parking_lot','not_held_reason')] + [str(a.get('description') or '') for a in m.get('actions',[])]) for m in found]
            found=[found[i] for i in ranked_indices(q.text,documents)]
        rows=[]
        for m in found[q.offset:q.offset+q.limit]:
            rows.append({'source':source(m),'title':m['title'],'meeting_date_utc':m.get('meeting_date_utc'),
                         'meeting_status':m.get('meeting_status'),
                         'meeting_held':m.get('meeting_held'),
                         'not_held_reason':str(m.get('not_held_reason') or '')[:1000],
                         'attendance':m.get('attendance',[])[:100],
                         'attendance_truncated':len(m.get('attendance',[]))>100,
                         'discussion':str(m.get('discussion') or '')[:2500],
                         'parking_lot':str(m.get('parking_lot') or '')[:1000],
                         'text_truncated':len(str(m.get('discussion') or ''))>2500 or len(str(m.get('parking_lot') or ''))>1000 or len(str(m.get('not_held_reason') or ''))>1000,
                         'action_total':len(m.get('actions',[])),
                         'open_actions':sum(not a.get('is_closed') for a in m.get('actions',[])),
                         'actions':[action_record(m,a,self.now) for a in m.get('actions',[])[:12]],
                         'actions_truncated':len(m.get('actions',[]))>12})
        return {'retrieval':q.match,'total':len(found),'rows':rows,'has_more':q.offset+len(rows)<len(found),
                'next_offset':q.offset+len(rows),'period_start':start.isoformat() if start else None,
                'period_end':end.isoformat() if end else None}

    def actions(self,q):
        start,end=period_bounds(q.period,self.now)
        for raw in (q.start,q.end):
            if raw is not None and (instant(raw) is None or datetime.fromisoformat(raw.replace('Z','+00:00')).tzinfo is None):
                raise ValueError('Dates require valid ISO timezone')
        start=instant(q.start) if q.start else start
        end=instant(q.end) if q.end else end
        if start and end and start>=end:raise ValueError('Invalid date range')
        pairs=[]
        excluded_dates=0
        for m in self.meetings:
            if q.meeting_no and normal(q.meeting_no)!=normal(m['meeting_no']):continue
            for a in m.get('actions',[]):
                if q.text and normal(q.text) not in normal(a.get('description')):continue
                if q.unit and normal(q.unit)!=normal(a.get('owner_unit')):continue
                if q.owner and normal(q.owner) not in {normal(a.get('owner_uid')),normal(a.get('owner_name'))}:continue
                due=instant(a.get('due_at_utc'))
                d=due if q.date_field=='due' else instant(m.get('meeting_date_utc'))
                if start or end:
                    if d is None:excluded_dates+=1;continue
                    if start and d<start or end and d>=end:continue
                opened=not a.get('is_closed')
                if q.status=='open' and not opened:continue
                if q.status=='closed' and opened:continue
                if q.status=='overdue' and not (opened and due and due<self.now):continue
                if q.status=='due_soon' and not (opened and due and self.now<=due<=self.now+timedelta(days=3)):continue
                pairs.append((m,a))
        def metrics(rows):
            values=[float(a['progress_percent']) for _,a in rows if a.get('progress_percent') is not None]
            closed=sum(bool(a.get('is_closed')) for _,a in rows)
            return {'total':len(rows),'closed':closed,'open':len(rows)-closed,
                    'overdue':sum(not a.get('is_closed') and instant(a.get('due_at_utc')) is not None and instant(a['due_at_utc'])<self.now for _,a in rows),
                    'missing_due':sum(not instant(a.get('due_at_utc')) for _,a in rows),
                    'missing_progress':len(rows)-len(values),
                    'average_progress':round(sum(values)/len(values),1) if values else None,
                    'closure_rate_percent':round(100*closed/len(rows),1) if rows else None}
        groups=defaultdict(list)
        for m,a in pairs:
            if q.group_by=='unit':key=(a.get('owner_unit') or 'واحد ثبت نشده',)
            elif q.group_by=='owner':key=(a.get('owner_uid') or 'unknown',a.get('owner_name') or 'نامشخص')
            elif q.group_by=='meeting':key=(m['meeting_id'],m['meeting_no'])
            elif q.group_by=='month':
                d=instant(a.get('due_at_utc') if q.date_field=='due' else m.get('meeting_date_utc'))
                if d:
                    from zoneinfo import ZoneInfo
                    import os
                    local_date=d.astimezone(ZoneInfo(os.getenv('AVAN_DATA_TIMEZONE','Asia/Tehran'))).date()
                    if self.calendar=='jalali':
                        import jdatetime
                        j=jdatetime.date.fromgregorian(date=local_date)
                        key=(f'{j.year:04d}/{j.month:02d}',)
                    else:
                        key=(local_date.strftime('%Y/%m'),)
                else:key=('تاریخ نامشخص',)
            else:continue
            groups[key].append((m,a))
        grouped=[{'group':list(k),**metrics(v),'source':source(*v[0])} for k,v in groups.items()]
        grouped.sort(key=lambda x:(-x['overdue'],-x['open'],str(x['group'])))
        pairs.sort(key=lambda p:(bool(p[1].get('is_closed')),instant(p[1].get('due_at_utc')) or datetime.max.replace(tzinfo=timezone.utc)))
        return {'metrics':metrics(pairs),'excluded_missing_date':excluded_dates,
                'groups':grouped[q.offset:q.offset+q.limit], 'group_count':len(grouped),
                'rows':[action_record(m,a,self.now) for m,a in pairs[q.offset:q.offset+q.limit]] if q.group_by=='none' else [],
                'has_more':q.offset+q.limit<(len(grouped) if q.group_by!='none' else len(pairs)),
                'next_offset':q.offset+q.limit,'period_start':start.isoformat() if start else None,
                'period_end':end.isoformat() if end else None,
                'definition':'Closure is workflow ClosedAt/Closed, not progress=100 or owner Completed. Unit and owner totals describe authorized records only; no quality/causal conclusions.'}

    def monitor(self,q):
        alerts=[]
        def add(kind,severity,m,a,reason):
            alerts.append({'kind':kind,'severity':severity,'reason':reason,**action_record(m,a,self.now)})
        for m in self.meetings:
            for a in m.get('actions',[]):
                if a.get('is_closed'):continue
                due=instant(a.get('due_at_utc'))
                if due and due<self.now:add('overdue','high',m,a,'موعد گذشته و اقدام هنوز در گردش کار بسته نشده است.')
                elif due and due<=self.now+timedelta(days=q.due_days):add('due_soon','medium',m,a,'موعد انجام نزدیک است.')
                elif due is None:add('missing_due','medium',m,a,'موعد معتبر ثبت نشده است.')
                if not a.get('owner_uid'):add('missing_owner','high',m,a,'مسئول مشخص نشده است.')
                if a.get('progress_percent')==100:add('awaiting_closure','medium',m,a,'پیشرفت ۱۰۰ درصد است و بستن اقدام تأیید نشده است.')
                seen=self.observations.get(source(m,a)['id'],{})
                last=instant(seen.get('changed_at'))
                if a.get('progress_percent') is not None and last and last<=self.now-timedelta(days=q.stale_days):
                    add('stalled_progress','high',m,a,'از زمان مشاهده آوان، درصد پیشرفت تغییری نکرده است؛ فعالیت خارج از سامانه قابل قضاوت نیست.')
                submitted=instant(a.get('last_submission_at_utc'))
                created=instant(a.get('created_at_utc'))
                reporting_age=submitted or created
                if a.get('submission_history_available') and reporting_age and reporting_age<=self.now-timedelta(days=q.stale_days):
                    add('no_recent_report','medium',m,a,'گزارش اجرا در بازه پایش ثبت نشده است.')
        # Recurring exact normalized titles are a screening signal, not a
        # semantic/root-cause conclusion. Deeper recurrence uses model searches.
        topics=defaultdict(list)
        units=defaultdict(list)
        for m in self.meetings:
            pending=[a for a in m.get('actions',[]) if not a.get('is_closed')]
            if pending and normal(m.get('title')):topics[normal(m['title'])].append((m,pending[0]))
            for a in pending:units[a.get('owner_unit') or 'واحد ثبت نشده'].append((m,a))
        for title,pairs in topics.items():
            if len(pairs)>=2:
                m,a=pairs[0]
                add('recurring_open_topic','medium',m,a,f'عنوان مشترک در {len(pairs)} جلسه دارای اقدام باز دیده شده است؛ ارتباط معنایی نیازمند بررسی است.')
                alerts[-1]['related_sources']=[source(m,a) for m,a in pairs[:10]]
        baseline=self.observations.get('__backlog',{})
        if self.complete and baseline.get('complete'):
            for unit,pairs in units.items():
                previous=baseline['counts'].get(unit,0)
                if len(pairs)-previous>=3 and len(pairs)>previous*1.25:
                    m,a=pairs[0]
                    add('backlog_growth','high',m,a,f'اقدامات باز {unit} از {previous} به {len(pairs)} نسبت به مشاهده قبلی افزایش یافته است؛ تغییر دامنه دسترسی هم می‌تواند مؤثر باشد.')
                    alerts[-1]['comparison_at']=baseline['at']
        alerts.sort(key=lambda a:(a['severity']!='high',-a['overdue_days'],a['source']['id']))
        return {'total':len(alerts),'alerts':alerts[:100],'truncated':len(alerts)>100,
                'notes':['توقف پیشرفت فقط از تاریخ شروع مشاهده آوان قابل تشخیص است.',
                         'هشدار نبود گزارش فقط در صورت وجود تاریخچه ارسال قابل محاسبه است.']}

