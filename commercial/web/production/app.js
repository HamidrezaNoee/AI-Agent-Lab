"use strict";
const app={user:null,csrf:null,page:"overview",cursor:null,meetings:[],questions:[],sending:false,pendingQuestion:null,monitorTimer:null,newConversation:false};
const $=id=>document.getElementById(id);
function el(tag,klass,text){const n=document.createElement(tag);if(klass)n.className=klass;if(text!==undefined)n.textContent=String(text);return n}
function add(parent,...children){for(const x of children.flat())if(x!==undefined&&x!==null)parent.append(x);return parent}
function link(text,callback,klass="button secondary"){const b=el("button",klass,text);b.type="button";b.addEventListener("click",callback);return b}
function card(title,subtitle){const s=el("section","panel");add(s,el("h2","",title),el("p","sub",subtitle||""));return s}
function note(text,error=false){return el("div","notice"+(error?" error":""),text)}
function heading(container,title,description){add(container,add(el("div","page-head"),el("h1","",title),el("p","",description)))}
function root(){const m=$("main");m.replaceChildren();return m}
function fmt(value){return new Intl.NumberFormat("fa-IR").format(value)}
function toast(text){const t=$("toast");t.textContent=text;t.hidden=false}
async function request(url,options={}){
 const headers={"Accept":"application/json",...(options.headers||{})};
 if(options.method==="POST" && app.csrf)headers["X-AVAN-CSRF"]=app.csrf;
 const response=await fetch(url,{...options,headers,credentials:"same-origin",cache:"no-store",redirect:"error"});
 if(response.status===401){sessionExpired();throw Error("نشست سازمانی پایان یافته است. دوباره وارد شوید.")}
 if(!response.ok){
   let message="دریافت اطلاعات با خطا مواجه شد.";
   try{const e=await response.json();if(typeof e.detail==="string")message=e.detail}catch{}
   throw Error(message);
 }
 return response.json();
}
function sessionExpired(){
 if(app.monitorTimer){clearTimeout(app.monitorTimer);app.monitorTimer=null}
 app.user=null;app.csrf=null;$("nav").hidden=true;$("logout").hidden=true;
 const m=root();add(m,add(el("section","login-card"),
   el("h1","","ورود سازمانی"),el("p","","برای ادامه با حساب سازمانی وارد شوید."),
   (()=>{const a=el("a","button primary","ورود با حساب سازمانی");a.href="/auth/login";return a})()));
}
function titleCase(role){return {Expert:"کارشناس",Manager:"مدیر",SysAdmin:"مدیر سیستم"}[role]||role}
function setupUser(user){
 app.user=user;app.csrf=user.csrf;$("nav").hidden=false;$("logout").hidden=false;
 $("person-name").textContent=user.name+" · "+titleCase(user.role);
 $("company-name").textContent=user.company;
 $("company-sub").textContent=user.department||"مدیریت جلسات";
 $("logout").addEventListener("click",async()=>{
  try{await request("/auth/logout",{method:"POST"})}catch{}window.location.replace("/");
 },{once:true});
 document.querySelectorAll("#nav button").forEach(b=>b.addEventListener("click",()=>select(b.dataset.page)));
}
function select(page){
 if(app.monitorTimer){clearTimeout(app.monitorTimer);app.monitorTimer=null}
 app.page=page;
 const labels={overview:"نمای کلی",meetings:"جلسات و مصوبات",assistant:"دستیار مدیریتی",secretary:"دبیر هوشمند",monitor:"هشدار و پیگیری"};
 $("breadcrumb").textContent=labels[page]||"آوان";
 document.querySelectorAll("#nav button").forEach(b=>b.classList.toggle("active",b.dataset.page===page));
 const m=root();add(m,el("p","muted","در حال دریافت اطلاعات سازمان..."));
 const work={overview:overview,meetings:meetingPage,assistant:assistantPage,secretary:secretaryPage,monitor:monitorPage}[page];
 if(work)work().catch(err=>{const target=root();add(target,note(err.message,true))});
}
async function fetchMeetings(cursor=null){
 const url="/api/meetings?limit=30"+(cursor!==null?"&cursor="+encodeURIComponent(cursor):"");
 return request(url);
}
async function overview(){
 const page=await fetchMeetings();
 const m=root();heading(m,"فضای کاری "+app.user.name,
  "اطلاعات ثبت‌شده در فرایند جلسات، متناسب با نقش و ارتباط سازمانی شما نمایش داده می‌شود.");
 if(page.has_more)add(m,note("فهرست کامل جلسات بیش از ۳۰ مورد است؛ برای بررسی همه جلسات از صفحه جلسات و مصوبات استفاده کنید."));
 const stats=el("div","stats");
 for(const [label,value] of [["جلسات بارگذاری‌شده",page.meetings.length],
   ["سطح دسترسی",titleCase(app.user.role)],["واحد سازمانی",app.user.department||"ثبت نشده"]]){
  add(stats,add(el("div","stat"),el("span","",label),el("strong","",value)));
 }
 add(m,stats);
 const panel=card("جلسات اخیر","جلسات قابل مشاهده براساس هویت فعلی");
 for(const meeting of page.meetings.slice(0,8))add(panel,meetingRow(meeting));
 if(!page.meetings.length)add(panel,el("p","muted","جلسه‌ای در دامنه مجاز این حساب یافت نشد."));
 add(m,panel,link("پرسش تخصصی درباره جلسات",()=>select("assistant"),"button primary"));
}
function meetingRow(meeting){
 const row=el("div","meeting-row"),details=el("div");
 add(details,el("strong","",meeting.title),el("small","",meeting.meeting_no+" · "+meeting.meeting_status+
  " · "+(meeting.meeting_date_utc||"تاریخ ثبت نشده")));
 add(row,details,link("بررسی اقدامات",()=>{
  app.pendingQuestion="اقدامات جلسه شماره "+meeting.meeting_no+" در چه وضعیتی هستند؟";
  select("assistant");
 }));
 return row;
}
async function meetingPage(){
 const m=root();heading(m,"جلسات و مصوبات","فقط جلسات مجاز شما نمایش داده می‌شوند.");
 const panel=card("فهرست جلسات","با انتخاب هر جلسه می‌توانید وضعیت اقدامات آن را بررسی کنید.");
 add(m,panel);
 app.meetings=[];app.cursor=null;
 async function appendPage(){
  const next=await fetchMeetings(app.cursor);
  app.meetings.push(...next.meetings);
  for(const mtg of next.meetings)add(panel,meetingRow(mtg));
  if(!app.meetings.length)add(panel,el("p","muted","جلسه‌ای برای این حساب ثبت نشده است."));
  more.replaceChildren();
  app.cursor=next.next_cursor;
  if(next.has_more)add(more,link("بارگذاری جلسات بیشتر",()=>appendPage().catch(err=>{
    add(more,note(err.message,true))
  })));
 }
 const more=el("div");
 add(m,more);
 await appendPage();
}
async function assistantPage(){
 const questionCatalog=await request("/api/questions");
 const m=root();heading(m,"دستیار مدیریتی",
   "گزارش‌های مستند از اقدامات، مصوبات و جلسات مجاز شما.");
 const form=card("پرسش مدیریتی","پاسخ براساس وضعیت ثبت‌شده در فرایند همراه با ارجاع به شماره جلسه و اقدام");
 const text=el("textarea");text.id="management-question";text.maxLength=2000;
 text.placeholder="سؤال مدیریتی خود را وارد کنید، یا یکی از پرسش‌های آماده را انتخاب کنید.";
 text.setAttribute("aria-label","سؤال مدیریتی");
 const send=link("دریافت پاسخ",()=>askQuestion(text.value),"button primary");
 const result=el("div");result.id="management-result";
 add(form,text,send,link("گفت‌وگوی تازه",()=>{app.newConversation=true;result.replaceChildren();text.value=""}),result);add(m,form);
 const status=await request("/api/agent/status");
 if(!status.enabled)add(form,note("مدل هوش مصنوعی فعال نیست؛ مدیر سامانه باید تنظیمات هوش مصنوعی را تکمیل کند.",true));
 const suggestions=card("پرسش‌های تخصصی","برای اجرای گزارش، یک سؤال را انتخاب کنید.");
 const grid=el("div","questions");
 questionCatalog.questions.forEach((q,i)=>add(grid,link(fmt(i+1)+". "+q,()=>{
   text.value=q;askQuestion(q);
 },"")));
 add(suggestions,grid);add(m,suggestions);
 if(app.pendingQuestion){
   const pending=app.pendingQuestion;app.pendingQuestion=null;
   text.value=pending;await askQuestion(pending);
 }
}
async function askQuestion(question){
 const target=$("management-result");if(!target)return;
 if(app.sending){toast("پرسش قبلی هنوز در حال بررسی است.");return}
 target.replaceChildren();
 if(question.trim().length<3){add(target,note("پرسش باید حداقل سه کاراکتر داشته باشد.",true));return}
 app.sending=true;add(target,note("در حال محاسبه پاسخ از اطلاعات مجاز جلسات..."));
 try{
  const result=await request("/api/ask",{
    method:"POST",headers:{"Content-Type":"application/json"},
    body:JSON.stringify({question:question.trim(),new_conversation:app.newConversation})
  });
  if(!target.isConnected)return;
  target.replaceChildren();
  app.newConversation=false;
  renderAnalysis(target,result);
  for(const n of result.notes||[])add(target,el("p","muted","• "+n));
  if(result.coverage_complete===false)add(target,note("دامنه بررسی به حد مجاز رسیده و پوشش گزارش کامل نیست."));
 }catch(err){
  if(target.isConnected){target.replaceChildren();add(target,note(err.message,true))}
 }finally{app.sending=false}
}
async function init(){
 try{const user=await request("/api/me");setupUser(user);select("overview")}
 catch(err){
  if(err.message.includes("نشست سازمانی"))return;
  const m=root();add(m,note(err.message,true),link("ورود با حساب سازمانی",()=>{
    window.location.assign("/auth/login");
  },"button primary"));
 }
}
document.addEventListener("DOMContentLoaded",init);


function renderAnalysis(target,result){
 add(target,el("p","muted","مدل: "+(result.model||"—")+" · بررسی "+fmt(result.meetings_considered)+" جلسه و "+fmt(result.actions_considered)+" اقدام"));
 if(result.clarification)add(target,note(result.clarification));
 const labels={fact:"یافته مستند",analysis:"تحلیل",recommendation:"پیشنهاد مدیریتی"};
 for(const c of result.claims||[]){
  const item=el("div","claim "+c.kind);add(item,el("strong","",labels[c.kind]),el("p","answer",c.text),el("small","",c.sources.join(" · ")));add(target,item);
 }
 const evidence=card("مستندات و محاسبات","پاسخ تحلیلی برداشت مدل از شواهد است؛ جزئیات محاسبات و ارجاع‌ها را می‌توانید بررسی کنید.");
 for(const ref of result.evidence||[]){
  const d=el("details","source");add(d,el("summary","",ref.id+" · "+(ref.meeting_no||ref.title||"گزارش")));
  if(ref.result){
   if(ref.result.metrics){const table=el("table");for(const [key,value] of Object.entries(ref.result.metrics)){const row=el("tr");add(row,el("th","",({total:"کل اقدامات",closed:"بسته‌شده",open:"باز",overdue:"تأخیردار",missing_due:"بدون موعد",missing_progress:"بدون درصد پیشرفت",average_progress:"میانگین پیشرفت",closure_rate_percent:"درصد بسته‌شدن"})[key]||key),el("td","",value===null?"نامشخص":fmt(value)));add(table,row)}add(d,table)}
   const data=ref.result;
   if(data.period_start)add(d,el("p","","بازه بررسی: "+data.period_start+" تا "+(data.period_end||"اکنون")));
   for(const g of data.groups||[])add(d,el("p","",g.group.join(" · ")+": "+fmt(g.total)+" اقدام، "+fmt(g.open)+" باز، "+fmt(g.overdue)+" تأخیردار"));
   for(const row of [...(data.rows||[]),...(data.alerts||[])]){
    add(d,el("p","",row.description||row.title||row.reason||""));
    if(row.discussion)add(d,el("blockquote","",row.discussion));
    if(row.source)add(d,el("small","","جلسه "+row.source.meeting_no+(row.source.action_no?" · اقدام "+row.source.action_no:"")));
   }
   if(data.has_more||data.truncated)add(d,note("فهرست نمایشی خلاصه شده است؛ تعداد کل در محاسبات لحاظ شده است."));
  }else add(d,el("p","",ref.title+(ref.action_no?" · اقدام "+ref.action_no:"")));
  add(evidence,d);
 }
 add(target,evidence,el("small","muted","زمان بررسی: "+result.as_of_utc));
}
async function secretaryPage(){
 const m=root();heading(m,"دبیر هوشمند جلسه","از متن جلسه، پیش‌نویس مصوبات و پیشنهاد مسئول، اولویت و موعد تهیه کنید.");
 if(!app.user.modules.includes(2)){add(m,note("ماژول دبیر هوشمند در لایسنس فعال نیست."));return}
 const panel=card("تهیه پیش‌نویس","شماره دقیق جلسه و متن گفتگو یا یادداشت دبیر را وارد کنید.");
 const number=el("input");number.placeholder="شماره جلسه";number.maxLength=80;number.setAttribute("aria-label","شماره جلسه");
 const notes=el("textarea");notes.rows=12;notes.maxLength=18000;notes.placeholder="متن جلسه و تصمیمات...";notes.setAttribute("aria-label","متن جلسه");
 const result=el("div");
 const create=link("استخراج مصوبات",async()=>{
  if(notes.value.trim().length<10||!number.value.trim()){result.replaceChildren(note("شماره جلسه و متن کافی وارد کنید.",true));return}
  create.disabled=true;result.replaceChildren(note("در حال استخراج پیش‌نویس..."));
  try{const draft=await request("/api/secretary/drafts",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({meeting_no:number.value.trim(),notes:notes.value.trim()})});
   result.replaceChildren();renderDraft(result,draft);
  }catch(e){result.replaceChildren(note(e.message,true))}finally{create.disabled=false}
 },"button primary");
 add(panel,number,notes,create,link("پیشنهاد دستور جلسه و گزارش پیگیری",()=>{app.pendingQuestion="برای جلسه آینده با توجه به اقدامات باز و سوابق جلسه شماره "+number.value+" دستور جلسه و گزارش پیگیری پیشنهاد بده";select("assistant")}),result);add(m,panel);
}
function renderDraft(target,draft){
 const payload=draft.payload;
 add(target,el("p","answer",payload.summary),note("پیش‌نویس پیشنهادی است. برای اصلاح، متن بالای صفحه را تغییر دهید و دوباره استخراج کنید."));
 for(const [i,a] of payload.actions.entries()){
  const item=card("اقدام "+fmt(i+1),a.description);
  const person=payload.candidate_owners.find(x=>x.uid===a.owner_uid);
  add(item,el("p","","مسئول پیشنهادی: "+(person?.name||a.suggested_role||"نیازمند تعیین")),
    el("p","",a.owner_reason),el("p","","اولویت پیشنهادی: "+({low:"کم",normal:"عادی",high:"زیاد",urgent:"فوری"}[a.priority])),
    el("p","","موعد پیشنهادی (میلادی): "+(a.proposed_due_date||"نامشخص")),el("p","",a.due_reason),
    el("blockquote","",a.source_quote));
  if(a.needs_clarification)add(item,note("این اقدام نیازمند رفع ابهام است."));add(target,item);
 }
 for(const q of payload.questions)add(target,note(q));
 const approval=el("label"),check=el("input");check.type="checkbox";add(approval,check,el("span","","موارد پیشنهادی را بررسی کردم و این پیش‌نویس را تأیید می‌کنم."));
 const out=el("div");const approve=link("تأیید پیش‌نویس",async()=>{
  if(!check.checked){out.replaceChildren(note("ابتدا بازبینی را تأیید کنید.",true));return}
  approve.disabled=true;
  try{await request("/api/secretary/drafts/"+encodeURIComponent(draft.id)+"/approve",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({confirmed:true})});
   out.replaceChildren(note("پیش‌نویس تأیید شد. ثبت در ProcessMaker انجام نشده است."));
   const a=el("a","button primary","دریافت اطلاعات تأییدشده برای انتقال");a.href="/api/secretary/drafts/"+encodeURIComponent(draft.id)+"/export";a.download="meeting-actions.json";add(out,a);
  }catch(e){out.replaceChildren(note(e.message,true));approve.disabled=false}
 });add(target,approval,approve,out);
}
async function monitorPage(){
 const m=root();heading(m,"هشدار و پیگیری","نشانه‌های تأخیر، موعد نزدیک، نبود گزارش و توقف پیشرفت در دامنه مجاز شما.");
 if(!app.user.modules.includes(4)){add(m,note("ماژول پایش در لایسنس فعال نیست."));return}
 const control=card("پایش دوره‌ای","با فعال‌سازی، سرور هر پنج دقیقه تا پایان اعتبار نشست شما بررسی می‌کند. یادآوری‌ها در همین صفحه نمایش داده می‌شوند.");
 const out=el("div"),results=el("div");let running=false;
 async function refresh(){
  if(running||app.page!=="monitor")return;running=true;
  try{
   const r=await request("/api/monitor",{method:"POST"});if(!results.isConnected)return;
   results.replaceChildren();add(results,note(fmt(r.total)+" هشدار در زمان "+r.as_of_utc));
   if(!r.coverage_complete||r.truncated)add(results,note("دامنه یا فهرست نمایش کامل نیست؛ نتیجه فقط مربوط به داده‌های بازیابی‌شده است."));
   for(const a of r.alerts){
    const item=card(a.severity==="high"?"نیازمند پیگیری فوری":"نیازمند پیگیری",a.reason);
    add(item,el("p","",a.description),el("p","","جلسه "+a.source.meeting_no+" · اقدام "+a.source.action_no+" · "+(a.owner_name||"مسئول نامشخص")),
     el("p","","پیشرفت: "+(a.progress_percent===null?"ثبت نشده":fmt(a.progress_percent)+"٪")));
    const reminder=el("textarea");reminder.readOnly=true;reminder.value="یادآوری اقدام "+a.source.action_no+" جلسه "+a.source.meeting_no+": "+a.description+". لطفاً آخرین وضعیت، موانع و زمان تکمیل را در فرایند ثبت کنید.";
    add(item,link("آماده‌سازی متن یادآوری",()=>{if(!reminder.isConnected)add(item,reminder);reminder.select()}));add(results,item);
   }
   for(const n of r.notes||[])add(results,el("p","muted",n));
  }catch(e){results.replaceChildren(note(e.message,true))}finally{running=false;if(app.page==="monitor")app.monitorTimer=setTimeout(refresh,60000)}
 }
 add(control,link("فعال‌سازی پایش",()=>subscribe(true)),link("توقف پایش",()=>subscribe(false)),out);
 async function subscribe(enabled){try{await request("/api/monitor/subscribe",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({enabled})});out.replaceChildren(note(enabled?"پایش تا پایان نشست فعال شد.":"پایش دوره‌ای متوقف شد."))}catch(e){out.replaceChildren(note(e.message,true))}}
 add(m,control,results);await refresh();
}
