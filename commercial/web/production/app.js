"use strict";
const app={processChoices:{},processManifests:{},secretaryTimer:null,user:null,csrf:null,page:"overview",selectedSourceId:null,cursor:null,meetings:[],questions:[],sending:false,pendingQuestion:null,monitorTimer:null,idleTimer:null,lastHeartbeat:0,newConversation:true,conversationId:null,voiceEnabled:false,cleanup:[]};
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
function sourceApi(sourceId,path){
 return sourceId?("/api/sources/"+encodeURIComponent(sourceId)+path):("/api"+path);
}
async function request(url,options={}){
 const headers={"Accept":"application/json",...(options.headers||{})};
 const scoped=url.match(/^\/api\/sources\/([^/]+)\/(ask|questions|meetings(?:\/[^/]+)?|agent\/(status|history)|reports\/actions(?:\/ask)?|monitor(?:\/[^/]+)?|voice\/(speech|transcribe))(?:\?|$)/);
 if(scoped&&app.processChoices[scoped[1]]?.packId)headers["X-AVAN-Process-Pack"]=app.processChoices[scoped[1]].packId;
 if(options.background)headers["X-AVAN-BACKGROUND"]="1";
 if(options.method==="POST" && app.csrf)headers["X-AVAN-CSRF"]=app.csrf;
 const {background,...fetchOptions}=options;
 const response=await fetch(url,{...fetchOptions,headers,credentials:"same-origin",cache:"no-store",redirect:"error"});
 if(response.status===401){
   if(app.user?.bootstrap_mode && url!=="/api/me" && url.startsWith("/api/")){
     throw Error("هویت سازمانی GodAdmin هنوز متصل نشده است؛ این بخش فعلاً در حالت محدود نمایش داده می‌شود.");
   }
   sessionExpired();throw Error("نشست سازمانی پایان یافته است. دوباره وارد شوید.")
 }
 if(!response.ok){
   let message="دریافت اطلاعات با خطا مواجه شد.";
   try{const e=await response.json();if(typeof e.detail==="string")message=e.detail}catch{}
   const error=Error(message);error.status=response.status;throw error;
 }
 return options.binary?response:response.json();
}
function cleanMedia(){for(const fn of app.cleanup.splice(0)){try{fn()}catch{}}}
function sessionExpired(){
 app.processChoices={};app.processManifests={};
 if(app.secretaryTimer){clearInterval(app.secretaryTimer);app.secretaryTimer=null}
 const wasBootstrap=!!app.user?.bootstrap_mode;
 cleanMedia();
 if(app.monitorTimer){clearTimeout(app.monitorTimer);app.monitorTimer=null}
 if(app.idleTimer){clearTimeout(app.idleTimer);app.idleTimer=null}
 app.user=null;app.csrf=null;$("nav").hidden=true;$("logout").hidden=true;$("admin-entry").hidden=true;
 document.body.classList.add("auth-screen");
 const m=root(),login=el("section","login-card"),a=el("a","button primary","ورود امن به فضای کار ←");
 a.href=wasBootstrap?"/admin/":"/auth/login";
 add(login,el("span","eyebrow","AVAN · INTELLIGENT WORKSPACE"),
  el("h1","","هوش جلسات در کنار تصمیم‌های شما"),
  el("p","","برای ادامه، با حساب سازمانی خود وارد شوید. زمان نشست پس از ده دقیقه بی‌فعالیتی پایان می‌یابد."),a);
 add(m,login);
}
function statusName(value){return {TO_DO:"در جریان",COMPLETED:"تکمیل‌شده",DRAFT:"پیش‌نویس",CANCELLED:"لغوشده",PAUSED:"متوقف",Open:"باز",Closed:"بسته‌شده"}[value]||value}
function titleCase(role){return {Expert:"کارشناس",Manager:"مدیر",SysAdmin:"مدیر سیستم",GodAdmin:"مدیر کل سامانه"}[role]||role}
function setupUser(user){
 app.user=user;app.csrf=user.csrf;$("nav").hidden=false;
 const workspaceNavigation=user.workspace_navigation!==undefined
   ?!!user.workspace_navigation
   :!!user.workspace_access;
 $("pm-nav").hidden=!workspaceNavigation||(user.bpms_sources||[]).length>0;
 $("platform-nav").hidden=!(user.is_godadmin&&user.platform_access!==false);
 $("admin-nav").hidden=!user.is_godadmin;
 const sourceNav=$("bound-source-nav"),sourceButtons=$("bound-source-buttons");
 sourceButtons.replaceChildren();
 const sourcePageButton=(source,page,label)=>{
  const b=el("button","",label);b.type="button";b.dataset.page=page;b.dataset.sourceId=source.source_id;
  b.addEventListener("click",()=>{app.selectedSourceId=source.source_id;select(page)});return b;
 };
 for(const source of user.bpms_sources||[]){
  const group=el("div","bound-source-group");
  add(group,el("span","bound-source-name",source.source_name));
  const capabilities=new Set(source.capabilities||["overview"]);
  add(group,sourcePageButton(source,"source-overview","◉  نمای BPMS"));
  if(capabilities.has("bi"))add(group,sourcePageButton(source,"source-bi","▦  BI اتصال"));
  add(sourceButtons,group);
  if(source.engine==="processmaker")loadProcessChoices(source,group);
 }
 sourceNav.hidden=!(user.bpms_sources||[]).length;
 installSecretaryBadges();
 $("admin-entry").hidden=true;$("logout").hidden=false;
 document.body.classList.remove("auth-screen");
 $("person-name").textContent=user.name+" · "+titleCase(user.role);
 $("company-name").textContent=user.company;
 $("company-sub").textContent=user.workspace_degraded
   ?(user.department||"حساب AVAN")+" · اتصال BPMS نیازمند بررسی"
   :(user.department||"فضای کاری سازمان");
 $("logout").onclick=signOut;
 recordActivity();
 document.querySelectorAll("#nav button:not([data-source-id])").forEach(b=>b.addEventListener("click",()=>select(b.dataset.page)));
}
async function signOut(){
 if(!app.csrf){sessionExpired();return}
 try{
  if(app.user?.bootstrap_mode){
   const response=await fetch("/admin/api/logout",{
    method:"POST",credentials:"same-origin",cache:"no-store",
    headers:{"Accept":"application/json","X-AVAN-ADMIN-CSRF":app.csrf}
   });
   if(!response.ok)throw Error("خروج انجام نشد.");
   sessionExpired();
   window.location.assign("/auth/login");
   return;
  }
  const response=await request("/auth/logout",{method:"POST"});
  sessionExpired();
  try{localStorage.setItem("avan-logout",String(Date.now()))}catch(_){}
  window.location.assign(response.logout_url||"/auth/signed-out");
 }catch(error){
  if(!app.user){window.location.assign("/auth/signed-out");return}
  toast(error.message||"خروج انجام نشد؛ دوباره تلاش کنید.");
 }
}
function recordActivity(){
 if(!app.user)return;
 clearTimeout(app.idleTimer);
 app.idleTimer=setTimeout(signOut,600000);
 if(Date.now()-app.lastHeartbeat<60000)return;
 app.lastHeartbeat=Date.now();
 if(app.user.bootstrap_mode){
  fetch("/admin/api/heartbeat",{credentials:"same-origin",cache:"no-store"}).catch(()=>{});
 }else{
  request("/auth/heartbeat",{method:"POST"}).catch(()=>{});
 }
}
for(const eventName of ["pointerdown","keydown","touchstart"]){
 document.addEventListener(eventName,recordActivity,{passive:true});
}
window.addEventListener("storage",event=>{if(event.key==="avan-logout"&&app.user)sessionExpired()});
function select(page){
 const platformPage=page.startsWith("platform-");
 const adminPage=page==="system-management";
 const sourcePage=page.startsWith("source-");
 const orgPage=!platformPage&&!adminPage&&!sourcePage;
 if(platformPage&&(!app.user?.is_godadmin||app.user?.platform_access===false))return;
 if(adminPage&&!app.user?.is_godadmin)return;
 if(sourcePage){
  const source=(app.user?.bpms_sources||[]).find(x=>x.source_id===app.selectedSourceId);
  const required={"source-meetings":"meetings","source-assistant":"assistant",
   "source-secretary":"secretary","source-reports":"reports","source-monitor":"monitor","source-bi":"bi"}[page];
  if(!source||(required&&!(source.capabilities||[]).includes(required)))return;
 }
 const workspaceNavigation=app.user?.workspace_navigation!==undefined?!!app.user.workspace_navigation:!!app.user?.workspace_access;
 if(orgPage&&!workspaceNavigation)return;
 cleanMedia();
 if(app.monitorTimer){clearTimeout(app.monitorTimer);app.monitorTimer=null}
 app.page=page;
 const labels={overview:"نمای کلی",meetings:"جلسات و مصوبات",assistant:"دستیار مدیریتی",reports:"گزارش اقدامات",bi:"BI همه فرایندها",secretary:"دبیر هوشمند",monitor:"هشدار و پیگیری","source-overview":"BPMS متصل","source-meetings":"جلسات BPMS","source-assistant":"دستیار BPMS","source-secretary":"دبیر هوشمند BPMS","source-reports":"گزارش اقدامات BPMS","source-monitor":"هشدار و پیگیری BPMS","source-bi":"BI منبع","platform-overview":"نمای کلی پلتفرم","platform-assistant":"دستیار پلتفرم","platform-bi":"گزارش BPMSها","system-management":"مدیریت سامانه"};
 $("breadcrumb").textContent=labels[page]||"آوان";
 document.querySelectorAll("#nav button").forEach(b=>b.classList.toggle("active",
   sourcePage&&b.dataset.sourceId
    ?b.dataset.sourceId===app.selectedSourceId&&b.dataset.page===page&&(!b.dataset.section||(b.dataset.packId===app.processChoices[app.selectedSourceId]?.packId&&b.dataset.section===app.processChoices[app.selectedSourceId]?.section))
    :b.dataset.page===page));
 const m=root();add(m,el("p","muted",adminPage?"در حال باز کردن مدیریت سامانه...":"در حال دریافت اطلاعات سازمان..."));
 const work={overview:overview,meetings:meetingPage,assistant:assistantPage,reports:reportsPage,bi:biPage,secretary:secretaryPage,monitor:monitorPage,"source-overview":boundSourceOverview,"source-meetings":boundSourceMeetings,"source-assistant":()=>assistantPage(app.selectedSourceId),"source-secretary":()=>processWorkspacePage(),"source-process":processWorkspacePage,"source-reports":()=>reportsPage(app.selectedSourceId),"source-monitor":()=>monitorPage(app.selectedSourceId),"source-bi":()=>biPage(app.selectedSourceId),"platform-overview":platformOverview,"platform-assistant":platformAssistant,"platform-bi":platformBI,"system-management":systemManagement}[page];
 if(work)work().catch(err=>{
  const target=root();
  if(orgPage&&app.user?.is_godadmin){
   heading(target,labels[page]||"فضای کاری سازمان","این بخش در Workspace باقی می‌ماند؛ اختلال منبع داده باعث انتقال به تنظیمات نمی‌شود.");
   add(target,note(err.message||"منبع داده سازمانی موقتاً در دسترس نیست.",true));
   const actions=el("div","flex");
   add(actions,
     link("تلاش دوباره",()=>select(page),"button primary"),
     link("مدیریت سامانه",()=>select("system-management"),"button secondary"));
   add(target,actions);
  }else add(target,note(err.message,true));
 });
}
async function fetchMeetings(cursor=null){
 const url="/api/meetings?limit=30"+(cursor!==null?"&cursor="+encodeURIComponent(cursor):"");
 return request(url);
}
async function overview(){
 const m=root();if(app.page!=="overview")return;
 const sources=app.user?.bpms_sources||[];
 heading(m,"فضای کاری "+app.user.name,
  "حساب و نقش شما در AVAN مستقل از BPMSهاست. برای داده و ابزار عملیاتی، BPMS متصل را انتخاب کنید.");
 const stats=el("div","stats");
 for(const [label,value] of [
  ["BPMSهای متصل",fmt(sources.length)],
  ["سطح دسترسی AVAN",titleCase(app.user.role)],
  ["واحد سازمانی",app.user.department||"ثبت نشده"]
 ])add(stats,add(el("div","stat"),el("span","",label),el("strong","",value)));
 add(m,stats);
 const panel=card("BPMSهای در دسترس","هر اتصال با کاربر متناظر همان BPMS و قابلیت‌های مجاز خودش نمایش داده می‌شود.");
 if(!sources.length){
  add(panel,note("هنوز BPMS فعالی به این حساب AVAN متصل نشده است."));
 }else{
  for(const source of sources){
   const row=el("div","meeting-row"),details=el("div");
   const capabilities=(source.capabilities||[]).filter(x=>x!=="overview").length;
   add(details,el("strong","",source.source_name),
    el("small","",(source.engine||"BPMS")+" · کاربر: "+
     (source.external_display_name||source.external_username||source.external_user_id||"—")+
     " · "+fmt(capabilities)+" قابلیت عملیاتی"));
   add(row,details,link("ورود به این BPMS",()=>{
    app.selectedSourceId=source.source_id;select("source-overview")
   },"button primary"));
   add(panel,row);
  }
 }
 add(m,panel);
}
function meetingRow(meeting){
 const row=el("div","meeting-row"),details=el("div");
 add(details,el("strong","",meeting.title),el("small","",meeting.meeting_no+" · "+meeting.meeting_status+
  " · "+(meeting.meeting_date_utc||"تاریخ ثبت نشده")));
 add(row,details,link("نمایش جزئیات",()=>showMeeting(meeting.meeting_id)),link("تحلیل اقدامات",()=>{
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
async function assistantPage(sourceId=null){
 const scoped=!!sourceId;
 const source=scoped?(app.user?.bpms_sources||[]).find(x=>x.source_id===sourceId):null;
 const m=root();
 if(scoped&&(!source||!(source.capabilities||[]).includes("assistant"))){
  add(m,note("دستیار برای این BPMS و لایسنس فعلی فعال نیست.",true));return
 }
 const base=sourceId?("/api/sources/"+encodeURIComponent(sourceId)):"/api";
 const [catalog,status,history]=await Promise.all([
  request(base+"/questions"),request(base+"/agent/status"),request(base+"/conversations")
 ]);
 if(app.page!==(scoped?"source-assistant":"assistant"))return;
 app.voiceEnabled=status.voice_enabled;
 heading(m,scoped?("دستیار · "+source.source_name):"دستیار مدیریتی",
  scoped
   ?"پرسش فقط بر داده‌های مجاز همین BPMS و Binding فعلی پاسخ داده می‌شود."
   :"پرسش فارسی، پاسخ مستند و گفت‌وگوهای ذخیره‌شده شما");
 const layout=el("div","agent-layout"),past=card("گفت‌وگوهای من","پاسخ‌های قبلی با زمان ثبت نمایش داده می‌شوند؛ برای وضعیت روز دوباره سؤال کنید.");
 const work=el("div"),form=card("پرسش مدیریتی","پاسخ شامل یافته، تحلیل و پیشنهاد همراه با شواهد جلسه است.");
 const text=el("textarea");text.id="management-question";text.maxLength=2000;text.rows=4;text.placeholder="مثلاً: کدام واحد بیشترین مصوبات تأخیردار را دارد و چه اقدامی پیشنهاد می‌دهی؟";text.setAttribute("aria-label","سؤال مدیریتی");
 const result=el("div");result.id="management-result";result.setAttribute("aria-live","polite");
 const startNew=()=>{app.newConversation=true;app.conversationId=null;result.replaceChildren();text.value="";text.focus()};
 add(form,text,link("دریافت پاسخ",()=>askQuestion(text.value,sourceId),"button primary"),link("گفت‌وگوی تازه",startNew));
 if(status.voice_enabled)attachVoiceInput(form,text,false,sourceId);
 if(!status.enabled)add(form,note("مدیر سامانه باید اتصال هوش مصنوعی را فعال کند.",true));
 add(work,form,result);add(layout,past,work);add(m,layout);
 const load=async id=>{
  try{const conv=await request(base+"/conversations/"+encodeURIComponent(id));if(!result.isConnected)return;
   app.conversationId=id;app.newConversation=false;result.replaceChildren();
   for(const turn of conv.turns){const panel=card(turn.question,"پاسخ ثبت‌شده در "+dateText(turn.created_at));
    renderAnalysis(panel,{...turn.answer,conversation_id:id,turn_id:turn.id},sourceId);add(result,panel)}
   text.placeholder="سؤال بعدی درباره این گفتگو...";
  }catch(e){result.replaceChildren(note(e.message,true))}
 };
 for(const item of history.conversations){const row=el("div","history-item");
  add(row,link(item.title,()=>load(item.id),"history-title"),el("small","muted",dateText(item.updated_at)),
   link("حذف",async()=>{try{await request(base+"/conversations/"+encodeURIComponent(item.id)+"/delete",{method:"POST"});row.remove();if(app.conversationId===item.id)startNew()}catch(e){toast(e.message)}},"link-button"));add(past,row)}
 if(!history.conversations.length)add(past,el("p","muted","هنوز گفت‌وگویی ذخیره نشده است."));
 const suggestions=card("پرسش‌های آماده"),grid=el("div","questions");
 catalog.questions.forEach(q=>add(grid,link(q,()=>{text.value=q;askQuestion(q,sourceId)},"")));add(suggestions,grid);add(work,suggestions);
 if(app.pendingQuestion){const q=app.pendingQuestion;app.pendingQuestion=null;startNew();text.value=q;await askQuestion(q,sourceId)}
 else if(app.conversationId)await load(app.conversationId);
}
async function askQuestion(question,sourceId=null){
 const target=$("management-result");if(!target)return;
 if(app.sending){toast("پرسش قبلی هنوز در حال بررسی است.");return}
 if(question.trim().length<3||question.trim().length>2000){toast("پرسش باید بین ۳ و ۲۰۰۰ نویسه باشد.");return}
 app.sending=true;const pending=note("در حال بررسی سوابق و محاسبه پاسخ...");add(target,pending);
 try{const result=await request(sourceApi(sourceId,"/ask"),{method:"POST",headers:{"Content-Type":"application/json"},
  body:JSON.stringify({question:question.trim(),new_conversation:app.newConversation,conversation_id:app.conversationId})});
  if(!target.isConnected)return;pending.remove();app.newConversation=false;app.conversationId=result.conversation_id;
  const panel=card(question,"پاسخ در "+dateText(result.as_of_utc));renderAnalysis(panel,result,sourceId);add(target,panel);panel.scrollIntoView({behavior:"smooth",block:"start"});
 }catch(err){if(target.isConnected)pending.replaceWith(note(err.message,true))}finally{app.sending=false}
}
async function init(){
 try{
  const user=await request("/api/me");setupUser(user);
  const workspaceNavigation=(user.bpms_sources||[]).length>0;
  if(user.bootstrap_mode){select("system-management");return}
  if(workspaceNavigation){app.selectedSourceId=user.bpms_sources[0].source_id;select("source-overview");return}
  if((user.bpms_sources||[]).length){
   app.selectedSourceId=user.bpms_sources[0].source_id;select("source-overview");return
  }
  if(user.is_godadmin&&user.platform_access!==false){select("platform-overview");return}
  const m=root();heading(m,"حساب AVAN فعال است","هنوز هیچ کاربر BPMS به این حساب متصل نشده است.");
  add(m,note("مدیر سامانه باید از بخش «سازمان و دسترسی» حداقل یک BPMS را به حساب شما متصل کند."));
 }
 catch(err){
  if(err.message.includes("نشست سازمانی"))return;
  const m=root();add(m,note(err.message,true),link("ورود با حساب سازمانی",()=>{
    window.location.assign("/auth/login");
  },"button primary"));
 }
}
document.addEventListener("DOMContentLoaded",init);

async function boundSourceOverview(){
 const source=(app.user?.bpms_sources||[]).find(x=>x.source_id===app.selectedSourceId);
 const m=root();
 if(!source){add(m,note("اتصال BPMS برای این حساب در دسترس نیست.",true));return}
 heading(m,source.source_name,"این BPMS با یک Binding مستقل به حساب AVAN شما متصل است.");
 const stats=el("div","stats");
 for(const [label,value] of [
  ["نوع BPMS",source.engine||"—"],
  ["کاربر متصل",source.external_display_name||source.external_username||source.external_user_id||"—"],
  ["وضعیت","Binding فعال"]
 ])add(stats,add(el("div","stat"),el("span","",label),el("strong","",value)));
 add(m,stats);
 const p=card("دسترسی منبع","نقش و مجوزهای AVAN مستقل هستند؛ این اتصال فقط دامنه داده و قابلیت‌های همین BPMS را مشخص می‌کند.");
 const capabilities=new Set(source.capabilities||["overview"]);
 if(source.engine==="processmaker"){
  add(p,note("داده‌های این ProcessMaker با Source ID خودش و Binding همین حساب خوانده می‌شود."));
  if(capabilities.has("meetings"))add(p,link("جلسات همین ProcessMaker",()=>select("source-meetings"),"button primary"));
  if(capabilities.has("assistant"))add(p,link("دستیار همین ProcessMaker",()=>select("source-assistant"),"button secondary"));
  if(capabilities.has("secretary"))add(p,link("دبیر هوشمند همین ProcessMaker",()=>select("source-secretary"),"button secondary"));
  if(capabilities.has("reports"))add(p,link("گزارش اقدامات همین ProcessMaker",()=>select("source-reports"),"button secondary"));
  if(capabilities.has("monitor"))add(p,link("هشدار و پیگیری همین ProcessMaker",()=>select("source-monitor"),"button secondary"));
  if(capabilities.has("bi"))add(p,link("BI همین ProcessMaker",()=>select("source-bi"),"button secondary"));
  add(m,p);
  const recent=card("جلسات اخیر این ProcessMaker","فقط جلساتی که کاربر متناظر این Binding مجاز به مشاهده آن‌هاست نمایش داده می‌شوند.");
  add(m,recent);
  try{
   const page=await request("/api/sources/"+encodeURIComponent(source.source_id)+"/meetings?limit=8");
   for(const meeting of page.meetings||[]){
    const row=el("div","meeting-row"),details=el("div");
    add(details,el("strong","",meeting.title),
     el("small","",meeting.meeting_no+" · "+meeting.meeting_status+" · "+(meeting.meeting_date_utc||"تاریخ ثبت نشده")));
    add(row,details,link("نمایش جزئیات",()=>showSourceMeeting(source.source_id,meeting.meeting_id)));
    add(recent,row);
   }
   if(!(page.meetings||[]).length)add(recent,el("p","muted","جلسه‌ای در دامنه مجاز این Binding یافت نشد."));
  }catch(err){add(recent,note(err.message,true))}
 }else{
  add(p,note("Binding این منبع فعال است. منوی عملیاتی زمانی نمایش داده می‌شود که آداپتر BPMS قرارداد User-Scoped مربوط به آن قابلیت را ارائه کند."));
  add(m,p);
 }
}

async function boundSourceMeetings(){
 const source=(app.user?.bpms_sources||[]).find(x=>x.source_id===app.selectedSourceId);
 const m=root();
 if(!source||!(source.capabilities||[]).includes("meetings")){
  add(m,note("قابلیت جلسات برای این BPMS و لایسنس فعلی در دسترس نیست.",true));return
 }
 heading(m,"جلسات · "+source.source_name,
  "فقط جلساتی نمایش داده می‌شوند که کاربر BPMS متصل به این حساب AVAN اجازه مشاهده آن‌ها را دارد.");
 const panel=card("فهرست جلسات",source.external_display_name||source.external_username||"Binding فعال");
 add(m,panel);let cursor=null,loaded=0;
 const more=el("div");add(m,more);
 async function load(){
  more.replaceChildren();
  const url="/api/sources/"+encodeURIComponent(source.source_id)+"/meetings?limit=30"+
    (cursor!==null?"&cursor="+encodeURIComponent(cursor):"");
  const page=await request(url);
  for(const meeting of page.meetings||[]){
   loaded++;
   const row=el("div","meeting-row"),details=el("div");
   add(details,el("strong","",meeting.title),
    el("small","",meeting.meeting_no+" · "+meeting.meeting_status+" · "+(meeting.meeting_date_utc||"تاریخ ثبت نشده")));
   add(row,details,link("نمایش جزئیات",()=>showSourceMeeting(source.source_id,meeting.meeting_id)));
   add(panel,row);
  }
  cursor=page.next_cursor;
  if(!loaded)add(panel,el("p","muted","جلسه‌ای در دامنه این Binding یافت نشد."));
  if(page.has_more)add(more,link("بارگذاری جلسات بیشتر",()=>load().catch(err=>add(more,note(err.message,true)))));
 }
 await load();
}

async function showSourceMeeting(sourceId,id){
 try{
  const meeting=await request("/api/sources/"+encodeURIComponent(sourceId)+"/meetings/"+encodeURIComponent(id));
  cleanMedia();app.page="source-detail";
  const m=root();heading(m,meeting.title,"جلسه "+meeting.meeting_no+" · "+dateText(meeting.meeting_date_utc));
  add(m,link("بازگشت به BPMS",()=>select("source-overview")));
  if(meeting.discussion)add(m,card("خلاصه مباحث",meeting.discussion));
  if(meeting.parking_lot)add(m,card("موضوعات باز",meeting.parking_lot));
  const table=el("table"),head=el("tr");
  for(const x of ["اقدام","شرح","مسئول / واحد","وضعیت","پیشرفت","موعد"])add(head,el("th","",x));
  add(table,add(el("thead"),head));const body=el("tbody");
  for(const a of meeting.actions||[]){
   const row=el("tr");
   for(const v of [a.action_no,a.description,(a.owner_name||"نامشخص")+" / "+(a.owner_unit||"نامشخص"),
    a.is_closed?"بسته‌شده":a.status,a.progress_percent==null?"نامشخص":fmt(a.progress_percent)+"٪",
    dateText(a.due_at_utc)])add(row,el("td","",v));
   add(body,row)
  }
  add(table,body);add(m,add(el("div","table-scroll panel"),table));
 }catch(e){toast(e.message)}
}

async function systemManagement(){
 if(!app.user?.is_godadmin)return;
 const m=root();
 heading(m,"مدیریت سامانه","تنظیمات، اتصال‌ها، کاربران، لایسنس و زیرساخت آوان در همان فضای کاری.");
 const frameWrap=el("section","system-admin-shell");
 const frame=el("iframe","system-admin-frame");
 frame.src="/admin/?embedded=1";
 frame.title="مدیریت سامانه آوان";
 frame.setAttribute("loading","eager");
 frame.setAttribute("referrerpolicy","same-origin");
 frame.setAttribute("aria-label","مدیریت سامانه");
 add(frameWrap,frame);add(m,frameWrap);
}

async function platformOverview(){
 const status=await request("/api/platform/status");if(app.page!=="platform-overview")return;
 const m=root();heading(m,"فضای کار GodAdmin","پیکربندی و استفاده از ابزارهای آوان و گزارش BPMSهای متصل.");
 const stats=el("div","stats");for(const [label,value] of [["BPMS متصل",status.sources.filter(s=>s.enabled).length],["دستیار هوشمند",status.enabled?"فعال":"نیازمند تنظیم"],["نقش",app.user.role]])add(stats,add(el("div","stat"),el("span","",label),el("strong","",value)));add(m,stats);
 const panel=card("ابزارهای کاری","گزارش هر BPMS از آداپتر خواندنی همان سامانه دریافت می‌شود.");
 const settings=link("مدیریت سامانه",()=>select("system-management"),"button secondary");
 add(panel,link("دستیار پلتفرم",()=>select("platform-assistant"),"button primary")," ",link("گزارش BPMSها",()=>select("platform-bi"))," ",settings);add(m,panel);
 if(!status.sources.some(s=>s.enabled))add(m,note("برای نمایش گزارش فرایندهای دیگر، یک مبدل AVAN REST v1 را در تنظیمات GodAdmin وصل کنید."));
}

async function platformAssistant(){
 const [status,history]=await Promise.all([request("/api/platform/status"),request("/api/platform/conversations")]);
 if(app.page!=="platform-assistant")return;app.voiceEnabled=status.voice_enabled;
 const m=root();heading(m,"دستیار پلتفرم","پرسش درباره تنظیمات آوان و اتصال BPMS؛ برای آمار سازمانی از صفحه گزارش منبع انتخابی استفاده کنید.");
 const work=card("پرسش از دستیار","پاسخ این بخش بدون داده‌های ProcessMaker ساخته می‌شود.");
 const question=el("textarea");question.maxLength=2000;question.rows=4;question.setAttribute("aria-label","سؤال درباره پلتفرم");
 question.placeholder="چطور یک موتور گردش کار دیگر را به آوان وصل کنم؟";
 const output=el("div");output.setAttribute("aria-live","polite");
 const send=link("دریافت پاسخ",async()=>{if(app.sending)return;app.sending=true;send.disabled=true;output.replaceChildren(note("در حال بررسی سؤال..."));
  try{const result=await request("/api/platform/ask",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({question:question.value,new_conversation:app.newConversation,conversation_id:app.conversationId})});if(!output.isConnected)return;app.newConversation=false;app.conversationId=result.conversation_id;output.replaceChildren();renderAnalysis(output,result)}catch(e){output.replaceChildren(note(e.message,true))}finally{app.sending=false;send.disabled=false}},"button primary");
 const fresh=link("گفت‌وگوی تازه",()=>{app.newConversation=true;app.conversationId=null;question.value="";output.replaceChildren();question.focus()});
 add(work,question,send,fresh);if(status.voice_enabled)attachVoiceInput(work,question,true);
 if(!status.enabled)add(work,note("برای استفاده از دستیار، مدل AI را در تنظیمات GodAdmin فعال کنید."));
 add(work,output);add(m,work);
 const past=card("گفت‌وگوهای پلتفرم","گفت‌وگوهای قبلی اطلاعات روز را جایگزین نمی‌کنند.");
 for(const c of history.conversations){const row=el("div","history-item");add(row,link(c.title,async()=>{try{const detail=await request("/api/platform/conversations/"+encodeURIComponent(c.id));app.conversationId=c.id;app.newConversation=false;output.replaceChildren();for(const t of detail.turns){const p=card(t.question,dateText(t.created_at));renderAnalysis(p,{...t.answer,conversation_id:c.id,turn_id:t.id});add(output,p)}}catch(e){toast(e.message)}},"history-title"),link("حذف",async()=>{try{await request("/api/platform/conversations/"+encodeURIComponent(c.id)+"/delete",{method:"POST"});row.remove();if(app.conversationId===c.id){app.conversationId=null;app.newConversation=true;output.replaceChildren()}}catch(e){toast(e.message)}},"link-button"));add(past,row)}
 if(!history.conversations.length)add(past,el("p","muted","هنوز گفت‌وگویی ثبت نشده است."));add(m,past);
}

async function platformBI(){
 const status=await request("/api/platform/status");if(app.page!=="platform-bi")return;app.voiceEnabled=status.voice_enabled;
 const m=root();heading(m,"گزارش BPMSهای متصل","اطلاعات هر موتور فقط از آداپتر همان منبع و در دامنه سازمان تنظیم‌شده دریافت می‌شود.");
 const enabled=status.sources.filter(s=>s.enabled);
 if(!enabled.length){const settings=link("افزودن اتصال در مدیریت سامانه",()=>select("system-management"),"button primary");add(m,note("هنوز هیچ مبدل خواندنی AVAN REST v1 فعال نشده است."),settings);return}
 const p=card("انتخاب منبع و بازه"),source=el("select"),period=el("select"),out=el("div"),analysis=card("تحلیل زبان طبیعی","مدل فقط به گزارش منبع انتخابی دسترسی دارد.");
 source.setAttribute("aria-label","منبع BPMS");period.setAttribute("aria-label","بازه گزارش");
 for(const s of enabled){const opt=el("option","",s.name);opt.value=s.id;add(source,opt)}
 for(const [key,label] of [["last_30_days","۳۰ روز گذشته"],["last_7_days","۷ روز گذشته"],["this_month","ماه جاری"],["last_month","ماه قبل"],["all","تمام زمان‌ها"]]){const opt=el("option","",label);opt.value=key;add(period,opt)}
 add(p,add(el("label"),el("span","","منبع"),source)," ",add(el("label"),el("span","","بازه"),period));
 const table=(labels,rows)=>{const t=el("table"),head=el("tr");for(const label of labels)add(head,el("th","",label));add(t,add(el("thead"),head));const body=el("tbody");for(const values of rows){const row=el("tr");for(const val of values)add(row,el("td","",val??"—"));add(body,row)}add(t,body);return add(el("div","table-scroll panel"),t)};
 const load=link("نمایش گزارش",async()=>{load.disabled=true;out.replaceChildren(note("در حال دریافت گزارش..."));try{const r=await request("/api/platform/bpms/report",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({source_id:source.value,period:period.value,limit:30})});if(!out.isConnected)return;out.replaceChildren();add(out,note("زمان استخراج: "+dateText(r.as_of_utc)+(r.coverage_complete?"":" · پوشش داده ناقص است.")));
  const stats=el("div","stats");for(const [key,label] of [["cases","کل پرونده"],["open_cases","باز"],["completed_cases","تکمیل‌شده"],["open_tasks","وظایف باز"],["overdue_tasks","وظایف تأخیردار"]])add(stats,add(el("div","stat"),el("span","",label),el("strong","",fmt(r.metrics[key]))));add(out,stats);
  add(out,table(["فرایند","کل","باز","تکمیل","وظایف تأخیردار"],r.processes.map(x=>[x.title,fmt(x.total),fmt(x.open),fmt(x.completed),fmt(x.overdue_tasks)])));
  add(out,table(["شماره پرونده","فرایند","وضعیت","ثبت"],r.rows.map(x=>[x.case_number,x.process_title,statusName(x.status),dateText(x.created_at)])));
  if(r.has_more)add(out,note("فهرست پرونده‌ها صفحه‌بندی شده است؛ برای ادامه بازه را محدود کنید."));
 }catch(e){out.replaceChildren(note(e.message,true))}finally{load.disabled=false}},"button primary");add(p,load,out);add(m,p);
 const question=el("textarea");question.maxLength=2000;question.rows=3;question.setAttribute("aria-label","سؤال درباره گزارش BPMS");question.placeholder="کدام فرایندها بیشترین وظایف تأخیردار را دارند؟";
 const result=el("div");const ask=link("تحلیل منبع انتخابی",async()=>{ask.disabled=true;result.replaceChildren(note("در حال تحلیل..."));try{const r=await request("/api/platform/bpms/ask",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({question:question.value,source_id:source.value,new_conversation:true})});if(result.isConnected){result.replaceChildren();renderAnalysis(result,r)}}catch(e){result.replaceChildren(note(e.message,true))}finally{ask.disabled=false}},"button primary");
 add(analysis,question,ask);if(status.voice_enabled)attachVoiceInput(analysis,question,true);if(!status.enabled)add(analysis,note("برای تحلیل متنی، اتصال مدل AI را فعال کنید."));add(analysis,result);add(m,analysis);
}


function renderAnalysis(target,result,sourceId=null){
 if(app.voiceEnabled&&result.conversation_id&&result.turn_id)attachSpeech(target,result,sourceId);
 for(const message of result.notes||[])add(target,note(message));
 add(target,el("p","muted","مدل: "+(result.model||"—")+(result.report_type==="platform"?" · راهنمای پلتفرم":result.report_type==="bpms_bi"||result.report_type==="process_bi"?" · تحلیل گردش کار فرایندها":" · بررسی "+fmt(result.meetings_considered)+" جلسه و "+fmt(result.actions_considered)+" اقدام")));
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
   for(const p of data.processes||[])add(d,el("p","",p.title+": "+fmt(p.total)+" پرونده، "+fmt(p.overdue_tasks)+" وظیفه تأخیردار"));
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
async function secretaryPage(sourceId=null,packId=null,sectionId="inbox",initialManifest=null){
 const m=root();heading(m,"کارتابل دبیر هوشمند","دعوت‌نامه، تأیید رئیس، صورتجلسه، اجرای اقدام و پایش در فرایند متصل BPMS");
 if(!sourceId){add(m,note("اتصال BPMS را از منوی کنار انتخاب کنید."));return}
 const base=sourceApi(sourceId,"/secretary"),out=el("div"),editor=el("div");add(m,out,editor);
 const post=(path,body={})=>request(base+path,{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(body)});
 const checked=fn=>async()=>{try{await fn()}catch(e){toast(e.message)}};
 let info;
 async function load(){
  if(packId){
   let manifest;
   try{manifest=initialManifest||await request(sourceApi(sourceId,"/process-workspace/"+packId+"?section="+encodeURIComponent(sectionId)),{background:true})}catch(e){
    if(e.status!==403||sectionId==="inbox")throw e;
    manifest=await request(sourceApi(sourceId,"/process-workspace/"+packId),{background:true});
    if(app.selectedSourceId===sourceId&&app.processChoices[sourceId]?.packId===packId&&app.processChoices[sourceId]?.section===sectionId){app.processChoices[sourceId].section=manifest.section;select("source-process")}return;
   }initialManifest=null;
   refreshProcessMenu(sourceId,manifest);
   if(!m.isConnected||app.selectedSourceId!==sourceId||app.processChoices[sourceId]?.packId!==packId||app.processChoices[sourceId]?.section!==sectionId)return;
   const personal=await request(base+"/inbox?pack_id="+packId,{background:true});
   info={...manifest,...personal,tasks:manifest.tasks,notifications:manifest.notifications,sessions:manifest.sessions,packs:[manifest.process]};
  }else info=await request(base+"/inbox",{background:true});
  if(!m.isConnected||(packId&&(app.selectedSourceId!==sourceId||app.processChoices[sourceId]?.packId!==packId||app.processChoices[sourceId]?.section!==sectionId)))return;
  out.replaceChildren();const top=card(info.packs[0]?.title||"فرایندهای فعال","کارتابل فقط برای فرایند و بخش انتخاب‌شده است.");
  if(!info.packs.length)add(top,note("بسته فرایند فعال نشده است."));
  const currentPack=packId||info.packs[0]?.id;
  if(sectionId==="drafts"||!packId){const create=link("شروع جلسه با دبیر هوشمند",checked(async()=>{const r=await post("/sessions",{pack_id:currentPack});await session(r.id)}),"button primary");create.disabled=!currentPack;add(top,create);if(currentPack&&!info.oauth_connected)add(top,el("small","muted","می‌توانید پیش‌نویس را با متن، صوت و فایل کامل کنید؛ برای ایجاد واقعی پرونده و ارسال به رئیس، اتصال شخصی ProcessMaker لازم است."))}
  add(top,link("تازه‌سازی کارتابل",checked(load)),link("فعال‌سازی اعلان‌های پس‌زمینه",checked(async()=>{await post("/subscribe");toast("پایش کارتابل فعال شد؛ نیازمند اعتبار نشست سازمانی است.")})));
  add(out,top);
  const connection=card("مجوز عملیات حساب BPMS",info.oauth_connected?"مجوز شخصی حساب متصل فعال است.":"برای ثبت و انتقال مراحل، مجوز حساب خودتان در ProcessMaker لازم است.");
  if(info.oauth_connected)add(connection,link("قطع مجوز شخصی",checked(async()=>{await post("/oauth/disconnect");await load()})));
  else{
   const fields=[inputField("نام کاربری ProcessMaker",""),inputField("رمز ProcessMaker","","password"),inputField("OAuth Client ID",""),inputField("OAuth Client Secret","","password")];for(const f of fields)add(connection,f.wrap);
   add(connection,link("اتصال حساب خودم",checked(async()=>{await post("/oauth/connect",{username:fields[0].input.value,password:fields[1].input.value,client_id:fields[2].input.value,client_secret:fields[3].input.value});fields[1].input.value="";fields[3].input.value="";await load()})));
  }add(out,connection);
  const notices=card("اعلان‌ها",String(info.notifications.filter(n=>!n.read).length)+" اعلان خوانده‌نشده");
  for(const n of info.notifications)add(notices,link((n.read?"":"● ")+n.task.stage_label+" · "+n.task.title,checked(async()=>{await post("/notifications/"+n.id+"/read");await open(n.task)})));
  if(!info.notifications.length)add(notices,note("اعلان جاری ندارید."));add(out,notices);
  const tasks=card("وظایف من","تأیید و ارسال فقط پس از بازبینی شما انجام می‌شود.");
  for(const t of info.tasks){const b=link(t.stage_label+" · "+t.title+" · "+t.number,checked(()=>open(t,!!info.oauth_connected)));b.disabled=!t.available;add(tasks,b);if(!info.oauth_connected)add(tasks,el("small","muted","مشاهده و شنیدن خلاصه آزاد است؛ برای ثبت تصمیم و انتقال مرحله، اتصال شخصی ProcessMaker لازم است."));if(!t.available)add(tasks,el("small","muted",t.reminder_at?("پایش از "+t.reminder_at+" فعال می‌شود."):"تاریخ و ساعت پایان برنامه‌ریزی در BPMS باید تکمیل شود."))}
  if(info.truncated)add(tasks,note("بیش از ۲۰۰ وظیفه جاری دارید؛ همه موارد در این صفحه نمایش داده نشده‌اند."));if(!info.tasks.length)add(tasks,note("وظیفه جاری ندارید."));add(out,tasks);
  const drafts=card("پیش‌نویس‌های فرایند","ادامه پیش‌نویس یا مشاهده وضعیت دعوت‌نامه");for(const r of info.sessions)add(drafts,link(r.title+" · "+r.status,checked(()=>session(r.id))));add(out,drafts);
 }
 async function open(t,prepare=true){const r=await post(prepare?"/tasks/open":"/tasks/load",{case_uid:t.case_uid,index:t.index,pack_id:t.pack_id});render(r,false)}
 async function session(id){const r=await request(base+"/sessions/"+encodeURIComponent(id));render({...r,draft:r.session,task:{stage:"invitation",title:r.session.values.MTG_MeetingTitle||"جلسه جدید"}},true)}
 function render(r,isSession){
  editor.replaceChildren();
  const d=r.draft,t=r.task,values=structuredClone(d.values||{}),assistant=r.assistant||{},p=card(t.title||"دبیر هوشمند",isSession?"ایجاد دعوت‌نامه با گفت‌وگو":"مرحله: "+t.stage);
  const path=isSession?"/sessions/"+encodeURIComponent(d.id):"/tasks/"+t.case_uid+"/"+t.index;
  const query=isSession?"":"?pack_id="+encodeURIComponent(t.pack_id);
  const status=el("div"),controls=[],locked=d.status!=="draft";let dirty=false;
  let send;
  function changed(){dirty=true;if(send)send.disabled=true;status.replaceChildren(note("تغییرات فرم ذخیره نشده‌اند؛ ابتدا ذخیره کنید."))}
  function control(key,spec,value,change){
   const label=spec.label||key,wrap=el("label","field");add(wrap,el("span","",label));let input;
   let options=spec.options||[];
   if(key.endsWith("UID"))options=(r.people||[]).map(x=>({value:x.uid,label:x.name}));
   if(key==="MTG_InvitationApproval"||key==="MTG_MinutesApproval")options=[{value:"Approved",label:"تأیید"},{value:"NeedsRevision",label:"نیاز به اصلاح"}];
   if(options.length){input=el("select");add(input,el("option","","انتخاب کنید"));for(const x of options){const o=el("option","",x.label||x.value);o.value=x.value;add(input,o)}input.value=value||""}
   else{input=el(spec.type==="textarea"?"textarea":"input");input.value=value??"";input.maxLength=14000}
   input.setAttribute("aria-label",label);input.disabled=locked||key==="MTG_MonActionNo";input.addEventListener("input",()=>{change(input.value);changed()});add(wrap,input);controls.push(input);return wrap;
  }

  const conversation=card("گفت‌وگو با دبیر هوشمند","متن، صوت یا فایل بدهید؛ دبیر اطلاعات PMX را استخراج می‌کند و فقط موارد ناقص را می‌پرسد.");
  conversation.classList.add("secretary-conversation");
  const chat=el("div","secretary-chat");
  const history=d.history||[];
  if(history.length){
   for(const turn of history){
    const bubble=el("div","chat-bubble "+(turn.role==="user"?"user":"assistant"));
    add(bubble,el("small","",turn.role==="user"?(turn.source==="file"?"فایل شما":"شما"):"دبیر هوشمند"),el("div","",turn.text||""));
    if(turn.summary)add(bubble,el("pre","chat-summary",turn.summary));
    add(chat,bubble);
   }
  }else if(assistant.message){
   const bubble=el("div","chat-bubble assistant");add(bubble,el("small","","دبیر هوشمند"),el("div","",assistant.message));add(chat,bubble);
  }
  if(assistant.summary){
   const summary=el("div","secretary-invitation-summary");
   add(summary,el("strong","",["invitation_approval","minutes_approval"].includes(t.stage)?"خلاصه برای تصمیم شما":"خلاصه اطلاعات فعلی"),el("pre","",assistant.summary));
   add(conversation,summary);
  }
  add(conversation,chat);

  const missing=assistant.missing||r.missing||[];
  if(missing.length){
   const gaps=el("div","secretary-missing");add(gaps,el("strong","","اطلاعاتی که هنوز لازم است"));
   for(const item of missing)add(gaps,el("p","",item.question||item));
   add(conversation,gaps);
  }

  const composer=el("div","secretary-composer"),notes=inputField("پیام به دبیر هوشمند","","textarea");
  notes.input.maxLength=18000;notes.input.rows=4;
  notes.input.placeholder=isSession?"مثلاً: فردا ساعت ۱۰ جلسه بررسی واردات در ساختمان جردن با ریاست ... برگزار شود.":"تصمیم، اصلاحات یا اطلاعات این مرحله را بنویسید...";
  add(composer,notes.wrap);
  const voiceAuto=el("input");voiceAuto.type="checkbox";
  const voiceAutoLabel=el("label","voice-auto");add(voiceAutoLabel,voiceAuto,el("span","","حالت دستیار صوتی؛ بعد از تبدیل صوت، پیام ارسال شود"));
  add(composer,voiceAutoLabel);

  async function detachedSpeech(){
   try{
    const speechQuery=isSession?"?part=0":query+"&part=0";
    const response=await request(base+path+"/speech"+speechQuery,{method:"POST",binary:true});
    const url=URL.createObjectURL(await response.blob()),player=new Audio(url);
    player.onended=()=>URL.revokeObjectURL(url);player.onerror=()=>URL.revokeObjectURL(url);
    await player.play();
   }catch(e){toast("پاسخ متنی آماده است؛ پخش خودکار صوت در مرورگر انجام نشد.")}
  }
  async function applyResult(result,fromVoice=false){
   if(result.advanced){
    editor.replaceChildren(note(result.assistant?.message||"پرونده به مرحله بعد منتقل شد."));
    await load();return
   }
   if(fromVoice)await detachedSpeech();
   if(isSession)render({...result,draft:result.session,task:result.task||{stage:"invitation",title:result.session?.values?.MTG_MeetingTitle||"جلسه جدید"}},true);
   else render(result,false);
  }
  async function sendTurn(textValue=null,fromVoice=false){
   if(locked)return;
   if(dirty)throw Error("ابتدا اصلاحات دستی فرم را ذخیره کنید.");
   const text=(textValue??notes.input.value).trim();if(!text)throw Error("متن یا صوتی برای ارسال وارد کنید.");
   const result=await post(path+"/turn"+query,{revision:d.revision,text,auto_advance:!!info.oauth_connected});
   await applyResult(result,fromVoice);
  }
  const sendMessage=link("ارسال به دبیر",checked(()=>sendTurn()),"button primary");add(composer,sendMessage);
  notes.input.addEventListener("keydown",e=>{if(e.key==="Enter"&&!e.shiftKey){e.preventDefault();sendTurn().catch(err=>toast(err.message))}});
  attachVoiceInput(composer,notes.input,false,sourceId,async text=>{if(voiceAuto.checked)await sendTurn(text,true)});

  const fileWrap=el("div","secretary-file-bar"),file=el("input");
  file.type="file";file.accept=".pdf,.docx,.txt,.md,.csv,.json,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document,text/plain,text/csv,application/json";
  file.setAttribute("aria-label","افزودن فایل به گفت‌وگوی دبیر");
  const fileStatus=el("small","muted","PDF متنی، DOCX، TXT، MD، CSV یا JSON تا ۸ مگابایت");
  async function uploadConversationFile(selected){
   if(!selected)return;
   if(dirty){fileStatus.textContent="ابتدا اصلاحات دستی فرم را ذخیره کنید.";file.value="";return}
   file.disabled=true;fileStatus.textContent="در حال خواندن و استخراج اطلاعات فایل...";
   try{
    const sep=query?"&":"?";
    const result=await request(base+path+"/attachment"+query+sep+"revision="+encodeURIComponent(d.revision),{
     method:"POST",
     headers:{"Content-Type":selected.type||"application/octet-stream","X-AVAN-Filename":encodeURIComponent(selected.name)},
     body:selected
    });
    await applyResult(result,false);
   }catch(e){fileStatus.textContent=e.message}finally{file.disabled=false}
  }
  file.addEventListener("change",()=>uploadConversationFile(file.files?.[0]));
  fileWrap.addEventListener("dragover",e=>{e.preventDefault();fileWrap.classList.add("dragging")});
  fileWrap.addEventListener("dragleave",()=>fileWrap.classList.remove("dragging"));
  fileWrap.addEventListener("drop",e=>{e.preventDefault();fileWrap.classList.remove("dragging");uploadConversationFile(e.dataTransfer?.files?.[0])});
  add(fileWrap,file,fileStatus);add(composer,fileWrap);

  if(["invitation_approval","minutes_approval"].includes(t.stage)){
   const quick=el("div","secretary-quick-actions");
   const approveText=t.stage==="invitation_approval"?"دعوت‌نامه را تأیید می‌کنم":"صورت‌جلسه را تأیید می‌کنم";
   const approve=link("✓ تأیید و ارسال",checked(()=>sendTurn(approveText)),"button primary");approve.disabled=!info.oauth_connected;
   add(quick,approve,link("↩ نیاز به اصلاح",()=>{notes.input.value="نیاز به اصلاح: ";notes.input.focus()},"button secondary"));
   add(composer,quick);
  }
  if(isSession&&!missing.length){
   const start=link("ایجاد گام اول و ارسال به رئیس",checked(()=>sendTurn("بله، ایجاد و ارسال کن")),"button primary");start.disabled=!info.oauth_connected;add(composer,start);
   if(!info.oauth_connected)add(composer,note("پیش‌نویس کامل است؛ برای ایجاد پرونده و ارسال آن به کارتابل رئیس، ابتدا «اتصال حساب خودم» را فعال کنید."));
  }

  const audio=el("audio");audio.controls=true;let audioPart=0,audioUrl=null;
  const audioStatus=el("small","muted","خلاصه و پاسخ دبیر به صورت صوتی");
  const speech=link("پخش پاسخ دبیر",checked(async()=>{
   if(dirty)throw Error("ابتدا اصلاحات دستی فرم را ذخیره کنید.");
   const speechQuery=isSession?("?part="+audioPart):(query+"&part="+audioPart);
   const response=await request(base+path+"/speech"+speechQuery,{method:"POST",binary:true});
   if(audioUrl)URL.revokeObjectURL(audioUrl);audioUrl=URL.createObjectURL(await response.blob());audio.src=audioUrl;
   const count=Number(response.headers.get("X-AVAN-Audio-Parts"))||1;audioStatus.textContent="پاسخ صوتی · بخش "+(audioPart+1)+" از "+count;audioPart=(audioPart+1)%count;await audio.play();
  }));
  add(composer,speech,audio,audioStatus);app.cleanup.push(()=>{audio.pause();if(audioUrl)URL.revokeObjectURL(audioUrl)});
  if((d.attachments||[]).length){
   const attachments=el("div","secretary-attachments");add(attachments,el("strong","","فایل‌های استفاده‌شده"));
   for(const a of d.attachments)add(attachments,el("span","badge",(a.name||"فایل")+" · "+(a.type||"")));
   add(composer,attachments);
  }
  add(conversation,composer);add(p,conversation);

  const formDetails=el("details","secretary-form-details"),formSummary=el("summary","","مشاهده / اصلاح فرم استخراج‌شده"),formBody=el("div","secretary-form-body");
  add(formDetails,formSummary,formBody);
  for(const [key,spec] of Object.entries(r.form||{})){
   if(spec.type==="grid"){
    const box=card(spec.label||key),rows=el("div");let data=values[key]&&typeof values[key]==="object"?values[key]:{};values[key]=data;
    function draw(){rows.replaceChildren();for(const [no,row] of Object.entries(data)){
     const item=card("ردیف "+no);for(const col of spec.columns||[])add(item,control(col.id,col,row[col.id]||"",v=>row[col.id]=v));
     if(key!=="MTG_ActionSummary")add(item,link("حذف ردیف",()=>{delete data[no];changed();draw()}));add(rows,item);
    }}draw();add(box,rows);
    if(key!=="MTG_ActionSummary"&&!locked)add(box,link("افزودن ردیف",()=>{const n=String(Math.max(0,...Object.keys(data).map(Number))+1);data[n]={};draw();changed()}));add(formBody,box);
   }else add(formBody,control(key,spec,values[key],v=>values[key]=v));
  }
  const context=el("details");add(context,el("summary","","شرح ثبت‌شده در فرایند"));
  for(const [k,v] of Object.entries(r.context||{})){const label=r.form?.[k]?.label||k;add(context,el("p","",label+": "+(typeof v==="object"?JSON.stringify(v):v)))}add(formBody,context);
  const save=link("ذخیره اصلاحات",checked(async()=>{await post(path+"/edit"+query,{revision:d.revision,values});if(isSession)await session(d.id);else await open(t,false)}));save.disabled=locked;
  send=link("تأیید بازبینی و ارسال به مرحله بعد",checked(async()=>{send.disabled=true;try{await post(path+"/submit"+query,{revision:d.revision,confirmed:true});editor.replaceChildren(note("اطلاعات در BPMS ثبت و به مرحله بعد ارسال شد."));await load()}finally{send.disabled=locked||dirty}}),"button primary");
  send.disabled=locked||missing.length>0||!info.oauth_connected;
  add(formBody,save,send,status);add(p,formDetails);

  if(!isSession&&t.stage==="monitoring")add(p,link("پیشنهاد جلسه پیگیری اقدامات باز",checked(async()=>{const row=await post(path+"/followup"+query);await session(row.id);await load()})));
  if(!isSession&&["action_review","monitoring"].includes(t.stage)){
   const evidence=card("اسناد و پیشنهاد بررسی","اسناد TXT و PDF دارای متن، با مجوز حساب BPMS شما خوانده می‌شوند. پیشنهاد هوش مصنوعی نیازمند تصمیم دبیر است."),list=el("div"),advice=el("div");
   add(evidence,link("دریافت اسناد پرونده",checked(async()=>{const docs=await post(path+"/documents"+query);list.replaceChildren();for(const doc of docs.documents)add(list,link(doc.app_doc_filename+" · نسخه "+doc.app_doc_version,checked(async()=>{if(dirty)throw Error("ابتدا اصلاحات را ذخیره کنید.");await post(path+"/evidence"+query,{revision:d.revision,doc_id:doc.app_doc_uid,version:Number(doc.app_doc_version)});await open(t,false)})));if(!docs.documents.length)add(list,note("سندی با مجوز فعلی در دسترس نیست؛ نبود سند به معنی تکمیل اقدام نیست."))})),list,
    link("پیشنهاد دبیر براساس گزارش و اسناد",checked(async()=>{const result=await post(path+"/advice"+query);advice.replaceChildren(el("p","",result.summary),note("پیشنهاد برای تصمیم شما: "+result.proposal),el("small","muted","تعداد اسناد خوانده‌شده: "+result.document_count));for(const q of result.quotes)add(advice,el("blockquote","",q));for(const q of result.missing)add(advice,note(q));})),advice);add(p,evidence);
  }
  if(d.status==="reconciliation_required")add(p,note("نتیجه عملیات نامشخص است؛ پرونده را در ProcessMaker بررسی کنید. ارسال خودکار تکرار نمی‌شود.",true));
  add(editor,p);editor.scrollIntoView({behavior:"smooth"});
 }
 await load();let busy=false;const timer=setInterval(async()=>{if(busy||!m.isConnected)return;busy=true;try{await load()}catch{}finally{busy=false}},60000);app.cleanup.push(()=>clearInterval(timer));
}
function inputField(label,value,type="text"){
 const wrap=el("label","field"),input=el(type==="textarea"?"textarea":"input");
 if(type!=="textarea")input.type=type;input.value=value??"";input.setAttribute("aria-label",label);add(wrap,el("span","",label),input);return {wrap,input};
}
function renderDraft(target,draft,sourceId=null){
 const payload=draft.payload,approved=draft.status==="approved",path=sourceApi(sourceId,"/secretary/drafts/"+encodeURIComponent(draft.id));
 const panel=card("بازبینی پیش‌نویس · نسخه "+fmt(draft.revision||1),"تأیید پیش‌نویس، اطلاعاتی در ProcessMaker ثبت نمی‌کند.");
 const summary=inputField("خلاصه جلسه",payload.summary,"textarea");summary.input.maxLength=3000;add(panel,summary.wrap);
 const actions=el("div"),editors=[],out=el("div");let dirty=false;
 function changed(){dirty=true;approve.disabled=true;out.replaceChildren(note("تغییرات ذخیره نشده‌اند؛ ابتدا ذخیره کنید."))}
 function actionEditor(a){
  const item=card("اقدام پیشنهادی"),fields={};
  for(const [key,label,type] of [["description","شرح اقدام","textarea"],["source_quote","عبارت مستند از متن اولیه","textarea"],["suggested_role","سمت پیشنهادی","text"],["owner_reason","دلیل انتخاب مسئول","text"],["proposed_due_date","موعد میلادی","date"],["due_reason","دلیل موعد پیشنهادی","text"]]){
   const f=inputField(label,a[key],type);fields[key]=f.input;add(item,f.wrap);
  }
  const owner=el("select"),priority=el("select");owner.setAttribute("aria-label","مسئول اقدام");priority.setAttribute("aria-label","اولویت اقدام");
  for(const x of [{uid:"",name:"نیازمند تعیین مسئول"},...(payload.candidate_owners||[])]){const o=el("option","",x.name||x.uid);o.value=x.uid;add(owner,o)}owner.value=a.owner_uid||"";
  for(const [v,t] of [["low","کم"],["normal","عادی"],["high","زیاد"],["urgent","فوری"]]){const o=el("option","",t);o.value=v;add(priority,o)}priority.value=a.priority;
  const clarify=el("input");clarify.type="checkbox";clarify.checked=a.needs_clarification;const l=el("label");add(l,clarify,el("span","","هنوز ابهام دارد"));
  add(item,el("label","","مسئول"),owner,el("label","","اولویت"),priority,l);
  const editor={item,read:()=>Object.fromEntries(Object.entries(fields).map(([k,v])=>[k,v.value||((k==="proposed_due_date")?null:"")]))};
  editor.value=()=>({...editor.read(),owner_uid:owner.value||null,priority:priority.value,needs_clarification:clarify.checked});editors.push(editor);
  if(!approved)add(item,link("حذف این اقدام",()=>{item.remove();changed()}));add(actions,item);
 }
 payload.actions.forEach(actionEditor);add(panel,actions);
 if(!approved)add(panel,link("افزودن اقدام مستند",()=>{if(editors.filter(e=>e.item.isConnected).length>=30){toast("حداکثر ۳۰ اقدام مجاز است.");return}actionEditor({description:"",source_quote:"",priority:"normal",needs_clarification:true});changed()}));
 for(const q of payload.questions||[])add(panel,note(q));
 const approve=link("تأیید نسخه ذخیره‌شده",async()=>{
  if(dirty||!check.checked){out.replaceChildren(note("نسخه ذخیره‌شده را بازبینی و تأیید کنید.",true));return}approve.disabled=true;
  try{const r=await request(path+"/approve",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({confirmed:true,revision:draft.revision||1})});target.replaceChildren();renderDraft(target,r,sourceId)}catch(e){out.replaceChildren(note(e.message,true));approve.disabled=false}
 },"button primary");
 const check=el("input");check.type="checkbox";const consent=el("label");add(consent,check,el("span","","این نسخه را بازبینی کرده‌ام."));
 if(!approved){const save=link("ذخیره اصلاحات",async()=>{save.disabled=true;try{
   const r=await request(path+"/edit",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({revision:draft.revision||1,payload:{summary:summary.input.value,actions:editors.filter(e=>e.item.isConnected).map(e=>e.value()),questions:payload.questions||[]}})});target.replaceChildren();renderDraft(target,r,sourceId);
  }catch(e){out.replaceChildren(note(e.message,true))}finally{save.disabled=false}},"button primary");add(panel,save,consent,approve);
  panel.addEventListener("input",e=>{if(e.target!==check)changed()});panel.addEventListener("change",e=>{if(e.target!==check)changed()});
 }else{
  panel.querySelectorAll("input,textarea,select").forEach(x=>x.disabled=true);add(panel,note("پیش‌نویس تأیید شده؛ هنوز در ProcessMaker ثبت نشده است."));
  for(const [suffix,title,filename] of [["export","دریافت پیش‌نویس کامل","meeting-actions.json"],["processmaker","دریافت ردیف‌های فرم ProcessMaker","processmaker-actions.json"]])add(panel,link(title,async()=>{try{downloadJson(await request(path+"/"+suffix),filename)}catch(e){out.replaceChildren(note(e.message,true))}},"button primary"));
  add(panel,link("بازگشایی برای اصلاح",async()=>{try{const r=await request(path+"/reopen",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({confirmed:true,revision:draft.revision||1})});target.replaceChildren();renderDraft(target,r,sourceId)}catch(e){out.replaceChildren(note(e.message,true))}}));
 }
 add(panel,out);add(target,panel);
}
async function monitorPage(sourceId=null){
 const scoped=!!sourceId;
 const source=scoped?(app.user?.bpms_sources||[]).find(x=>x.source_id===sourceId):null;
 const m=root();
 if(scoped&&(!source||!(source.capabilities||[]).includes("monitor"))){
  add(m,note("پایش برای این BPMS و لایسنس فعلی فعال نیست.",true));return
 }
 heading(m,scoped?("هشدار و پیگیری · "+source.source_name):"هشدار و پیگیری",
  scoped?"هشدارها، Baseline و Subscription فقط برای همین BPMS نگهداری می‌شوند.":"موعد نزدیک، تأخیر، توقف پیشرفت و اقدامات نیازمند پیگیری");
 if(!app.user.modules.includes(4)){add(m,note("ماژول پایش در لایسنس فعال نیست."));return}
 const monitorBase=sourceApi(sourceId,"/monitor");
 const control=card("پایش پس‌زمینه","پس از فعال‌سازی، با بستن مرورگر هم ادامه می‌یابد؛ حداکثر ۳۰ روز و تا زمانی که سرویس هویت اجازه تمدید بدهد. در هر نوبت مجوزها دوباره بررسی می‌شوند.");
 const interval=inputField("فاصله بررسی (دقیقه)",5,"number");interval.input.min=5;interval.input.max=1440;const state=el("div"),out=el("div"),results=el("div");let running=false;
 const hide=el("input");hide.type="checkbox";const filter=el("label");add(filter,hide,el("span","","پنهان‌کردن هشدارهای دیده‌شده"));
 async function refresh(background=false){
  if(running||app.page!==(scoped?"source-monitor":"monitor"))return;running=true;if(app.monitorTimer)clearTimeout(app.monitorTimer);
  try{const r=await request(monitorBase,{method:"POST",background});if(!results.isConnected)return;results.replaceChildren();
   const subscription=r.subscription||{};state.replaceChildren(note(subscription.enabled?"پایش فعال است. آخرین بررسی پس‌زمینه: "+(subscription.last_run?dateText(subscription.last_run*1000):"در انتظار اجرا"):"پایش پس‌زمینه غیرفعال است."));
   if(subscription.last_error)add(state,note(({login_required:"مجوز تمدید پایان یافته؛ دوباره وارد شوید و پایش را فعال کنید.",access_denied:"دسترسی تغییر کرده و پایش متوقف شده است.",source_unavailable:"منبع داده موقتاً در دسترس نیست؛ بررسی دوباره انجام می‌شود."})[subscription.last_error]||"پایش نیازمند بررسی است.",true));
   add(results,note(fmt(r.total)+" هشدار · "+dateText(r.as_of_utc)));
   if(!r.coverage_complete||r.truncated)add(results,note("پوشش داده یا فهرست نمایش کامل نیست."));
   for(const a of r.alerts){if(hide.checked&&a.acknowledged)continue;
    const item=card(a.severity==="high"?"پیگیری فوری":"پیگیری",a.reason);add(item,el("p","",a.description),el("p","","جلسه "+a.source.meeting_no+" · اقدام "+a.source.action_no+" · "+(a.owner_name||"مسئول نامشخص")),el("small","muted","اولین مشاهده: "+dateText(a.first_seen)));
    if(a.acknowledged)add(item,el("span","badge","دیده‌شده"));else add(item,link("دیده شد",async()=>{try{await request(monitorBase+"/alerts/"+a.id+"/acknowledge",{method:"POST"});await refresh()}catch(e){toast(e.message)}}));
    add(item,link("مشاهده جلسه",()=>scoped?showSourceMeeting(sourceId,a.source.meeting_id):showMeeting(a.source.meeting_id)),link("متن یادآوری",()=>{const t=el("textarea");t.readOnly=true;t.value="یادآوری اقدام "+a.source.action_no+" جلسه "+a.source.meeting_no+": "+a.description+". لطفاً وضعیت پیشرفت، موانع و زمان تکمیل را در فرایند ثبت کنید.";add(item,t);t.select()}));add(results,item)
   }
   for(const n of r.notes||[])add(results,note(n));if(!r.total)add(results,note("در دامنه بررسی‌شده هشداری مشاهده نشد."));
  }catch(e){results.replaceChildren(note(e.message,true))}finally{running=false;if(app.page===(scoped?"source-monitor":"monitor"))app.monitorTimer=setTimeout(()=>refresh(true),60000)}
 }
 async function subscribe(enabled){try{await request(monitorBase+"/subscribe",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({enabled,interval_seconds:Number(interval.input.value)*60})});out.replaceChildren(note(enabled?"پایش پس‌زمینه فعال شد.":"پایش متوقف شد."));await refresh()}catch(e){out.replaceChildren(note(e.message,true))}}
 hide.addEventListener("change",refresh);add(control,interval.wrap,link("فعال‌سازی پایش",()=>subscribe(true),"button primary"),link("توقف پایش",()=>subscribe(false)),link("بررسی اکنون",refresh),filter,state,out);add(m,control,results);await refresh();
}
function dateText(value){if(!value)return "ثبت نشده";const d=new Date(value);return Number.isNaN(d.getTime())?String(value):new Intl.DateTimeFormat("fa-IR",{dateStyle:"medium",timeStyle:"short"}).format(d)}
function downloadJson(data,name){const url=URL.createObjectURL(new Blob([JSON.stringify(data,null,2)],{type:"application/json;charset=utf-8"}));const a=el("a");a.href=url;a.download=name;document.body.append(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(url),1000)}
async function showMeeting(id){
 try{const meeting=await request("/api/meetings/"+id);cleanMedia();if(app.monitorTimer)clearTimeout(app.monitorTimer);app.page="detail";
  const m=root();heading(m,meeting.title,"جلسه "+meeting.meeting_no+" · "+dateText(meeting.meeting_date_utc));
  add(m,link("بازگشت به جلسات",()=>select("meetings")),link("تحلیل این جلسه",()=>{app.pendingQuestion="وضعیت و ریسک اقدامات جلسه شماره "+meeting.meeting_no+" را تحلیل کن";select("assistant")},"button primary"));
  if(meeting.discussion)add(m,card("خلاصه مباحث",meeting.discussion));if(meeting.parking_lot)add(m,card("موضوعات باز",meeting.parking_lot));
  const table=el("table"),head=el("tr");for(const x of ["اقدام","شرح","مسئول / واحد","وضعیت","پیشرفت","موعد"])add(head,el("th","",x));add(table,add(el("thead"),head));const body=el("tbody");
  for(const a of meeting.actions){const row=el("tr");for(const v of [a.action_no,a.description,(a.owner_name||"نامشخص")+" / "+(a.owner_unit||"نامشخص"),a.is_closed?"بسته‌شده":a.status,a.progress_percent==null?"نامشخص":fmt(a.progress_percent)+"٪",dateText(a.due_at_utc)])add(row,el("td","",v));add(body,row)}add(table,body);add(m,add(el("div","table-scroll panel"),table));
 }catch(e){toast(e.message)}
}
function attachVoiceInput(target,input,platform=false,sourceId=null,onTranscript=null){
 const wrap=el("div","voice-bar"),status=el("span","muted");let recorder=null,stream=null,timer=null,discard=false,busy=false;
 const cleanup=()=>{discard=true;if(timer)clearTimeout(timer);if(recorder?.state==="recording")recorder.stop();stream?.getTracks().forEach(t=>t.stop())};app.cleanup.push(cleanup);
 async function convert(blob){
  if(busy||discard)return;if(blob.size>8*1024*1024){status.textContent="حداکثر حجم صوت ۸ مگابایت است.";return}busy=true;button.disabled=true;upload.disabled=true;status.textContent="در حال تبدیل صوت؛ سپس متن را بازبینی کنید...";
  try{const endpoint=platform?"/api/platform/voice/transcribe":sourceApi(sourceId,"/voice/transcribe");
   const r=await request(endpoint,{method:"POST",headers:{"Content-Type":blob.type||"audio/mpeg"},body:blob});if(!input.isConnected)return;
   if(r.text.length>input.maxLength){status.textContent="متن از ظرفیت این کادر بیشتر است؛ فایل کوتاه‌تری انتخاب کنید.";return}input.value=r.text;input.dispatchEvent(new Event("input",{bubbles:true}));status.textContent="متن آماده است؛ قبل از ارسال بازبینی کنید.";
   if(onTranscript)await onTranscript(r.text);
  }catch(e){status.textContent=e.message}finally{busy=false;button.disabled=false;upload.disabled=false}
 }
 const button=link("ضبط سؤال / یادداشت",async()=>{
  if(recorder?.state==="recording"){recorder.stop();return}
  if(!window.isSecureContext||!navigator.mediaDevices?.getUserMedia||!window.MediaRecorder){status.textContent="ضبط به HTTPS یا localhost نیاز دارد؛ می‌توانید فایل صوت انتخاب کنید.";return}
  try{stream=await navigator.mediaDevices.getUserMedia({audio:true});if(discard){stream.getTracks().forEach(t=>t.stop());return}
   const mime=["audio/webm;codecs=opus","audio/mp4"].find(x=>MediaRecorder.isTypeSupported(x));if(!mime)throw Error("قالب ضبط مرورگر پشتیبانی نمی‌شود؛ فایل صوت انتخاب کنید.");
   recorder=new MediaRecorder(stream,{mimeType:mime});const chunks=[];recorder.ondataavailable=e=>{if(e.data.size)chunks.push(e.data)};
   recorder.onstop=()=>{clearTimeout(timer);stream.getTracks().forEach(t=>t.stop());button.textContent="ضبط سؤال / یادداشت";if(!discard)convert(new Blob(chunks,{type:mime.split(";")[0]}))};
   recorder.start();button.textContent="پایان ضبط و تبدیل";status.textContent="در حال ضبط؛ حداکثر ۹۰ ثانیه";timer=setTimeout(()=>{if(recorder.state==="recording")recorder.stop()},90000);
  }catch(e){stream?.getTracks().forEach(t=>t.stop());status.textContent=e.message}
 });
 const upload=el("input");upload.type="file";upload.accept="audio/webm,audio/ogg,audio/wav,audio/mpeg,audio/mp4,.m4a";upload.setAttribute("aria-label","انتخاب فایل صوت برای تبدیل به متن");upload.addEventListener("change",()=>{if(upload.files[0])convert(upload.files[0])});
 add(wrap,button,upload,el("small","muted","برای تبدیل، صوت انتخابی به سرویس هوش مصنوعی ارسال می‌شود."),status);add(target,wrap);
}
function attachSpeech(target,result,sourceId=null){
 const area=el("div","voice-bar"),status=el("span","muted","صدای تولیدشده توسط هوش مصنوعی"),player=el("audio");player.controls=true;let part=0,parts=1,url=null;
 app.cleanup.push(()=>{player.pause();player.removeAttribute("src");if(url)URL.revokeObjectURL(url)});
 const play=link("شنیدن پاسخ",async()=>{play.disabled=true;try{
  const endpoint=result.report_type==="platform"?"/api/platform/voice/speech":sourceApi(sourceId,"/voice/speech");
  const response=await request(endpoint,{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({conversation_id:result.conversation_id,turn_id:result.turn_id,part}),binary:true});
  const blob=await response.blob();if(!area.isConnected)return;if(url)URL.revokeObjectURL(url);url=URL.createObjectURL(blob);player.src=url;parts=Number(response.headers.get("X-AVAN-Audio-Parts"))||1;status.textContent="صدای هوش مصنوعی · بخش "+fmt(part+1)+" از "+fmt(parts);add(area,player);await player.play();
  part=(part+1)%parts;play.textContent=parts>1?"شنیدن بخش "+fmt(part+1):"پخش دوباره";
 }catch(e){status.textContent=e.message}finally{play.disabled=false}});add(area,play,status);add(target,area);
}

async function reportsPage(sourceId=null){
 const scoped=!!sourceId;
 const source=scoped?(app.user?.bpms_sources||[]).find(x=>x.source_id===sourceId):null;
 const m=root();
 if(scoped&&(!source||!(source.capabilities||[]).includes("reports"))){
  add(m,note("گزارش اقدامات برای این BPMS و لایسنس فعلی فعال نیست.",true));return
 }
 heading(m,scoped?("گزارش اقدامات · "+source.source_name):"گزارش اقدامات",
  scoped?"فیلتر، مقایسه و CSV فقط از دامنه همین BPMS تهیه می‌شود.":"فیلتر، مقایسه عملکرد و خروجی CSV از داده‌های مجاز جاری");
 if(!app.user.modules.includes(3)){add(m,note("ماژول گزارش‌گیری در لایسنس فعال نیست."));return}
 const reportBase=sourceApi(sourceId,"/reports/actions");
 const panel=card("فیلتر گزارش"),filters=el("div","report-filters"),result=el("div"),controls={};let offset=0,lastQuery=null;
 for(const [key,label,options] of [["status","وضعیت",[["all","همه"],["open","باز"],["closed","بسته‌شده"],["overdue","تأخیردار"],["due_soon","موعد نزدیک"]]],
  ["period","بازه",[["all","همه زمان‌ها"],["this_month","ماه جاری شمسی"],["last_month","ماه قبل شمسی"],["last_30_days","۳۰ روز گذشته"],["last_7_days","۷ روز گذشته"]]],
  ["date_field","مبنای تاریخ",[["meeting","تاریخ جلسه"],["due","موعد اقدام"]]],
  ["group_by","مقایسه",[["unit","واحد"],["owner","مسئول"],["meeting","جلسه"],["none","بدون گروه‌بندی"]]]]){
  const select=el("select"),labelEl=el("label");select.setAttribute("aria-label",label);for(const [v,t] of options){const option=el("option","",t);option.value=v;add(select,option)}controls[key]=select;add(labelEl,el("span","",label),select);add(filters,labelEl)
 }
 for(const [key,label] of [["meeting_no","شماره جلسه"],["owner","مسئول"],["unit","واحد"]]){const f=inputField(label,"");controls[key]=f.input;add(filters,f.wrap)}
 const query=()=>Object.fromEntries(Object.entries(controls).map(([k,v])=>[k,v.value||null]));
 async function load(reset=true){if(reset)offset=0;result.replaceChildren(note("در حال تهیه گزارش..."));try{
  lastQuery=query();const r=await request(reportBase,{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({...lastQuery,offset,limit:30})});if(!result.isConnected)return;result.replaceChildren();
  const stats=el("div","stats");for(const [label,value] of [["کل اقدامات",r.metrics.total],["باز",r.metrics.open],["تأخیردار",r.metrics.overdue]])add(stats,add(el("div","stat"),el("span","",label),el("strong","",fmt(value))));add(result,stats);
  if(!r.coverage_complete)add(result,note("پوشش داده ناقص است؛ آمار فقط مربوط به داده‌های بازیابی‌شده است."));
  for(const g of r.groups||[])add(result,el("p","",g.group.join(" · ")+": "+fmt(g.total)+" اقدام، "+fmt(g.overdue)+" تأخیردار"));
  const table=el("table"),head=el("tr");for(const label of ["جلسه / اقدام","شرح","مسئول","وضعیت","پیشرفت","موعد"])add(head,el("th","",label));add(head,el("th","","حذف"));add(table,head);
  for(const a of r.rows){const row=el("tr");for(const value of [a.source.meeting_no+" / "+a.source.action_no,a.description,a.owner_name,a.is_closed?"بسته‌شده":a.status,a.progress_percent==null?"نامشخص":fmt(a.progress_percent)+"٪",dateText(a.due_at_utc)])add(row,el("td","",value||"—"));add(table,row)}add(result,add(el("div","table-scroll"),table));
  if(offset>0)add(result,link("صفحه قبل",()=>{offset=Math.max(0,offset-30);load(false)}));if(r.has_more)add(result,link("صفحه بعد",()=>{offset+=30;load(false)}));
 }catch(e){result.replaceChildren(note(e.message,true))}}
 add(panel,filters,link("نمایش گزارش",()=>load(),"button primary"),link("دریافت CSV",async()=>{try{const r=await request(reportBase+"/export",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(query()),binary:true});const url=URL.createObjectURL(await r.blob()),a=el("a");a.href=url;a.download="meeting-actions.csv";document.body.append(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(url),1000)}catch(e){toast(e.message)}}));add(m,panel,result);await load();
}
async function biPage(sourceId=null){
 const source=sourceId?(app.user?.bpms_sources||[]).find(x=>x.source_id===sourceId):null;
 const scoped=!!sourceId;
 const m=root();
 heading(m,scoped?("BI · "+(source?.source_name||"ProcessMaker")):"BI همه فرایندها",
  scoped?"گزارش فقط از ProcessMaker انتخاب‌شده و Binding همین حساب خوانده می‌شود.":"نمای مشترک پرونده‌ها، حجم کار، تأخیر و زمان چرخه در ProcessMaker");
 if(!app.user.modules.includes(3)){add(m,note("ماژول BI در لایسنس فعال نیست."));return}
 if(scoped&&(!source||!(source.capabilities||[]).includes("bi"))){add(m,note("BI مستقیم این منبع برای Binding و لایسنس فعلی فعال نیست.",true));return}
 const biBase=scoped?("/api/sources/"+encodeURIComponent(sourceId)+"/bi"):"/api/bi";
 if(!scoped){
  const analysis=card("تحلیل مدیریتی همه فرایندها","سؤال درباره تأخیر مراحل، زمان چرخه و حجم کار مسئولان بپرسید.");const question=inputField("پرسش BI","کدام فرایندها بیشترین وظایف تأخیردار را دارند؟","textarea"),answer=el("div");question.input.maxLength=2000;
  const ask=link("تحلیل فرایندها",async()=>{ask.disabled=true;answer.replaceChildren(note("در حال تحلیل..."));try{const r=await request("/api/bi/ask",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({question:question.input.value})});answer.replaceChildren();renderAnalysis(answer,r)}catch(e){answer.replaceChildren(note(e.message,true))}finally{ask.disabled=false}},"button primary");add(analysis,question.wrap,ask,answer);add(m,analysis);
 }
 const panel=card("دامنه گزارش","فقط پرونده‌هایی که در دامنه مجاز شما هستند محاسبه می‌شوند."),controls=el("div","report-filters"),out=el("div");
 const process=el("select"),period=el("select");process.setAttribute("aria-label","فرایند BI");period.setAttribute("aria-label","بازه BI");
 const all=el("option","","همه فرایندها");all.value="";add(process,all);
 for(const [v,t] of [["last_30_days","۳۰ روز گذشته"],["this_month","ماه جاری شمسی"],["last_month","ماه قبل"],["all","همه زمان‌ها"]]){const o=el("option","",t);o.value=v;add(period,o)}
 const from=inputField("از تاریخ میلادی (اختیاری)","","date"),to=inputField("تا تاریخ میلادی (غیرشامل)","","date");
 add(controls,add(el("label"),el("span","","فرایند"),process),add(el("label"),el("span","","بازه"),period),from.wrap,to.wrap);
 let offset=0,known=new Set();const query=()=>({process_uid:process.value||null,period:period.value,start:from.input.value||null,end:to.input.value||null,offset,limit:30});
 function table(headers,rows){const t=el("table"),h=el("tr");headers.forEach(x=>add(h,el("th","",x)));add(t,h);for(const values of rows){const r=el("tr");values.forEach(x=>add(r,el("td","",x==null?"—":x)));add(t,r)}return add(el("div","table-scroll"),t)}
 function bars(title,rows){const p=card(title),max=Math.max(1,...rows.map(x=>x[1]));for(const [label,value] of rows){const r=el("div","bi-bar-row"),meter=el("meter");meter.min=0;meter.max=max;meter.value=value;meter.setAttribute("aria-label",label);add(r,el("span","",label),meter,el("strong","",fmt(value)));add(p,r)}return p}
 async function load(reset=true){if(reset)offset=0;out.replaceChildren(note("در حال خواندن اطلاعات گردش کار..."));try{const r=await request(biBase+"/processes",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(query())});if(!out.isConnected)return;out.replaceChildren();
  for(const p of r.processes){if(known.has(p.process_uid))continue;known.add(p.process_uid);const o=el("option","",p.title);o.value=p.process_uid;add(process,o)}
  const metrics=el("div","stats");for(const [key,label] of [["cases","کل پرونده"],["open_cases","پرونده باز"],["completed_cases","تکمیل‌شده"],["open_tasks","وظیفه باز"],["overdue_tasks","وظیفه تأخیردار"],["median_cycle_hours","میانه چرخه (ساعت)"]])add(metrics,add(el("div","stat"),el("span","",label),el("strong","",r.metrics[key]==null?"نامشخص":fmt(r.metrics[key]))));add(out,metrics);
  if(!r.coverage_complete)add(out,note("بیش از ۲۰هزار پرونده در دامنه وجود دارد؛ دوره را محدود کنید. آمار حاضر فقط زیرمجموعه بازیابی‌شده است.",true));
  const charts=el("div","bi-charts");add(charts,bars("وضعیت پرونده‌ها",Object.entries(r.statuses).map(([k,v])=>[statusName(k),v])),bars("پرونده‌های ایجادشده در ماه شمسی",r.monthly.map(x=>[x.month,x.count])));add(out,charts);
  const p=card("عملکرد فرایندها");add(p,table(["فرایند","کل","باز","تکمیل","وظیفه تأخیردار","میانگین چرخه ساعت"],r.processes.map(x=>[x.title,fmt(x.total),fmt(x.open),fmt(x.completed),fmt(x.overdue_tasks),x.average_cycle_hours==null?null:fmt(x.average_cycle_hours)])));add(out,p);
  const bottleneck=card("مراحل نیازمند بررسی","زمان انتظار از تخصیص تا شروع، و زمان کار از شروع تا پایان وظیفه محاسبه می‌شود.");add(bottleneck,table(["مرحله","باز","تأخیر","انتظار (ساعت)","کار (ساعت)"],r.tasks.map(x=>[x.title,fmt(x.open),fmt(x.overdue),x.average_wait_hours,x.average_work_hours])));add(out,bottleneck);
  const people=card("حجم کار مسئولان");add(people,table(["مسئول","واحد","کار باز","تأخیر"],r.owners.map(x=>[x.name,x.unit,fmt(x.open),fmt(x.overdue)])));add(out,people);
  const details=card("پرونده‌های دامنه گزارش");add(details,table(["شماره","فرایند","وضعیت","ایجاد","پایان"],r.rows.map(x=>[fmt(x.case_number),x.process_title,statusName(x.status),dateText(x.created_at),dateText(x.finished_at)])));if(offset)add(details,link("صفحه قبل",()=>{offset=Math.max(0,offset-30);load(false)}));if(r.has_more)add(details,link("صفحه بعد",()=>{offset+=30;load(false)}));add(out,details);
  r.notes.forEach(n=>add(out,note(n)));
 }catch(e){out.replaceChildren(note(e.message,true))}}
 add(panel,controls,link("نمایش BI",()=>load(),"button primary"),link("دریافت CSV فرایندها",async()=>{try{const r=await request(biBase+"/processes/export",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(query()),binary:true});const url=URL.createObjectURL(await r.blob()),a=el("a");a.href=url;a.download=scoped?"processmaker-source-bi.csv":"processmaker-bi.csv";document.body.append(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(url),1000)}catch(e){toast(e.message)}}));add(m,panel,out);await load();
}


function installSecretaryBadges(){
 if(app.secretaryTimer)clearInterval(app.secretaryTimer);
 let running=false;
 async function poll(){if(running||!app.user)return;running=true;const user=app.user;
  try{for(const source of user.bpms_sources||[]){if(!(source.capabilities||[]).includes("secretary"))continue;
   try{const box=await request(sourceApi(source.source_id,"/secretary/inbox"),{background:true});if(app.user!==user)return;
    const count=box.notifications.filter(x=>!x.read).length;for(const b of document.querySelectorAll('[data-page="source-secretary"]'))if(b.dataset.sourceId===source.source_id)b.textContent="▧  دبیر هوشمند"+(count?" · "+fmt(count):"");
   }catch{}}
  }finally{running=false}
 }
 poll();app.secretaryTimer=setInterval(poll,60000);
}

async function loadProcessChoices(source,group){
 const user=app.user,choice=el("select"),sections=el("div"),message=el("small","muted");choice.setAttribute("aria-label","فرایند · "+source.source_name);add(choice,el("option","","انتخاب فرایند..."));
 sections.dataset.processMenu=source.source_id;add(group,choice,message,sections);let serial=0;
 async function apply(openPage=true){const token=++serial;sections.replaceChildren();message.textContent="";const packId=choice.value;
  if(app.processChoices[source.source_id]?.packId!==packId){app.newConversation=true;app.conversationId=null}
  app.processChoices[source.source_id]={packId,section:"inbox"};if(!packId)return;
  try{const manifest=await request(sourceApi(source.source_id,"/process-workspace/"+encodeURIComponent(packId)),{background:true});if(token!==serial||app.user!==user||!group.isConnected)return;
   app.processManifests[source.source_id]=manifest;
   const saved=app.processChoices[source.source_id];saved.section=manifest.section;
   for(const section of manifest.navigation){const b=link(section.label+(section.count?" · "+fmt(section.count):""),()=>{app.selectedSourceId=source.source_id;saved.section=section.id;select("source-process")});b.dataset.page="source-process";b.dataset.sourceId=source.source_id;b.dataset.packId=packId;b.dataset.section=section.id;add(sections,b)}
   if(openPage){app.selectedSourceId=source.source_id;select("source-process")}
  }catch(e){if(token===serial){message.textContent=e.message;app.processChoices[source.source_id]={packId:null,section:null};}}
 }
 choice.addEventListener("change",()=>{cleanMedia();if(app.selectedSourceId===source.source_id)root().replaceChildren(note("در حال تغییر فرایند..."));apply()});
 try{const result=await request(sourceApi(source.source_id,"/process-workspace"),{background:true});if(app.user!==user||!group.isConnected)return;
  for(const p of result.processes){const o=el("option","",p.title);o.value=p.id;add(choice,o)}
  if(!result.processes.length){choice.disabled=true;message.textContent="فرایند فعال و مجاز تنظیم نشده است.";return}
  const previous=app.processChoices[source.source_id]?.packId;
  choice.value=result.processes.some(p=>p.id===previous)?previous:result.processes[0].id;
  await apply(false);
 }catch(e){choice.disabled=true;message.textContent=e.message;add(group,link("دریافت دوباره فرایندها",()=>{choice.remove();message.remove();sections.remove();loadProcessChoices(source,group)}))}
}
async function processWorkspacePage(){
 const sourceId=app.selectedSourceId,selection=app.processChoices[sourceId],m=root();
 if(!selection?.packId){add(m,note("ابتدا فرایند را از منوی اتصال انتخاب کنید."));return}
 const packId=selection.packId;let section=selection.section,manifest;
 try{manifest=await request(sourceApi(sourceId,"/process-workspace/"+packId+"?section="+encodeURIComponent(section)))}catch(e){
  if(e.status!==403||section==="inbox")throw e;
  manifest=await request(sourceApi(sourceId,"/process-workspace/"+packId));
  if(app.selectedSourceId!==sourceId||app.processChoices[sourceId]?.packId!==packId||app.processChoices[sourceId]?.section!==section)return;
  section=manifest.section;selection.section=section;
 }
 if(!m.isConnected||!["source-process","source-secretary"].includes(app.page)||app.selectedSourceId!==sourceId||app.processChoices[sourceId]?.packId!==packId||app.processChoices[sourceId]?.section!==section)return;
 app.processManifests[sourceId]=manifest;refreshProcessMenu(sourceId,manifest);
 $("breadcrumb").textContent=manifest.process.title+" · "+(manifest.navigation.find(s=>s.id===section)?.label||"کارتابل");
 if(manifest.process.renderer==="meeting"){
  const view=manifest.navigation.find(s=>s.id===section)?.view;
  if(view==="assistant"){await assistantPage(sourceId);return}
  if(view==="reports"){await reportsPage(sourceId);return}
  if(view==="monitor"){await monitorPage(sourceId);return}
  if(view==="meetings"){await boundSourceMeetings();return}
  await secretaryPage(sourceId,packId,section,manifest);return;
 }
 heading(m,manifest.process.title,manifest.navigation.find(s=>s.id===manifest.section)?.label||"کارتابل فرایند");
 const view=manifest.navigation.find(s=>s.id===manifest.section)?.view;
 if(view==="overview"){for(const p of manifest.process.processes)add(m,note(p.title+" · "+p.process_uid));for(const s of manifest.navigation)add(m,note(s.label+": "+fmt(s.count)));return}
 const box=card("وظایف من","این آداپتور، کارتابل بومی فرایند را به صورت خواندنی نمایش می‌دهد.");
 for(const t of manifest.tasks)add(box,el("p","",t.stage_label+" · پرونده "+t.number));
 if(!manifest.tasks.length)add(box,note("وظیفه جاری برای شما در این فرایند وجود ندارد."));
 if(manifest.truncated)add(box,note("بیش از ۲۰۰ وظیفه وجود دارد؛ فهرست کامل نیست."));add(m,box);
}

function refreshProcessMenu(sourceId,manifest){
 const choice=app.processChoices[sourceId];if(!choice||choice.packId!==manifest.process.id)return;
 const target=Array.from(document.querySelectorAll('[data-process-menu]')).find(x=>x.dataset.processMenu===sourceId);if(!target)return;
 target.replaceChildren();for(const section of manifest.navigation){const b=link(section.label+(section.count?" · "+fmt(section.count):""),()=>{app.selectedSourceId=sourceId;app.processChoices[sourceId].section=section.id;select("source-process")});b.dataset.page="source-process";b.dataset.sourceId=sourceId;b.dataset.packId=manifest.process.id;b.dataset.section=section.id;b.classList.toggle("active",sourceId===app.selectedSourceId&&section.id===choice.section);add(target,b)}
}
