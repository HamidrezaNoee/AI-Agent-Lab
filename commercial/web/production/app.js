"use strict";
const app={processChoices:{},processManifests:{},secretaryTimer:null,user:null,csrf:null,page:"overview",selectedSourceId:null,cursor:null,meetings:[],questions:[],sending:false,pendingQuestion:null,monitorTimer:null,idleTimer:null,lastHeartbeat:0,newConversation:true,conversationId:null,voiceEnabled:false,calendar:"jalali",preferences:{secretary_auto_play_voice:false,voice_auto_transcribe:true,voice_auto_send:false},activeOperation:null,cleanup:[]};
const $=id=>document.getElementById(id);
function el(tag,klass,text){const n=document.createElement(tag);if(klass)n.className=klass;if(text!==undefined)n.textContent=String(text);return n}
function add(parent,...children){for(const x of children.flat())if(x!==undefined&&x!==null)parent.append(x);return parent}
function link(text,callback,klass="button secondary"){const b=el("button",klass,text);b.type="button";b.addEventListener("click",callback);return b}
function card(title,subtitle){const s=el("section","panel");add(s,el("h2","",title),el("p","sub",subtitle||""));return s}
function note(text,error=false){
 const box=el("div","notice"+(error?" error dismissible-notice":""));add(box,el("span","",text));
 if(error){box.setAttribute("role","alert");const close=link("×",()=>box.remove(),"notice-close");close.setAttribute("aria-label","بستن پیام خطا");add(box,close)}
 return box;
}
// Render a small, safe Markdown subset using text nodes only.
function secretaryRichText(text){
 const body=el("div","chat-bubble-text");let code=null;
 for(const line of String(text).split("\n")){
  if(line.trim().startsWith("```")){if(code)code=null;else{code=el("code");add(body,add(el("pre","chat-code"),code))}continue}
  if(code){code.append(document.createTextNode(line+"\n"));continue}
  const row=el("div",/^\s*[-*] /.test(line)?"chat-list-item":"");
  for(const part of line.split(/(\*\*[^*]+\*\*|`[^`]+`)/g)){
   if(part.startsWith("**")&&part.endsWith("**"))add(row,el("strong","",part.slice(2,-2)));
   else if(part.startsWith("`")&&part.endsWith("`"))add(row,el("code","",part.slice(1,-1)));
   else row.append(document.createTextNode(part));
  }
  if(!line)add(row,el("br"));add(body,row);
 }
 return body;
}
function heading(container,title,description){add(container,add(el("div","page-head"),el("h1","",title),el("p","",description)))}
function root(){const m=$("main");m.replaceChildren();return m}
function fmt(value){return new Intl.NumberFormat("fa-IR").format(value)}
function calendarMode(){return app.calendar==="gregorian"?"gregorian":"jalali"}
function calendarName(){return calendarMode()==="jalali"?"شمسی":"میلادی"}
function calendarLocale(latin=false){
 const calendar=calendarMode()==="jalali"?"persian":"gregory";
 return "fa-IR-u-ca-"+calendar+(latin?"-nu-latn":"");
}
const jalaliIsoCache=new Map();
function persianParts(value){
 const d=value instanceof Date?value:new Date(value);
 if(Number.isNaN(d.getTime()))return null;
 const out={};
 for(const part of new Intl.DateTimeFormat("fa-IR-u-ca-persian-nu-latn",{year:"numeric",month:"numeric",day:"numeric"}).formatToParts(d)){
  if(part.type==="year"||part.type==="month"||part.type==="day")out[part.type]=Number(part.value);
 }
 return out;
}
function jalaliToIso(value){
 const raw=String(value||"").trim().replaceAll("-","/");
 if(jalaliIsoCache.has(raw))return jalaliIsoCache.get(raw);
 const match=raw.match(/^(\d{4})\/(\d{1,2})\/(\d{1,2})$/);if(!match)return "";
 const jy=Number(match[1]),jm=Number(match[2]),jd=Number(match[3]);
 if(jy<1300||jy>1600||jm<1||jm>12||jd<1||jd>31)return "";
 const cursor=new Date(jy+621,2,1,12,0,0,0);
 for(let i=0;i<430;i++){
  const parts=persianParts(cursor);
  if(parts?.year===jy&&parts?.month===jm&&parts?.day===jd){
   const result=[cursor.getFullYear(),String(cursor.getMonth()+1).padStart(2,"0"),String(cursor.getDate()).padStart(2,"0")].join("-");
   jalaliIsoCache.set(raw,result);return result;
  }
  cursor.setDate(cursor.getDate()+1);
 }
 return "";
}
function isoToJalali(value){
 const d=value instanceof Date?value:parseDateValue(value);if(!d)return "";
 const parts=persianParts(d);if(!parts)return "";
 return [parts.year,String(parts.month).padStart(2,"0"),String(parts.day).padStart(2,"0")].join("/");
}
function parseDateValue(value){
 if(!value)return null;
 const raw=String(value).trim();
 if(/^1[3-6]\d{2}[\/-]\d{1,2}[\/-]\d{1,2}$/.test(raw)){
  const iso=jalaliToIso(raw);if(!iso)return null;
  const [year,month,day]=iso.split("-").map(Number);return new Date(year,month-1,day,12,0,0,0);
 }
 if(/^\d{4}-\d{2}-\d{2}$/.test(raw)){
  const [year,month,day]=raw.split("-").map(Number);
  const result=new Date(year,month-1,day,12,0,0,0);
  return Number.isNaN(result.getTime())?null:result;
 }
 const normalized=/^\d{4}-\d{2}-\d{2} /.test(raw)?raw.replace(" ","T"):raw;
 const result=new Date(normalized);
 return Number.isNaN(result.getTime())?null:result;
}
function isoDate(value){
 const d=value instanceof Date?value:parseDateValue(value);
 if(!d)return "";
 return [d.getFullYear(),String(d.getMonth()+1).padStart(2,"0"),String(d.getDate()).padStart(2,"0")].join("-");
}
function calendarParts(value){
 const d=value instanceof Date?value:parseDateValue(value);
 if(!d)return null;
 const out={};
 for(const part of new Intl.DateTimeFormat(calendarLocale(true),{year:"numeric",month:"numeric",day:"numeric"}).formatToParts(d)){
  if(part.type==="year"||part.type==="month"||part.type==="day")out[part.type]=Number(part.value);
 }
 return out;
}
function dateOnlyText(value){
 if(!value)return "ثبت نشده";
 const d=parseDateValue(value);
 if(!d)return String(value);
 return new Intl.DateTimeFormat(calendarLocale(),{year:"numeric",month:"2-digit",day:"2-digit"}).format(d);
}
function dateText(value){
 if(!value)return "ثبت نشده";
 const raw=String(value),d=parseDateValue(raw);
 if(!d)return raw;
 const hasTime=/T|\s\d{1,2}:\d{2}/.test(raw);
 const options=hasTime
  ?{dateStyle:"medium",timeStyle:"short",timeZone:"Asia/Tehran"}
  :{dateStyle:"medium"};
 return new Intl.DateTimeFormat(calendarLocale(),options).format(d);
}
function firstCalendarMonthDate(anchor){
 let cursor=new Date(anchor.getFullYear(),anchor.getMonth(),anchor.getDate(),12,0,0,0);
 for(let i=0;i<35;i++){
  const parts=calendarParts(cursor);
  if(parts?.day===1)return cursor;
  cursor.setDate(cursor.getDate()-1);
 }
 return cursor;
}
function shiftCalendarMonth(anchor,delta){
 const first=firstCalendarMonthDate(anchor);
 if(delta>0){first.setDate(first.getDate()+32);return firstCalendarMonthDate(first)}
 first.setDate(first.getDate()-1);return firstCalendarMonthDate(first);
}
function monthTitle(anchor){
 return new Intl.DateTimeFormat(calendarLocale(),{year:"numeric",month:"long"}).format(anchor);
}
function dateControl(initial="",options={}){
 const control=el("div","avan-date-picker"),canonical=el("input","avan-date-canonical"),
  display=el("input","avan-date-display"),toggle=el("button","avan-date-toggle","▦"),
  popup=el("div","avan-date-popover");
 canonical.type="hidden";
 const storage=options.storage==="jalali"?"jalali":"iso",initialDate=parseDateValue(initial),initialIso=initialDate?isoDate(initialDate):"";
 canonical.value=initialIso?(storage==="jalali"?isoToJalali(initialIso):initialIso):"";
 display.type="text";display.readOnly=true;display.autocomplete="off";
 display.placeholder=calendarMode()==="jalali"?"انتخاب تاریخ شمسی":"انتخاب تاریخ میلادی";
 toggle.type="button";toggle.setAttribute("aria-label","باز کردن انتخابگر تاریخ "+calendarName());
 popup.hidden=true;popup.setAttribute("role","dialog");popup.setAttribute("aria-label","انتخاب تاریخ "+calendarName());
 let anchor=parseDateValue(canonical.value)||new Date();
 const sync=()=>{display.value=canonical.value?dateOnlyText(canonical.value):""};
 const set=value=>{
  const selected=value?String(value).slice(0,10):"";
  canonical.value=selected?(storage==="jalali"?isoToJalali(selected):selected):"";
  anchor=parseDateValue(canonical.value)||new Date();
  sync();popup.hidden=true;
  canonical.dispatchEvent(new Event("input",{bubbles:true}));
  canonical.dispatchEvent(new Event("change",{bubbles:true}));
 };
 const render=()=>{
  popup.replaceChildren();
  const head=el("div","avan-date-head"),prev=el("button","avan-date-nav","‹"),
   title=el("strong","",monthTitle(anchor)),next=el("button","avan-date-nav","›");
  prev.type=next.type="button";prev.setAttribute("aria-label","ماه قبل");next.setAttribute("aria-label","ماه بعد");
  prev.addEventListener("click",()=>{anchor=shiftCalendarMonth(anchor,-1);render()});
  next.addEventListener("click",()=>{anchor=shiftCalendarMonth(anchor,1);render()});
  add(head,prev,title,next);
  const weekdays=el("div","avan-date-weekdays");
  for(const name of ["ش","ی","د","س","چ","پ","ج"])add(weekdays,el("span","",name));
  const grid=el("div","avan-date-grid"),first=firstCalendarMonthDate(anchor),month=calendarParts(first);
  const offset=(first.getDay()+1)%7;
  const start=new Date(first);start.setDate(first.getDate()-offset);
  const today=isoDate(new Date()),selectedDate=parseDateValue(canonical.value),selectedIso=selectedDate?isoDate(selectedDate):"";
  for(let i=0;i<42;i++){
   const day=new Date(start);day.setDate(start.getDate()+i);
   const parts=calendarParts(day),value=isoDate(day),button=el("button","avan-date-day",fmt(parts?.day??""));
   button.type="button";
   if(parts?.year!==month?.year||parts?.month!==month?.month)button.classList.add("is-outside");
   if(value===today)button.classList.add("is-today");
   if(value===selectedIso)button.classList.add("is-selected");
   button.setAttribute("aria-label",dateOnlyText(value));
   button.addEventListener("click",()=>set(value));add(grid,button);
  }
  const foot=el("div","avan-date-foot"),todayButton=el("button","avan-date-today","امروز"),clearButton=el("button","avan-date-clear","پاک کردن");
  todayButton.type=clearButton.type="button";
  todayButton.addEventListener("click",()=>set(isoDate(new Date())));
  clearButton.addEventListener("click",()=>set(""));
  add(foot,todayButton,clearButton);add(popup,head,weekdays,grid,foot);
 };
 const open=()=>{anchor=parseDateValue(canonical.value)||new Date();render();popup.hidden=!popup.hidden};
 toggle.addEventListener("click",open);display.addEventListener("click",open);
 display.addEventListener("keydown",event=>{if(event.key==="Enter"||event.key===" "){event.preventDefault();open()}});
 const outside=event=>{if(!control.contains(event.target))popup.hidden=true};
 document.addEventListener("pointerdown",outside);app.cleanup.push(()=>document.removeEventListener("pointerdown",outside));
 add(control,canonical,display,toggle,popup);sync();
 return {control,input:canonical,display,toggle,set};
}
function toast(text,options={}){
 const t=$("toast");if(!t)return;
 if(toast.timer){clearTimeout(toast.timer);toast.timer=null}
 const hide=()=>{t.hidden=true;t.replaceChildren();if(toast.timer){clearTimeout(toast.timer);toast.timer=null}};
 const message=el("span","toast-message",text||"");
 const close=el("button","toast-close","×");close.type="button";close.setAttribute("aria-label","بستن پیام");
 close.addEventListener("click",event=>{event.stopPropagation();hide()});
 t.replaceChildren(message,close);t.hidden=false;t.setAttribute("role",options.error?"alert":"status");
 t.onclick=event=>{if(event.target===t||event.target===message)hide()};
 const duration=Number(options.duration);
 toast.timer=setTimeout(hide,Number.isFinite(duration)&&duration>0?Math.min(duration,10000):10000);
}
function sourceApi(sourceId,path){
 return sourceId?("/api/sources/"+encodeURIComponent(sourceId)+path):("/api"+path);
}
function makeRequestId(){
 if(globalThis.crypto?.randomUUID)return crypto.randomUUID().replaceAll("-","");
 return Date.now().toString(36)+Math.random().toString(36).slice(2)+Math.random().toString(36).slice(2);
}
async function clientAudit(event,detail={}){
 if(!app.user||!app.csrf||app.user.bootstrap_mode)return;
 try{
  await fetch("/api/support/client-event",{
   method:"POST",credentials:"same-origin",cache:"no-store",redirect:"error",
   headers:{"Accept":"application/json","Content-Type":"application/json","X-AVAN-CSRF":app.csrf},
   body:JSON.stringify({event,detail})
  });
 }catch(_){}
}
function errorDescription(error){
 const message=error?.message||"خطای نامشخص",parts=[message];
 if(error?.code && !String(error.code).startsWith("HTTP_") && error.code!=="NETWORK_ERROR" && error.code!=="ABORTED"){
  parts.push("کد: "+error.code);
 }
 const alreadyShowsUpstream=/ProcessMaker.*HTTP\s+\d{3}/i.test(String(message));
 if(error?.status && !(error.status===502&&alreadyShowsUpstream))parts.push("HTTP "+error.status);
 if(error?.requestId)parts.push("شناسه پیگیری: "+error.requestId);
 return parts.join(" · ");
}
async function request(url,options={}){
 const requestId=options.requestId||makeRequestId();
 const headers={"Accept":"application/json","X-AVAN-Request-ID":requestId,...(options.headers||{})};
 const scoped=url.match(/^\/api\/sources\/([^/]+)\/(ask|questions|meetings(?:\/[^/]+)?|agent\/(status|history)|reports\/actions(?:\/ask)?|monitor(?:\/[^/]+)?|voice\/(speech|transcribe))(?:\?|$)/);
 if(scoped){
  const sourceId=scoped[1],choice=app.processChoices[sourceId],manifest=app.processManifests[sourceId];
  if(choice?.packId && manifest?.process?.id===choice.packId &&
     manifest?.process?.adapter==="meeting_v2" && manifest?.process?.renderer==="meeting"){
   headers["X-AVAN-Process-Pack"]=choice.packId;
  }
 }
 if(options.background)headers["X-AVAN-BACKGROUND"]="1";
 if(options.method==="POST" && app.csrf)headers["X-AVAN-CSRF"]=app.csrf;
 const {background,requestId:ignoredRequestId,audit=true,...fetchOptions}=options;
 let response;
 try{
  response=await fetch(url,{...fetchOptions,headers,credentials:"same-origin",cache:"no-store",redirect:"error"});
 }catch(cause){
  if(cause?.name==="AbortError"){
   const error=Error("پردازش به درخواست شما متوقف شد.");error.code="ABORTED";error.requestId=requestId;
   void clientAudit("CLIENT_REQUEST_ABORTED",{request_id:requestId,path:url,method:options.method||"GET",result:"cancelled"});
   throw error;
  }
  const error=Error("ارتباط با سرور AVAN برقرار نشد.");error.code="NETWORK_ERROR";error.requestId=requestId;error.cause=cause;
  void clientAudit("CLIENT_NETWORK_ERROR",{request_id:requestId,path:url,method:options.method||"GET",error_type:cause?.name||"network"});
  throw error;
 }
 if(response.status===401){
   if(app.user?.bootstrap_mode && url!=="/api/me" && url.startsWith("/api/")){
     throw Error("هویت سازمانی GodAdmin هنوز متصل نشده است؛ این بخش فعلاً در حالت محدود نمایش داده می‌شود.");
   }
   sessionExpired();throw Error("نشست سازمانی پایان یافته است. دوباره وارد شوید.")
 }
 if(!response.ok){
   let message="دریافت اطلاعات با خطا مواجه شد.",code="HTTP_"+response.status,serverRequestId=null;
   try{
    const e=await response.json();
    if(typeof e.detail==="string")message=e.detail;
    else if(Array.isArray(e.detail)){
     const validation=e.detail.map(x=>x?.msg).filter(Boolean);
     if(validation.length)message=validation.join("؛ ");
    }else if(e.detail?.message)message=e.detail.message;
    if(typeof e.detail?.code==="string")code=e.detail.code;
    else if(typeof e.code==="string")code=e.code;
    if(typeof e.request_id==="string")serverRequestId=e.request_id;
   }catch{}
   const error=Error(message);error.status=response.status;error.code=code;error.requestId=serverRequestId||requestId;
   void clientAudit("API_ERROR",{request_id:error.requestId,path:url,method:options.method||"GET",status:response.status,error:message,code});
   throw error;
 }
 if(audit!==false && !background && options.method==="POST" &&
    !url.startsWith("/api/support/client-event") && !url.includes("/auth/heartbeat")){
   void clientAudit("API_ACTION",{request_id:requestId,path:url.split("?")[0],method:"POST",status:response.status,result:"success"});
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
 $("user-nav").hidden=!!user.bootstrap_mode;
 $("support-nav").hidden=!!user.bootstrap_mode;
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
  if(capabilities.has("secretary"))add(group,sourcePageButton(source,"source-secretary","✦  دبیر هوشمند"));
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
window.addEventListener("error",event=>{
 if(!app.user)return;
 void clientAudit("CLIENT_UI_ERROR",{page:app.page,message:String(event.message||"خطای رابط کاربری"),error_type:"window_error"});
});
window.addEventListener("unhandledrejection",event=>{
 if(!app.user)return;
 const reason=event.reason;
 void clientAudit("CLIENT_UI_ERROR",{page:app.page,message:String(reason?.message||reason||"خطای Promise"),error_type:"unhandled_rejection"});
});
window.addEventListener("message",event=>{
 if(event.origin!==window.location.origin||event.data?.type!=="avan-ui-settings-changed")return;
 const calendar=event.data.calendar==="gregorian"?"gregorian":"jalali";
 if(calendar!==app.calendar){app.calendar=calendar;window.location.reload()}
});
function select(page){
 const platformPage=page.startsWith("platform-");
 const adminPage=page==="system-management";
 const personalPage=page==="user-settings"||page==="support-logs";
 const sourcePage=page.startsWith("source-");
 const orgPage=!platformPage&&!adminPage&&!sourcePage&&!personalPage;
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
 if(app.user&&!app.user.bootstrap_mode)void clientAudit("NAVIGATE",{page,source_id:app.selectedSourceId||null});
 const labels={overview:"نمای کلی",meetings:"جلسات و مصوبات",assistant:"دستیار مدیریتی",reports:"گزارش اقدامات",bi:"BI همه فرایندها",secretary:"دبیر هوشمند",monitor:"هشدار و پیگیری","source-overview":"BPMS متصل","source-meetings":"جلسات BPMS","source-assistant":"دستیار BPMS","source-secretary":"اجرای هوشمند جلسات","source-reports":"گزارش اقدامات BPMS","source-monitor":"هشدار و پیگیری BPMS","source-bi":"BI منبع","platform-overview":"نمای کلی پلتفرم","platform-assistant":"دستیار پلتفرم","platform-bi":"گزارش BPMSها","system-management":"مدیریت سامانه","user-settings":"تنظیمات من","support-logs":"پشتیبانی · لاگ‌ها"};
 $("breadcrumb").textContent=labels[page]||"آوان";
 document.querySelectorAll("#nav button").forEach(b=>b.classList.toggle("active",
   sourcePage&&b.dataset.sourceId
    ?b.dataset.sourceId===app.selectedSourceId&&b.dataset.page===page&&(!b.dataset.section||(b.dataset.packId===app.processChoices[app.selectedSourceId]?.packId&&b.dataset.section===app.processChoices[app.selectedSourceId]?.section))
    :b.dataset.page===page));
 const m=root();add(m,el("p","muted",adminPage?"در حال باز کردن مدیریت سامانه...":"در حال دریافت اطلاعات سازمان..."));
 const work={overview:overview,meetings:meetingPage,assistant:assistantPage,reports:reportsPage,bi:biPage,secretary:secretaryPage,monitor:monitorPage,"source-overview":boundSourceOverview,"source-meetings":boundSourceMeetings,"source-assistant":()=>assistantPage(app.selectedSourceId),"source-secretary":()=>intelligentMeetingPage(),"source-process":processWorkspacePage,"source-reports":()=>reportsPage(app.selectedSourceId),"source-monitor":()=>monitorPage(app.selectedSourceId),"source-bi":()=>biPage(app.selectedSourceId),"platform-overview":platformOverview,"platform-assistant":platformAssistant,"platform-bi":platformBI,"system-management":systemManagement,"user-settings":userSettingsPage,"support-logs":supportLogsPage}[page];
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
  " · "+dateText(meeting.meeting_date_utc)));
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
  const user=await request("/api/me");
  try{const ui=await request("/api/ui-config");app.calendar=ui.calendar==="gregorian"?"gregorian":"jalali"}catch(_){app.calendar="jalali"}
  setupUser(user);
  if(!user.bootstrap_mode){
   try{app.preferences={...app.preferences,...await request("/api/user/preferences",{audit:false})}}catch(_){}
  }
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

async function userSettingsPage(){
 const m=root();m.classList.add("user-settings-page");heading(m,"تنظیمات من","تنظیمات شخصی، امنیت حساب و رفتار دبیر هوشمند فقط برای حساب شما.");
 let prefs;
 try{prefs=await request("/api/user/preferences",{audit:false})}catch(e){add(m,note(errorDescription(e),true));return}
 app.preferences={...app.preferences,...prefs};
 const isLocalGodAdmin=app.user?.subject==="bootstrap-godadmin"||app.user?.bootstrap_mode===true;

 const identity=el("section","settings-identity-hero");
 const avatar=el("span","settings-avatar",(app.user?.name||app.user?.username||"U").trim().slice(0,1));
 const identityCopy=el("div","settings-identity-copy");
 add(identityCopy,el("span","settings-kicker","حساب فعال"),el("h2","",app.user?.name||app.user?.username||"کاربر آوان"),
  el("p","muted",(app.user?.username||"")+" · "+(app.user?.role||"User")));
 const securityBadge=el("span","settings-security-badge",isLocalGodAdmin?"GodAdmin داخلی · حساب دائمی":"Keycloak · ورود سازمانی");
 add(identity,avatar,identityCopy,securityBadge);add(m,identity);

 const layout=el("div","settings-layout");
 const panel=card("صوت و گفت‌وگو با دبیر هوشمند","رفتار مکالمه و صوت را برای حساب خودتان تنظیم کنید.");panel.classList.add("settings-card");
 const form=el("div","user-preferences-grid");
 function toggle(key,title,description,icon){
  const row=el("label","user-preference-row"),input=el("input"),copy=el("span","user-preference-copy"),mark=el("span","preference-icon",icon);
  input.type="checkbox";input.checked=!!app.preferences[key];input.dataset.preference=key;
  add(copy,el("strong","",title),el("small","muted",description));add(row,mark,copy,input);return {row,input};
 }
 const autoplay=toggle("secretary_auto_play_voice","پخش خودکار صدای دبیر","پس از آماده شدن پاسخ، صوت به‌صورت خودکار پخش شود.","◉");
 const transcribe=toggle("voice_auto_transcribe","تبدیل خودکار ویس به متن","بعد از ضبط یا انتخاب فایل صوتی، متن بدون مرحله اضافی آماده شود.","⌁");
 const autosend=toggle("voice_auto_send","ارسال خودکار متن ویس","متن تبدیل‌شده بدون بازبینی دستی برای دبیر ارسال شود.","↑");
 const sync=()=>{autosend.input.disabled=!transcribe.input.checked;if(!transcribe.input.checked)autosend.input.checked=false};
 transcribe.input.addEventListener("change",sync);sync();
 add(form,autoplay.row,transcribe.row,autosend.row);
 const status=el("div","preference-save-status");
 const save=link("ذخیره تنظیمات گفتگو",async()=>{
  save.disabled=true;status.replaceChildren();
  try{
   const body={secretary_auto_play_voice:autoplay.input.checked,voice_auto_transcribe:transcribe.input.checked,voice_auto_send:transcribe.input.checked&&autosend.input.checked};
   const saved=await request("/api/user/preferences",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(body)});
   app.preferences={...app.preferences,...saved};status.replaceChildren(note("تنظیمات شخصی ذخیره شد."));
  }catch(e){status.replaceChildren(note(errorDescription(e),true))}finally{save.disabled=false}
 },"button primary");
 add(panel,form,add(el("div","settings-card-actions"),save),status);

 const security=card("امنیت و رمز عبور",isLocalGodAdmin?"رمز GodAdmin در مخزن امن محلی تغییر می‌کند؛ رمز فعلی برای چرخش لازم است.":"رمز در Keycloak تغییر می‌کند و هیچ رمز عبوری داخل AVAN ذخیره نمی‌شود.");security.classList.add("settings-card","settings-security-card");
 const securityInfo=el("div","settings-security-info");
 add(securityInfo,
  add(el("div","settings-security-item"),el("span","","ارائه‌دهنده هویت"),el("strong","",isLocalGodAdmin?"AVAN Local GodAdmin":"Keycloak / OIDC")),
  add(el("div","settings-security-item"),el("span","","حساب"),el("strong","",app.user?.username||app.user?.subject||"—")),
  add(el("div","settings-security-item"),el("span","","اثر تغییر رمز"),el("strong","","خروج از همه نشست‌ها"))
 );
 const passwordGrid=el("div","settings-password-grid");
 const p0=isLocalGodAdmin?inputField("رمز فعلی GodAdmin","","password"):null;
 const p1=inputField("رمز جدید (حداقل ۱۶ نویسه)","","password"),p2=inputField("تکرار رمز جدید","","password");
 if(p0)p0.input.autocomplete="current-password";p1.input.autocomplete="new-password";p2.input.autocomplete="new-password";
 const meter=el("div","password-strength"),meterFill=el("span"),meterText=el("small","muted","قدرت رمز: —");add(meter,meterFill);
 function passwordScore(){
  const v=p1.input.value||"";let n=0;
  if(v.length>=16)n++;if(/[a-z]/i.test(v)&&/\d/.test(v))n++;if(/[^A-Za-z0-9]/.test(v))n++;if(v.length>=24)n++;
  meterFill.style.width=(n*25)+"%";meter.dataset.score=String(n);meterText.textContent="قدرت رمز: "+(["—","حداقلی","متوسط","خوب","قوی"][n]||"—");
 }
 p1.input.addEventListener("input",passwordScore);
 if(p0)add(passwordGrid,p0.wrap);add(passwordGrid,p1.wrap,p2.wrap);const pwOut=el("div","settings-password-status");
 const changePassword=link("تغییر رمز و خروج از نشست‌ها",async()=>{
  pwOut.replaceChildren();
  if((p1.input.value||"").length<16){pwOut.replaceChildren(note("رمز جدید باید حداقل ۱۶ نویسه باشد.",true));return}
  if(p1.input.value!==p2.input.value){pwOut.replaceChildren(note("تکرار رمز با رمز جدید یکسان نیست.",true));return}
  changePassword.disabled=true;
  try{
   await request("/api/user/password",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({current:p0?.input.value||"",password:p1.input.value,confirmation:p2.input.value})});
   if(p0)p0.input.value="";p1.input.value="";p2.input.value="";passwordScore();pwOut.replaceChildren(note("رمز تغییر کرد. برای امنیت، همه نشست‌ها پایان یافت؛ در حال انتقال به ورود..."));
   setTimeout(()=>window.location.assign("/auth/login"),900);
  }catch(e){pwOut.replaceChildren(note(errorDescription(e),true));changePassword.disabled=false}
 },"button primary");
 add(security,securityInfo,passwordGrid,meter,meterText,add(el("div","settings-card-actions"),changePassword),pwOut);
 add(layout,panel,security);add(m,layout);
}

async function supportLogsPage(){
 const m=root();m.classList.add("support-logs-page");heading(m,"لاگ‌های پشتیبانی","رویدادها را بر اساس کاربر، فرایند، اتصال BPMS، پرونده و مرحله پیدا کنید؛ محتوای پیام، رمز و Token لاگ نمی‌شود.");
 const panel=card("رویدادهای عملیاتی","فیلترها روی لاگ‌های مجاز همین حساب/سازمان اعمال می‌شوند.");panel.classList.add("support-log-panel");
 const controls=el("div","support-log-controls");
 const limit=el("select"),event=el("select"),actor=el("select"),source=el("select"),process=el("select"),stage=el("select");
 const caseUid=el("input"),requestId=el("input"),search=el("input"),out=el("div","support-log-output");
 requestId.value=String(app.pendingLogRequestId||"");app.pendingLogRequestId="";
 for(const [v,t] of [["100","۱۰۰ رویداد"],["250","۲۵۰ رویداد"],["500","۵۰۰ رویداد"]]){const o=el("option","",t);o.value=v;add(limit,o)}limit.value="250";
 const known=[
  ["API_ERROR","خطاهای API"],["CLIENT_NETWORK_ERROR","خطای ارتباط"],["CLIENT_UI_ERROR","خطای رابط کاربری"],["CLIENT_REQUEST_ABORTED","پردازش متوقف‌شده"],
  ["SECRETARY_PROCESSING_STARTED","شروع پردازش دبیر"],["SECRETARY_PROCESSING_COMPLETED","پایان پردازش دبیر"],["SECRETARY_CONFIRMATION_RESOLVED","تأیید قطعی Resolver"],
  ["SECRETARY_AGENTIC_COMMAND_EXECUTED","اجرای فرمان هوشمند دبیر"],["SECRETARY_PROCESSING_FAILED","خطای پردازش دبیر"],["SECRETARY_PROCESSING_CANCELLED","توقف پردازش دبیر"],
  ["USER_PASSWORD_CHANGED","تغییر رمز حساب"],["API_ACTION","عملیات کاربر"],["NAVIGATE","جابجایی صفحات"],["USER_PREFERENCES_CHANGED","تغییر تنظیمات"]
 ];
 function option(select,value,label){const o=el("option","",label);o.value=value;add(select,o)}
 option(event,"","همه رویدادها");for(const [v,t] of known)option(event,v,t);
 option(actor,"","همه کاربران");option(source,"","همه اتصال‌ها");option(process,"","همه فرایندها");option(stage,"","همه مراحل");
 caseUid.placeholder="Case UID";requestId.placeholder="Request ID";search.placeholder="جستجو در رویداد، خطا، مسیر یا شناسه...";
 function refill(select,items,empty,labelOf=x=>x){
  const keep=select.value;select.replaceChildren();option(select,"",empty);
  for(const item of items||[]){const value=typeof item==="object"?item.id:item;option(select,value,labelOf(item))}
  if(Array.from(select.options).some(o=>o.value===keep))select.value=keep;
 }
 let filterOptionsLoaded=false,logGeneration=0;
 async function load(){
  const generation=++logGeneration;
  out.replaceChildren(note("در حال دریافت لاگ‌ها..."));
  try{
   const q=new URLSearchParams({limit:limit.value});
   for(const [key,control] of [["event",event],["actor_id",actor],["source_id",source],["process_uid",process],["stage",stage],["case_uid",caseUid],["request_id",requestId],["q",search]])if(control.value.trim())q.set(key,control.value.trim());
   const data=await request("/api/support/logs?"+q.toString(),{audit:false});
   if(generation!==logGeneration||!out.isConnected)return;
   if(!filterOptionsLoaded){
    refill(actor,data.filters?.actors,"همه کاربران",x=>x.name||x.id);
    refill(source,data.filters?.sources,"همه اتصال‌ها");
    refill(process,data.filters?.processes,"همه فرایندها");
    refill(stage,data.filters?.stages,"همه مراحل");
    filterOptionsLoaded=true;
   }
   out.replaceChildren();
   const head=el("div","support-log-result-head");
   add(head,el("span","support-log-scope",data.scope==="tenant"?"نمای مدیر سیستم · تمام کاربران مجاز":"نمای شخصی · فقط رویدادهای شما"),
       el("span","muted",fmt((data.logs||[]).length)+" رویداد در این صفحه"));
   add(out,head);if(data.truncated)add(out,note("پنجره لاگ بسیار بزرگ است؛ برای نتیجه دقیق‌تر فیلتر کاربر/فرایند/پرونده را محدود کنید.",true));
   const rows=el("div","support-log-list"),labels=Object.fromEntries(known);
   if(!(data.logs||[]).length)add(rows,note("لاگی مطابق فیلتر فعلی وجود ندارد."));
   for(const item of data.logs||[]){
    const detail=item.detail||{},row=el("article","support-log-row"),headRow=el("div","support-log-row-head"),copy=el("div");
    add(copy,el("strong","",labels[item.event_code]||item.event_code),
      el("small","muted",dateText(item.happened_at)+" · "+(item.actor_id===app.user?.subject?"شما":(item.actor_name||item.actor_id))));
    const severity=/FAILED|ERROR|NETWORK/.test(item.event_code)?"error":/CANCELLED|ABORTED/.test(item.event_code)?"warning":"ok";
    add(headRow,copy,el("span","support-log-status "+severity,item.event_code));add(row,headRow);
    const chips=el("div","support-log-chips");
    for(const [label,value] of [["اتصال",detail.source_id],["فرایند",detail.process_uid||detail.pack_id],["پرونده",detail.case_uid],["مرحله",detail.stage],["Request",detail.request_id]])if(value)add(chips,el("span","support-log-chip",label+": "+value));
    if(chips.childNodes.length)add(row,chips);
    const summary=[detail.message||detail.error,detail.path,detail.result].filter(Boolean).join(" · ");if(summary)add(row,el("p","",summary));
    const details=el("details","support-log-detail");add(details,el("summary","","جزئیات فنی"),el("pre","",JSON.stringify(detail,null,2)),el("small","muted","شناسه رویداد: "+item.id));add(row,details);add(rows,row);
   }
   add(out,rows);
  }catch(e){if(generation===logGeneration&&out.isConnected)out.replaceChildren(note(errorDescription(e),true))}
 }
 function labelField(title,control,wide=false){const x=el("label","field"+(wide?" support-log-wide":""));control.setAttribute("aria-label",title);add(x,el("span","",title),control);return x}
 const refresh=link("↻ تازه‌سازی",()=>{filterOptionsLoaded=false;load()},"button secondary");
 const clear=link("پاک‌کردن فیلترها",()=>{for(const x of [event,actor,source,process,stage])x.value="";for(const x of [caseUid,requestId,search])x.value="";load()},"button secondary");
 add(controls,labelField("جستجو",search,true),labelField("کاربر",actor),labelField("اتصال BPMS",source),labelField("فرایند",process),
  labelField("مرحله",stage),labelField("نوع رویداد",event),labelField("Case UID",caseUid),labelField("Request ID",requestId),labelField("تعداد",limit),
  add(el("div","support-log-actions"),refresh,clear));
 let timer=null;search.addEventListener("input",()=>{clearTimeout(timer);timer=setTimeout(load,350)});
 for(const x of [event,actor,source,process,stage,limit])x.addEventListener("change",load);
 for(const x of [caseUid,requestId])x.addEventListener("change",load);
 add(panel,controls,out);add(m,panel);await load();
}

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
  if(capabilities.has("secretary"))add(p,link("مدیریت جلسات / دبیر هوشمند",()=>select("source-secretary"),"button secondary"));
  else add(p,note("ماژول «مدیریت جلسات و دبیر هوشمند» برای این حساب فعال نیست. مدیر سامانه باید از «کاربران → دسترسی‌ها» ماژول ۲ را فعال کند."));
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
     el("small","",meeting.meeting_no+" · "+meeting.meeting_status+" · "+dateText(meeting.meeting_date_utc)));
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
    el("small","",meeting.meeting_no+" · "+meeting.meeting_status+" · "+dateText(meeting.meeting_date_utc)));
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
 const m=root();heading(m,"گزارش BPMSهای متصل","هر موتور از Connector خودش و فقط در دامنه مجاز همین حساب AVAN خوانده می‌شود.");

 const native=(app.user?.bpms_sources||[])
  .filter(s=>(s.capabilities||[]).includes("bi"))
  .map(s=>({id:s.source_id,name:s.source_name,engine:s.engine||"BPMS",mode:"native",source:s}));
 const rest=(status.sources||[]).filter(s=>s.enabled)
  .map(s=>({id:s.id,name:s.name,engine:s.kind||"AVAN REST v1",mode:"rest",source:s}));
 const seen=new Set(),connected=[...native,...rest].filter(s=>!seen.has(s.id)&&seen.add(s.id));

 if(!connected.length){
  const settings=link("افزودن اتصال در مدیریت سامانه",()=>select("system-management"),"button primary");
  add(m,note("هنوز هیچ BPMS دارای دسترسی BI برای این حساب فعال نشده است."),settings);return
 }

 const sources=card("منابع گزارش","ProcessMaker از Connector بومی AVAN خوانده می‌شود؛ سایر موتورها می‌توانند قرارداد AVAN REST v1 داشته باشند.");
 for(const s of connected){
  const row=el("div","history-item"),details=el("div");
  add(details,el("strong","",s.name),el("small","",s.mode==="native"?(s.engine+" · اتصال بومی و Binding همین حساب"):(s.engine+" · AVAN REST v1")));
  if(s.mode==="native"){
   const open=link("باز کردن BI این اتصال",()=>{app.selectedSourceId=s.id;select("source-bi")},"button primary");
   add(row,details,open);
  }else{
   const choose=link("گزارش REST این اتصال",()=>{restPanel.hidden=false;restSource.value=s.id;restPanel.scrollIntoView({behavior:"smooth",block:"start"})},"button secondary");
   add(row,details,choose);
  }
  add(sources,row);
 }
 add(m,sources);

 const restEnabled=connected.filter(s=>s.mode==="rest");
 const restPanel=card("گزارش موتورهای AVAN REST v1","این بخش فقط برای موتورهایی است که قرارداد خواندنی AVAN REST v1 را پیاده کرده‌اند.");
 restPanel.hidden=!restEnabled.length;
 const restSource=el("select"),period=el("select"),out=el("div"),analysis=card("تحلیل زبان طبیعی","مدل فقط به گزارش REST منبع انتخابی دسترسی دارد.");
 restSource.setAttribute("aria-label","منبع BPMS REST");period.setAttribute("aria-label","بازه گزارش");
 for(const s of restEnabled){const opt=el("option","",s.name);opt.value=s.id;add(restSource,opt)}
 for(const [key,label] of [["last_30_days","۳۰ روز گذشته"],["last_7_days","۷ روز گذشته"],["this_month","ماه جاری"],["last_month","ماه قبل"],["all","تمام زمان‌ها"]]){const opt=el("option","",label);opt.value=key;add(period,opt)}
 add(restPanel,add(el("label"),el("span","","منبع"),restSource)," ",add(el("label"),el("span","","بازه"),period));
 const table=(labels,rows)=>{const t=el("table"),head=el("tr");for(const label of labels)add(head,el("th","",label));add(t,add(el("thead"),head));const body=el("tbody");for(const values of rows){const row=el("tr");for(const val of values)add(row,el("td","",val??"—"));add(body,row)}add(t,body);return add(el("div","table-scroll panel"),t)};
 const load=link("نمایش گزارش REST",async()=>{load.disabled=true;out.replaceChildren(note("در حال دریافت گزارش..."));try{const r=await request("/api/platform/bpms/report",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({source_id:restSource.value,period:period.value,limit:30})});if(!out.isConnected)return;out.replaceChildren();add(out,note("زمان استخراج: "+dateText(r.as_of_utc)+(r.coverage_complete?"":" · پوشش داده ناقص است.")));
  const stats=el("div","stats");for(const [key,label] of [["cases","کل پرونده"],["open_cases","باز"],["completed_cases","تکمیل‌شده"],["open_tasks","وظایف باز"],["overdue_tasks","وظایف تأخیردار"]])add(stats,add(el("div","stat"),el("span","",label),el("strong","",fmt(r.metrics[key]))));add(out,stats);
  add(out,table(["فرایند","کل","باز","تکمیل","وظایف تأخیردار"],r.processes.map(x=>[x.title,fmt(x.total),fmt(x.open),fmt(x.completed),fmt(x.overdue_tasks)])));
  add(out,table(["شماره پرونده","فرایند","وضعیت","ثبت"],r.rows.map(x=>[x.case_number,x.process_title,statusName(x.status),dateText(x.created_at)])));
  if(r.has_more)add(out,note("فهرست پرونده‌ها صفحه‌بندی شده است؛ برای ادامه بازه را محدود کنید."));
 }catch(e){out.replaceChildren(note(e.message,true))}finally{load.disabled=false}},"button primary");add(restPanel,load,out);

 const question=el("textarea");question.maxLength=2000;question.rows=3;question.setAttribute("aria-label","سؤال درباره گزارش BPMS REST");question.placeholder="کدام فرایندها بیشترین وظایف تأخیردار را دارند؟";
 const result=el("div");const ask=link("تحلیل منبع REST",async()=>{ask.disabled=true;result.replaceChildren(note("در حال تحلیل..."));try{const r=await request("/api/platform/bpms/ask",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({question:question.value,source_id:restSource.value,new_conversation:true})});if(result.isConnected){result.replaceChildren();renderAnalysis(result,r)}}catch(e){result.replaceChildren(note(e.message,true))}finally{ask.disabled=false}},"button primary");
 add(analysis,question,ask);if(status.voice_enabled)attachVoiceInput(analysis,question,true);if(!status.enabled)add(analysis,note("برای تحلیل متنی، اتصال مدل AI را فعال کنید."));add(analysis,result);add(restPanel,analysis);
 if(restEnabled.length)add(m,restPanel);
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
 add(target,evidence,el("small","muted","زمان بررسی: "+dateText(result.as_of_utc)));
}
async function renderMeetingCaseFlowGraph(target,sourceId,packId){
 target.replaceChildren();
 const shell=el("section","meeting-flow-report meeting-flow-report-v2");
 const head=el("div","meeting-flow-head");
 const headCopy=el("div","meeting-flow-head-copy");
 add(headCopy,el("span","secretary-eyebrow","دید فرایندی"),el("h3","","گراف جریان پرونده‌ها"),el("p","muted","هر پرونده را از دعوت تا اختتام دنبال کنید؛ شاخه‌های اقدامات موازی مثل Branchهای Git از مسیر جلسه جدا و دوباره Merge می‌شوند."));
 const legend=el("div","meeting-flow-legend");
 for(const [kind,label] of [["done","انجام‌شده"],["current","مرحله جاری"],["future","مرحله آینده"],["branch","اقدام موازی"]])add(legend,add(el("span","meeting-flow-legend-item"),el("i","legend-dot "+kind),el("span","",label)));
 add(head,headCopy,legend);add(shell,head);

 const perspectives=el("div","meeting-flow-perspectives");
 add(perspectives,el("span","meeting-flow-perspective-title","نمای سریع"));
 const perspectiveDefs=[
  ["all","همه پرونده‌ها"],
  ["waiting","منتظر اقدام"],
  ["secretary","در نقش دبیر"],
  ["chair","در نقش رئیس"],
  ["action_owner","اقدام‌های من"],
  ["completed","تکمیل‌شده"],
  ["with_actions","دارای اقدام"]
 ];
 const perspectiveButtons=[];
 let waitingOnly=false,activePerspective="all";

 const filters=el("div","meeting-flow-filters");
 const search=el("input");search.placeholder="جستجوی شماره پرونده، شماره جلسه یا عنوان";search.setAttribute("aria-label","جستجوی پرونده یا جلسه");
 const person=el("select"),process=el("select"),period=el("select"),fromDate=dateControl(),toDate=dateControl(),from=fromDate.input,to=toDate.input,role=el("select"),status=el("select"),stage=el("select"),owner=el("select"),unit=el("select"),actionScope=el("select"),sort=el("select");
 const processOption=el("option","","مدیریت جلسات + اقدامات مصوب");processOption.value="meeting_v2";add(process,processOption);process.disabled=true;
 for(const [control,label] of [[person,"شخص"],[process,"فرایند"],[period,"بازه زمانی"],[role,"نقش"],[status,"وضعیت"],[stage,"مرحله فعلی"],[owner,"مسئول فعلی"],[unit,"واحد سازمانی"],[actionScope,"نوع جریان"],[sort,"مرتب‌سازی"]])control.setAttribute("aria-label",label);
 fromDate.display.setAttribute("aria-label","از تاریخ "+calendarName());toDate.display.setAttribute("aria-label","تا تاریخ "+calendarName());
 for(const [v,t] of [["90d","۹۰ روز گذشته"],["30d","۳۰ روز گذشته"],["365d","یک سال گذشته"],["all","همه زمان‌ها"],["custom","بازه دلخواه"]]){const o=el("option","",t);o.value=v;add(period,o)}
 for(const [v,t] of [["","همه"],["with_actions","دارای اقدام"],["without_actions","بدون اقدام"]]){const o=el("option","",t);o.value=v;add(actionScope,o)}
 for(const [v,t] of [["newest","جدیدترین"],["oldest","قدیمی‌ترین"],["waiting","منتظر اقدام اول"],["stage","مرحله فرایند"],["progress_desc","بیشترین پیشرفت"],["progress_asc","کمترین پیشرفت"]]){const o=el("option","",t);o.value=v;add(sort,o)}
 const field=(label,control,kind="")=>add(el("label","meeting-flow-filter "+kind),el("span","",label),control);
 add(filters,
  field("جستجو",search,"is-search"),field("شخص",person),field("فرایند",process),
  field("بازه زمانی",period),field("از تاریخ "+calendarName(),fromDate.control,"is-date"),field("تا تاریخ "+calendarName(),toDate.control,"is-date"),
  field("نقش در پرونده",role),field("وضعیت",status),field("مرحله فعلی",stage),
  field("مسئول فعلی",owner),field("واحد سازمانی",unit),field("نوع جریان",actionScope),field("مرتب‌سازی",sort)
 );

 const actionBar=el("div","meeting-flow-actions");
 const refresh=link("↻ به‌روزرسانی",()=>loadGraph(true),"button secondary");
 const reset=link("پاک‌کردن فیلترها",()=>{resetFilters();loadGraph(true)},"button secondary");
 add(actionBar,reset,refresh);add(shell,perspectives,filters,actionBar);
 const body=el("div","meeting-flow-body");add(shell,body);add(target,shell);

 let offset=0,loading=false,loadedOptions=false;
 const addAll=(select,label="همه")=>{const o=el("option","",label);o.value="";add(select,o)};
 addAll(role);addAll(status);addAll(stage);addAll(owner);addAll(unit);

 function refill(select,items,valueKey="value",labelKey="label",allLabel="همه"){
  const previous=select.value;select.replaceChildren();addAll(select,allLabel);
  for(const item of items||[]){const o=el("option","",item[labelKey]||item.name||item[valueKey]||item);o.value=item[valueKey]||item.uid||item;add(select,o)}
  if([...select.options].some(o=>o.value===previous))select.value=previous;
 }
 function personOptions(items,current){
  const previous=person.value||current;person.replaceChildren();
  for(const item of items||[]){const o=el("option","",(item.name||item.username||item.uid)+(item.username?" · "+item.username:""));o.value=item.uid;add(person,o)}
  if([...person.options].some(o=>o.value===previous))person.value=previous;
 }
 function syncPerspective(){
  for(const [key,b] of perspectiveButtons)b.setAttribute("aria-pressed",String(key===activePerspective));
 }
 function resetFilters(){
  search.value="";period.value="90d";fromDate.set("");toDate.set("");role.value="";status.value="";stage.value="";owner.value="";unit.value="";actionScope.value="";sort.value="newest";waitingOnly=false;activePerspective="all";syncPerspective();
 }
 function applyPerspective(key){
  resetFilters();activePerspective=key;
  if(key==="waiting"){waitingOnly=true;sort.value="waiting"}
  else if(key==="secretary")role.value="secretary";
  else if(key==="chair")role.value="chair";
  else if(key==="action_owner")role.value="action_owner";
  else if(key==="completed")status.value="completed";
  else if(key==="with_actions")actionScope.value="with_actions";
  syncPerspective();loadGraph(true);
 }
 for(const [key,label] of perspectiveDefs){const b=link(label,()=>applyPerspective(key),"meeting-flow-perspective");b.setAttribute("aria-pressed",String(key==="all"));perspectiveButtons.push([key,b]);add(perspectives,b)}

 const payload=()=>{
  const custom=period.value==="custom"&&from.value&&to.value;
  return {
   pack_id:packId,person_uid:person.value||null,q:search.value.trim(),
   status:status.value||"all",stage:stage.value||"all",role:role.value||"all",
   owner_uid:owner.value||null,unit:unit.value||null,action_scope:actionScope.value||"all",
   waiting_only:waitingOnly,sort:sort.value||"newest",period:period.value,
   start:custom?from.value:null,end:custom?to.value:null,offset,limit:30
  };
 };

 function badge(text,kind=""){return el("span","meeting-flow-chip "+kind,text)}
 function miniPerson(p){return p?(p.name+(p.username?" · "+p.username:"")):"نامشخص"}
 function peopleText(items){
  const names=(items||[]).map(miniPerson).filter(Boolean);
  return names.length?names.join("، "):"فردی برای این مرحله ثبت نشده است";
 }
 let activeFlowTooltip=null;
 function flowTooltip(node,row,branch=null){
  const tip=el("span","meeting-flow-tooltip");
  add(tip,el("strong","",node.title||node.stage_title||"مرحله فرایند"));
  const entered=node.entered_at||node.delegated_at;
  add(tip,
   el("span","","زمان ورود: "+(entered?dateText(entered):"هنوز وارد این مرحله نشده")),
   el("span","","دبیر: "+miniPerson(row.meeting_roles?.secretary)),
   el("span","","رئیس جلسه: "+miniPerson(row.meeting_roles?.chair)),
   el("span","","افراد مرحله: "+peopleText(node.people||(node.owner?[node.owner]:[])))
  );
  if(branch)add(tip,el("span","","اقدام: "+branch.action_no+" · "+branch.title));
  if(node.finished_at)add(tip,el("span","","زمان پایان: "+dateText(node.finished_at)));
  add(tip,el("small","","برای مشاهده آخرین اطلاعات کل پرونده کلیک کنید."));
  return tip;
 }
 function hideFlowTooltip(){
  if(activeFlowTooltip){activeFlowTooltip.remove();activeFlowTooltip=null}
 }
 function showFlowTooltip(anchor,node,row,branch=null){
  hideFlowTooltip();
  const tip=flowTooltip(node,row,branch);
  tip.classList.add("meeting-flow-tooltip-floating");
  document.body.appendChild(tip);
  const rect=anchor.getBoundingClientRect(),gap=12,margin=12;
  const width=tip.offsetWidth,height=tip.offsetHeight;
  let left=rect.left+(rect.width/2)-(width/2);
  left=Math.max(margin,Math.min(left,window.innerWidth-width-margin));
  let top=rect.top-height-gap,placement="top";
  if(top<margin){top=rect.bottom+gap;placement="bottom"}
  const arrow=Math.max(18,Math.min(width-18,(rect.left+rect.width/2)-left));
  tip.style.left=Math.round(left)+"px";
  tip.style.top=Math.round(top)+"px";
  tip.style.setProperty("--flow-tooltip-arrow",Math.round(arrow)+"px");
  tip.dataset.placement=placement;
  activeFlowTooltip=tip;
 }

 function snapshotSection(title,subtitle=""){
  const section=el("section","flow-snapshot-section"),head=el("div","flow-snapshot-section-head");
  add(head,el("h4","",title));if(subtitle)add(head,el("small","muted",subtitle));add(section,head);return section;
 }
 function snapshotKv(label,value){
  const row=el("div","flow-snapshot-kv");add(row,el("span","",label),el("strong","",value||"ثبت نشده"));return row;
 }
 function renderSnapshot(panel,data,focusStage="",focusAction=""){
  panel.replaceChildren();
  const header=el("header","flow-snapshot-head"),copy=el("div");
  add(copy,el("span","secretary-eyebrow","آخرین وضعیت تجمیعی پرونده"),el("h3","",data.meeting?.title||"جزئیات پرونده"),el("p","muted","پرونده "+fmt(data.case_number)+" · جلسه "+(data.meeting?.meeting_no||"—")+" · "+(data.status_label||"")));
  const close=el("button","flow-snapshot-close","×");close.type="button";close.setAttribute("aria-label","بستن جزئیات پرونده");add(header,copy,close);add(panel,header);
  panel._closeButton=close;

  const overview=snapshotSection("اطلاعات اصلی");
  const grid=el("div","flow-snapshot-overview");
  add(grid,
   snapshotKv("تاریخ جلسه",data.meeting?.meeting_date?dateOnlyText(data.meeting.meeting_date):"ثبت نشده"),
   snapshotKv("ساعت شروع",data.meeting?.start_time),
   snapshotKv("مکان / لینک",data.meeting?.location),
   snapshotKv("دبیر",miniPerson(data.secretary)),
   snapshotKv("رئیس جلسه",miniPerson(data.chair)),
   snapshotKv("تاریخ ایجاد پرونده",data.meeting?.created_at?dateText(data.meeting.created_at):"ثبت نشده")
  );
  if(data.meeting?.objective)add(grid,snapshotKv("هدف جلسه",data.meeting.objective));
  if(data.meeting?.discussion)add(grid,snapshotKv("جمع‌بندی مذاکرات",data.meeting.discussion));
  if(data.meeting?.parking_lot)add(grid,snapshotKv("موارد پارکینگ",data.meeting.parking_lot));
  if(data.meeting?.closing_note)add(grid,snapshotKv("جمع‌بندی اختتام",data.meeting.closing_note));
  add(overview,grid);add(panel,overview);

  const people=snapshotSection("افراد و شرکت‌کنندگان",fmt((data.participants||[]).length)+" شرکت‌کننده ثبت‌شده");
  const peopleGrid=el("div","flow-snapshot-cards");
  add(peopleGrid,add(el("article","flow-snapshot-card"),el("strong","","دبیر"),el("span","",miniPerson(data.secretary))),
      add(el("article","flow-snapshot-card"),el("strong","","رئیس جلسه"),el("span","",miniPerson(data.chair))));
  for(const item of data.participants||[]){
   const card=el("article","flow-snapshot-card");add(card,el("strong","",miniPerson(item.person)));
   for(const detail of item.details||[])add(card,el("small","muted",detail.key+": "+detail.value));
   add(peopleGrid,card);
  }
  add(people,peopleGrid);add(panel,people);

  const agenda=snapshotSection("دستور جلسه",fmt((data.agenda||[]).length)+" ردیف");
  const agendaList=el("div","flow-snapshot-list");
  if(!(data.agenda||[]).length)add(agendaList,el("p","muted","دستور جلسه‌ای ثبت نشده است."));
  for(const item of data.agenda||[]){
   const card=el("article","flow-snapshot-list-row");
   add(card,el("strong","",fmt(item.index)+" · "+item.title),
    el("span","","ارائه‌دهنده: "+miniPerson(item.presenter)+(item.minutes?" · "+fmt(item.minutes)+" دقیقه":"")));
   add(agendaList,card);
  }
  add(agenda,agendaList);add(panel,agenda);

  const decisions=snapshotSection("مصوبات",fmt((data.decisions||[]).length)+" مصوبه");
  const decisionList=el("div","flow-snapshot-list");
  if(!(data.decisions||[]).length)add(decisionList,el("p","muted","مصوبه‌ای ثبت نشده است."));
  for(const item of data.decisions||[])add(decisionList,add(el("article","flow-snapshot-list-row"),el("strong","","مصوبه "+item.number),el("span","",item.text)));
  add(decisions,decisionList);add(panel,decisions);

  const actions=snapshotSection("اقدامات و شاخه‌های اجرایی",fmt((data.actions||[]).length)+" اقدام");
  const actionList=el("div","flow-snapshot-list");
  if(!(data.actions||[]).length)add(actionList,el("p","muted","اقدامی برای این جلسه ثبت نشده است."));
  for(const item of data.actions||[]){
   const card=el("article","flow-snapshot-action"+(focusAction===item.action_no?" is-focused":""));
   const top=el("div","flow-snapshot-action-head");
   add(top,el("strong","","اقدام "+item.action_no+" · "+item.title),badge(item.stage_label||item.state,"branch-state "+item.state));add(card,top);
   add(card,
    el("span","","مسئول: "+miniPerson(item.current_owner||item.owner)),
    el("span","","موعد: "+(item.due_date?dateOnlyText(item.due_date):"ثبت نشده")),
    el("span","","پیشرفت: "+fmt(item.progress_percent||0)+"٪")
   );
   if(item.decision_no)add(card,el("span","","مصوبه مرتبط: "+item.decision_no));
   const recent=(item.latest_fields||[]).filter(x=>x.value).slice(0,12);
   if(recent.length){
    const details=el("details","flow-snapshot-inline-details"),summary=el("summary","","آخرین داده‌های اقدام");
    add(details,summary);for(const field of recent)add(details,snapshotKv(field.key,field.value));add(card,details);
   }
   add(actionList,card);
  }
  add(actions,actionList);add(panel,actions);

  const stages=snapshotSection("آخرین اطلاعات جمع‌شده در تمام مراحل","فقط داده‌های ثبت‌شده و قابل مشاهده در همین پرونده");
  const stageList=el("div","flow-snapshot-stages");
  for(const stage of data.stages||[]){
   const block=el("details","flow-snapshot-stage"+(focusStage===stage.key?" is-focused":""));
   if(focusStage===stage.key)block.open=true;
   add(block,el("summary","",stage.title+" · "+stage.role));
   const values=el("div","flow-snapshot-stage-values");
   if(!(stage.fields||[]).length&&!(stage.actions||[]).length)add(values,el("p","muted","داده جدیدی برای این مرحله ثبت نشده است."));
   for(const field of stage.fields||[])add(values,snapshotKv(field.label,field.value));
   for(const action of stage.actions||[]){
    const group=el("div","flow-snapshot-stage-action");add(group,el("strong","","اقدام "+action.action_no+" · "+action.title));
    for(const field of action.fields||[])add(group,snapshotKv(field.label,field.value));add(values,group);
   }
   add(block,values);add(stageList,block);
  }
  add(stages,stageList);add(panel,stages);

  const history=snapshotSection("تاریخچه عبور از مراحل",fmt((data.stage_history||[]).length)+" رویداد");
  const timeline=el("div","flow-snapshot-timeline");
  if(!(data.stage_history||[]).length)add(timeline,el("p","muted","تاریخچه‌ای برای نمایش وجود ندارد."));
  for(const event of data.stage_history||[]){
   const item=el("div","flow-snapshot-timeline-row "+event.state);
   add(item,el("i"),add(el("div"),el("strong","",event.stage_title),
    el("span","",miniPerson(event.owner)),
    el("small","muted",(event.delegated_at?"ورود: "+dateText(event.delegated_at):"")+(event.finished_at?" · پایان: "+dateText(event.finished_at):""))));
   add(timeline,item);
  }
  add(history,timeline);add(panel,history);
 }
 async function openSnapshot(row,focusStage="",focusAction=""){
  const overlay=el("div","meeting-flow-snapshot-overlay"),panel=el("div","meeting-flow-snapshot-panel");
  overlay.setAttribute("role","dialog");overlay.setAttribute("aria-modal","true");overlay.setAttribute("aria-label","جزئیات کامل پرونده "+row.case_number);
  add(panel,el("div","flow-snapshot-loading","در حال دریافت آخرین اطلاعات پرونده..."));add(overlay,panel);document.body.appendChild(overlay);
  document.body.classList.add("flow-snapshot-open");
  const close=()=>{document.removeEventListener("keydown",onKey);document.body.classList.remove("flow-snapshot-open");overlay.remove()};
  const onKey=e=>{if(e.key==="Escape")close()};
  document.addEventListener("keydown",onKey);
  overlay.addEventListener("click",e=>{if(e.target===overlay)close()});
  try{
   const result=await request(sourceApi(sourceId,"/secretary/flow-graph/"+encodeURIComponent(row.case_uid)+"/snapshot"),{
    method:"POST",headers:{"Content-Type":"application/json"},
    body:JSON.stringify({pack_id:packId,person_uid:person.value||null})
   });
   if(!overlay.isConnected)return;
   renderSnapshot(panel,result,focusStage,focusAction);
   panel._closeButton?.addEventListener("click",close);panel._closeButton?.focus();
  }catch(e){
   panel.replaceChildren(note(e.message,true));
   const b=link("بستن",close,"button secondary");add(panel,b);
  }
 }
 function stageNodeButton(node,row,branch=null,compact=false){
  const n=el("button",(compact?"branch-mini-node ":"case-git-node ")+node.state);
  n.type="button";n.dataset.stage=node.key;n.setAttribute("aria-label",(node.title||"مرحله")+"؛ برای مشاهده جزئیات کلیک کنید");
  if(compact)add(n,el("span","branch-mini-label",node.title));
  else add(n,el("span","case-git-dot"),el("span","case-git-label",node.title),el("small","",node.role));
  n.addEventListener("mouseenter",()=>showFlowTooltip(n,node,row,branch));
  n.addEventListener("mouseleave",hideFlowTooltip);
  n.addEventListener("focus",()=>showFlowTooltip(n,node,row,branch));
  n.addEventListener("blur",hideFlowTooltip);
  n.addEventListener("click",()=>{hideFlowTooltip();openSnapshot(row,node.key,branch?.action_no||"")});
  return n;
 }
 function actionBranches(row){
  const branches=row.action_branches||[];
  if(!branches.length)return null;
  const corridor=el("section","case-branch-corridor");
  const split=el("div","case-branch-hub split");split.title="انشعاب پرونده‌های واقعی اقدام";add(split,el("i"),el("span","","اقدام‌ها"));
  const lanes=el("div","case-branch-lanes");
  for(const branch of branches){
   const historyStages=(branch.history||[]).map(x=>x.stage);
   const reworked=historyStages.filter(x=>x==="action_execution").length>1;
   const lane=el("article","case-branch-lane "+branch.state+(reworked?" has-rework":""));
   const head=el("button","case-branch-lane-head");head.type="button";
   add(head,el("strong","",branch.action_no||"اقدام"),el("span","",branch.title||"اقدام جلسه"));
   head.addEventListener("click",()=>openSnapshot(row,branch.stage||"action_execution",branch.action_no));
   const owner=branch.current_owner||branch.owner;
   const route=el("div","case-branch-route");
   const execution=(branch.nodes||[]).find(x=>x.key==="action_execution")||{key:"action_execution",title:"اجرای اقدام",state:"future",role:"اقدام‌کننده"};
   const review=(branch.nodes||[]).find(x=>x.key==="action_review")||{key:"action_review",title:"بررسی اقدام",state:"future",role:"دبیر"};
   add(route,stageNodeButton(execution,row,branch,true),el("span","case-branch-link"),stageNodeButton(review,row,branch,true));
   if(reworked)add(route,el("span","case-rework-loop","↶ اصلاح و اجرای مجدد"));
   const foot=el("div","case-branch-lane-foot");
   add(foot,el("span","",owner?miniPerson(owner):"مسئول ثبت نشده"),
    el("span","",branch.case_number?"پرونده اقدام "+fmt(branch.case_number):"در انتظار ایجاد پرونده"),
    badge(branch.stage_label||"در انتظار","branch-state "+branch.state));
   add(lane,head,route,foot);add(lanes,lane);
  }
  const merge=el("div","case-branch-hub merge");merge.title="تکمیل همه اقدامات و ادامه پایش جلسه";add(merge,el("i"),el("span","",row.topology?.all_branches_closed?"تکمیل":"انتظار"));
  add(corridor,split,lanes,merge);return corridor;
 }
 function historyDetails(row){
  const d=el("details","meeting-flow-details"),summary=el("summary","","جزئیات جریان پرونده");
  add(d,summary);
  const wrap=el("div","meeting-flow-details-grid");
  const overview=el("div","meeting-flow-detail-card");
  add(overview,el("strong","","خلاصه پرونده"),
   el("p","","شماره پرونده: "+fmt(row.case_number)),
   el("p","","شماره جلسه: "+row.meeting_no),
   el("p","","تاریخ جلسه: "+dateOnlyText(row.meeting_date)),
   el("p","","پیشرفت: "+fmt(row.progress_percent)+"٪"),
   link("مشاهده آخرین اطلاعات کامل پرونده",()=>openSnapshot(row),"button secondary"));
  const ownersBox=el("div","meeting-flow-detail-card");
  add(ownersBox,el("strong","","مسئولان فعلی"));
  if(!(row.current_owners||[]).length)add(ownersBox,el("p","muted","وظیفه باز با مسئول مشخص وجود ندارد."));
  for(const p of row.current_owners||[])add(ownersBox,el("p","",miniPerson(p)+" · "+(p.unit||"واحد ثبت نشده")));
  const history=el("div","meeting-flow-detail-card meeting-flow-history");
  add(history,el("strong","","تاریخچه Taskها"));
  if(!(row.history||[]).length)add(history,el("p","muted","تاریخچه قابل نمایش نیست."));
  for(const item of row.history||[]){
   const line=el("div","meeting-flow-history-row "+item.state);
   add(line,el("i"),add(el("div"),el("b","",item.stage_title),el("small","",miniPerson(item.owner)+(item.delegated_at?" · "+dateText(item.delegated_at):""))));
   add(history,line);
  }
  add(wrap,overview,ownersBox,history);add(d,wrap);return d;
 }
 function graphRow(row){
  const article=el("article","meeting-flow-case");
  const top=el("div","meeting-flow-case-head"),title=el("div","meeting-flow-case-heading");
  add(title,el("span","meeting-flow-case-kicker","پرونده "+fmt(row.case_number)+" · جلسه "+row.meeting_no),el("strong","meeting-flow-case-title",row.title),el("small","muted",(row.meeting_date?"تاریخ "+dateOnlyText(row.meeting_date)+" · ":"")+"آخرین مرحله: "+row.current_stage_title));
  const state=badge(row.status_label,"status-"+row.status);add(top,title,state);
  const meta=el("div","meeting-flow-meta");
  add(meta,badge("نقش: "+(row.my_role_label||"مشارکت")),badge("مرحله جاری: "+row.current_stage_title,"current"),badge("الان دست: "+row.current_owner_label,"owner"));
  const planned=Number(row.actions?.planned||0),materialized=Number(row.actions?.total||0);
  if(planned||materialized)add(meta,badge("اقدام‌ها: "+fmt(planned||materialized)+(materialized?" · پرونده ساخته‌شده "+fmt(materialized):" · هنوز پرونده اقدام ساخته نشده"),"actions"));
  const graphShell=el("div","meeting-flow-graph-shell"),map=el("div","case-process-map case-process-map-integrated");
  map.setAttribute("aria-label","مسیر پیشرفت و شاخه‌های پرونده "+row.case_number);
  const branches=row.action_branches||[];
  if(!branches.length){
   const linear=el("div","case-git-graph case-git-graph-linear");
   for(const node of row.nodes||[])add(linear,stageNodeButton(node,row));
   add(map,linear);
  }else{
   const before=el("div","case-git-graph case-git-graph-before");
   for(const node of (row.nodes||[]).filter(node=>["invitation","invitation_approval","minutes","minutes_approval"].includes(node.key)))add(before,stageNodeButton(node,row));
   add(map,before);
   const corridor=actionBranches(row);if(corridor)add(map,corridor);
   const monitoring=(row.nodes||[]).find(node=>node.key==="monitoring");
   if(monitoring){const after=el("div","case-git-graph case-git-graph-after");add(after,stageNodeButton(monitoring,row));add(map,after)}
  }
  add(graphShell,map);
  const progress=el("div","meeting-flow-progress");
  const label=el("div","meeting-flow-progress-label");add(label,el("span","","پیشرفت پرونده"),el("strong","",fmt(row.progress_percent)+"٪"));
  const bar=el("div","meeting-flow-progress-bar"),fill=el("span");fill.style.width=Math.max(0,Math.min(100,row.progress_percent||0))+"%";add(bar,fill);add(progress,label,bar);
  add(article,top,meta,graphShell,progress,historyDetails(row));
  if(branches.length)connectCaseBranches(map);
  return article;
 }

 function connectCaseBranches(map){
  // Measure the rendered nodes: curved paths stay attached after resize, font
  // loading and horizontal scrolling. Draft-only actions never enter this map.
  map.classList.add("measured-flow");
  const svg=document.createElementNS("http://www.w3.org/2000/svg","svg");
  svg.classList.add("case-flow-connections");svg.setAttribute("aria-hidden","true");map.prepend(svg);
  let observer;
  function draw(){
   if(!map.isConnected){observer?.disconnect();return}
   svg.replaceChildren();svg.setAttribute("width",map.scrollWidth);svg.setAttribute("height",map.scrollHeight);
   const base=map.getBoundingClientRect();
   const point=(element,side="center")=>{const b=element.getBoundingClientRect();return {x:(side==="right"?b.right:side==="left"?b.left:(b.left+b.right)/2)-base.left+map.scrollLeft,y:(b.top+b.bottom)/2-base.top}};
   const path=(a,b)=>{const p=document.createElementNS(svg.namespaceURI,"path"),mid=(a.x+b.x)/2;
    p.setAttribute("d",`M ${a.x} ${a.y} C ${mid} ${a.y}, ${mid} ${b.y}, ${b.x} ${b.y}`);svg.appendChild(p)};
   const split=map.querySelector(".split i"),merge=map.querySelector(".merge i");
   const before=map.querySelector(".case-git-graph-before .case-git-node:last-child .case-git-dot");
   const after=map.querySelector(".case-git-graph-after .case-git-dot");
   if(before&&split)path(point(before),point(split));
   if(merge&&after)path(point(merge),point(after));
   for(const lane of map.querySelectorAll(".case-branch-lane")){
    if(split)path(point(split),point(lane,"right"));
    if(merge)path(point(lane,"left"),point(merge));
   }
  }
  requestAnimationFrame(()=>{draw();if(map.isConnected){observer=new ResizeObserver(draw);observer.observe(map);for(const lane of map.querySelectorAll(".case-branch-lane"))observer.observe(lane)}});
 }

 async function loadGraph(resetPage=false){
  if(loading)return;
  if(period.value==="custom"&&((from.value&&!to.value)||(!from.value&&to.value))){toast("برای بازه دلخواه، تاریخ شروع و پایان را با هم انتخاب کنید.");return}
  if(resetPage)offset=0;loading=true;refresh.disabled=true;body.replaceChildren(note("در حال ساخت گراف واقعی پرونده‌ها و شاخه‌های اقدام..."));
  try{
   const r=await request(sourceApi(sourceId,"/secretary/flow-graph"),{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(payload())});
   if(!body.isConnected)return;
   if(!loadedOptions){
    personOptions(r.filters?.people,r.person?.uid);
    refill(role,r.filters?.roles);refill(status,r.filters?.statuses);refill(stage,r.filters?.stages);
    loadedOptions=true;
   }
   refill(owner,r.filters?.owners,"uid","name");refill(unit,r.filters?.units);
   body.replaceChildren();
   const stats=el("div","meeting-flow-kpis");
   const statDefs=[
    [r.summary.total_cases,"کل پرونده‌های این نما","⌘","total"],
    [r.summary.active_cases,"فعال","●","active"],
    [r.summary.completed_cases,"تکمیل‌شده","✓","completed"],
    [r.summary.waiting_my_action,"منتظر اقدام شخص","!","waiting"],
    [r.summary.average_progress+"٪","میانگین پیشرفت","↗","progress"]
   ];
   for(const [value,label,icon,kind] of statDefs){
    const box=el("div","meeting-flow-kpi "+kind),ico=el("span","meeting-flow-kpi-icon",icon),copy=el("div");
    add(copy,el("span","",label),el("strong","",typeof value==="number"?fmt(value):value));add(box,ico,copy);add(stats,box);
   }add(body,stats);
   const context=el("div","meeting-flow-context");
   add(context,el("span","meeting-flow-scope","نمایش برای "+(r.person?.name||r.person?.username||"کاربر انتخاب‌شده")),el("span","muted",fmt(r.total)+" پرونده مطابق فیلترها"));
   add(body,context);
   if(r.truncated)add(body,note("بیش از ۱۰۰۰ پرونده در دامنه اولیه وجود دارد؛ برای پوشش کامل بازه را محدود کنید.",true));
   const list=el("div","meeting-flow-list");
   if(!(r.rows||[]).length)add(list,el("div","secretary-empty","پرونده‌ای با این زاویه دید پیدا نشد. فیلترها یا نمای سریع را تغییر دهید."));
   for(const row of r.rows||[])add(list,graphRow(row));
   add(body,list);
   const pager=el("div","meeting-flow-pager");
   if(offset>0)add(pager,link("صفحه قبل",()=>{offset=Math.max(0,offset-30);loadGraph()},"button secondary"));
   if(r.has_more)add(pager,link("صفحه بعد",()=>{offset+=30;loadGraph()},"button secondary"));
   if(pager.childNodes.length)add(body,pager);
  }catch(e){body.replaceChildren(note(e.message,true))}
  finally{loading=false;refresh.disabled=false}
 }

 let timer=null;
 search.addEventListener("input",()=>{activePerspective="all";syncPerspective();clearTimeout(timer);timer=setTimeout(()=>loadGraph(true),350)});
 person.addEventListener("change",()=>{loadedOptions=false;activePerspective="all";waitingOnly=false;syncPerspective();loadGraph(true)});
 period.addEventListener("change",()=>{if(period.value!=="custom"){from.value="";to.value=""}activePerspective="all";syncPerspective();loadGraph(true)});
 for(const control of [role,status,stage,owner,unit,actionScope,sort])control.addEventListener("change",()=>{activePerspective="all";waitingOnly=false;syncPerspective();loadGraph(true)});
 for(const control of [from,to])control.addEventListener("change",()=>{period.value="custom";activePerspective="all";syncPerspective();if(from.value&&to.value)loadGraph(true)});
 await loadGraph(true);
}

async function secretaryPage(sourceId=null,packId=null,sectionId="inbox",initialManifest=null){
 const m=root();m.classList.add("secretary-workspace");heading(m,"دبیر هوشمند","از دعوت تا پیگیری مصوبات؛ هر کار در زمان و کارتابل خودش.");
 if(!sourceId){add(m,note("اتصال BPMS را از منوی کنار انتخاب کنید."));return}
 const base=sourceApi(sourceId,"/secretary"),out=el("div"),editor=el("div");add(m,out,editor);
 const post=(path,body={},options={})=>request(base+path,{...options,method:"POST",headers:{"Content-Type":"application/json",...(options.headers||{})},body:JSON.stringify(body)});
 const checked=fn=>async()=>{try{await fn()}catch(e){toast(e.message)}};
 const stages=[
  ["invitation","دعوت جلسه","دبیر"],
  ["invitation_approval","تأیید دعوت‌نامه","رئیس جلسه"],
  ["minutes","ثبت صورت‌جلسه","دبیر"],
  ["minutes_approval","تأیید صورت‌جلسه","رئیس جلسه"],
  ["action_execution","اجرای اقدام","اقدام‌کننده"],
  ["action_review","بررسی اقدام","دبیر"],
  ["monitoring","پایش و اختتام","دبیر"]
 ];
 let info,stageFilter=null;
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
   info={...manifest,...personal,tasks:manifest.tasks,notifications:manifest.notifications,sessions:manifest.sessions,packs:[manifest.process],workflow_tasks:personal.tasks};
  }else info=await request(base+"/inbox",{background:true});
  if(!m.isConnected||(packId&&(app.selectedSourceId!==sourceId||app.processChoices[sourceId]?.packId!==packId||app.processChoices[sourceId]?.section!==sectionId)))return;
  out.replaceChildren();out.hidden=editor.dataset.editing==="true";
  const allTasks=info.workflow_tasks||info.tasks||[];
  const unread=(info.notifications||[]).filter(n=>!n.read).length;
  const currentPack=packId||info.packs[0]?.id;
  const top=el("section","secretary-hero"),intro=el("div","secretary-hero-copy");
  add(intro,el("span","secretary-eyebrow","میز کار جلسات"),el("h2","",info.packs[0]?.title||"جلسه‌ها از اینجا شروع می‌شوند"),el("p","","دعوت را آغاز کنید؛ ادامهٔ کار با رسیدن پرونده به شما فعال می‌شود."));
  const metrics=el("div","secretary-metrics");
  for(const [value,label] of [[allTasks.length,"وظیفه در کارتابل"],[unread,"اعلان تازه"],[(info.sessions||[]).filter(x=>x.status==="draft").length,"پیش‌نویس دعوت"]]){
   const metric=el("div","secretary-metric");add(metric,el("strong","",fmt(value)),el("span","",label));add(metrics,metric);
  }
  const actions=el("div","secretary-hero-actions");
  const create=link("+ دعوت جلسه",checked(async()=>{const r=await post("/sessions",{pack_id:currentPack});await session(r.id)}),"button primary secretary-create");
  create.disabled=!currentPack;create.dataset.action="new-invitation";
  add(actions,create,link("↻ تازه‌سازی",checked(load),"button secondary"));add(top,intro,metrics,actions);add(out,top);
  if(!info.packs.length)add(out,note("برای شروع، مدیر سامانه باید بسته جلسات این اتصال را فعال کند."));
  const flow=el("section","secretary-flow"),rail=el("div","secretary-steps");rail.setAttribute("aria-label","ترتیب مراحل فرایند جلسات");
  add(flow,el("h3","","مسیر جلسه"),el("p","muted","شماره‌ها ترتیب مراحل‌اند؛ نشان رنگی، تعداد پرونده‌های موجود در کارتابل شماست."));
  const taskArea=el("section","secretary-task-area");
  const drawTasks=()=>{
   taskArea.replaceChildren();
   const chosen=allTasks.filter(t=>!stageFilter||t.stage===stageFilter);
   const head=el("div","secretary-section-head");add(head,el("h3","",stageFilter?stages.find(x=>x[0]===stageFilter)?.[1]||"وظایف من":"منتظر اقدام شما"));
   if(stageFilter)add(head,link("همه وظایف",()=>{stageFilter=null;drawTasks();updateRail()},"button secondary"));add(taskArea,head);
   if(!chosen.length)add(taskArea,el("div","secretary-empty","فعلاً پرونده‌ای منتظر اقدام شما نیست. با «دعوت جلسه» شروع کنید؛ کارهای بعدی خودکار اینجا ظاهر می‌شوند."));
   const grid=el("div","secretary-task-grid");
   for(const t of chosen){
    const tile=el("article","secretary-task-card"),meta=el("div","secretary-task-meta");
    add(meta,el("span","secretary-stage-tag",t.stage_label||stages.find(x=>x[0]===t.stage)?.[1]||"وظیفه"),el("span","muted","پرونده "+t.number));
    add(tile,meta,el("h4","",t.title));
    const b=link("مشاهده و انجام وظیفه",checked(()=>open(t,!!info.oauth_connected)),"button secondary");b.dataset.caseUid=t.case_uid;b.disabled=!t.available;
    add(tile,b);
    if(!t.available)add(tile,el("small","muted",t.reminder_at?"زمان فعال‌شدن: "+dateText(t.reminder_at):"زمان پایش هنوز تکمیل نشده است."));
    add(grid,tile);
   }add(taskArea,grid);
   if(info.truncated)add(taskArea,note("نمایش به ۲۰۰ وظیفه محدود است؛ تعدادها مربوط به همین فهرست‌اند."));
  };
  const stepButtons=[];
  function updateRail(){for(const [key,b] of stepButtons)b.setAttribute("aria-pressed",String(stageFilter===key))}
  stages.forEach(([key,title,role],i)=>{
   const count=allTasks.filter(t=>t.stage===key).length;
   const step=link("",()=>{stageFilter=key;drawTasks();updateRail()},"secretary-step");step.disabled=count===0;step.dataset.stage=key;
   add(step,el("span","secretary-step-index",fmt(i+1)),el("strong","",title),el("small","",role));
   if(count)add(step,el("span","secretary-step-count",fmt(count)));
   else add(step,el("span","secretary-step-wait","در انتظار پرونده"));
   stepButtons.push([key,step]);add(rail,step);
  });add(flow,rail);add(out,flow,taskArea);drawTasks();updateRail();
  if(currentPack){
   const graphTarget=el("div","meeting-flow-slot");add(out,graphTarget);
   renderMeetingCaseFlowGraph(graphTarget,sourceId,currentPack).catch(e=>graphTarget.replaceChildren(note(e.message,true)));
  }
  const connection=card("مجوز عملیات حساب BPMS",info.oauth_connected?"مجوز شخصی حساب متصل فعال است.":"برای ثبت و انتقال مراحل، مجوز حساب خودتان در ProcessMaker لازم است.");
  if(info.oauth_connected)add(connection,link("قطع مجوز شخصی",checked(async()=>{await post("/oauth/disconnect");await load()})));
  else{
   const fields=[inputField("نام کاربری ProcessMaker",""),inputField("رمز ProcessMaker","","password"),inputField("OAuth Client ID",""),inputField("OAuth Client Secret","","password")];for(const f of fields)add(connection,f.wrap);
   add(connection,link("اتصال حساب خودم",checked(async()=>{await post("/oauth/connect",{username:fields[0].input.value,password:fields[1].input.value,client_id:fields[2].input.value,client_secret:fields[3].input.value});fields[1].input.value="";fields[3].input.value="";await load()})));
  }
  const connectionDetails=el("details","secretary-connection");
  add(connectionDetails,el("summary","",info.oauth_connected?"● حساب فرایندی متصل است":"اتصال حساب برای ارسال نهایی پرونده"),connection);add(out,connectionDetails);
  const notices=card("اعلان‌ها",String(info.notifications.filter(n=>!n.read).length)+" اعلان خوانده‌نشده");
  for(const n of info.notifications)add(notices,link((n.read?"":"● ")+n.task.stage_label+" · "+n.task.title,checked(async()=>{await post("/notifications/"+n.id+"/read");await open(n.task)})));
  if(info.notifications.length)add(out,notices);
  if(info.sessions.length){
   const drafts=card("دعوت‌های من","پیش‌نویس‌ها و وضعیت دعوت‌های ارسال‌شده");drafts.classList.add("secretary-drafts");
   for(const r of info.sessions)add(drafts,link(r.title+" · "+({draft:"پیش‌نویس",sent:"ارسال‌شده",reconciliation_required:"نیازمند بررسی"}[r.status]||r.status),checked(()=>session(r.id)),"button secondary"));add(out,drafts);
  }

 }
 async function open(t,prepare=true){
  try{
   const r=await post(prepare?"/tasks/open":"/tasks/load",{case_uid:t.case_uid,index:t.index,pack_id:t.pack_id});
   render(r,false);
  }catch(e){
   if(t.stage!=="minutes"||e.status!==503||!info?.oauth_connected)throw e;
   // The write path for FR-MTG-003 no longer depends on the read-only PM MySQL
   // adapter. If reporting/read access is temporarily unavailable, allow the
   // already-saved native case to continue through PM REST.
   editor.replaceChildren();editor.dataset.editing="true";out.hidden=true;
   add(editor,link("← بازگشت به میز کار",()=>{editor.replaceChildren();editor.dataset.editing="false";out.hidden=false},"button secondary secretary-back"));
   const fallback=card("ارسال صورت‌جلسه ثبت‌شده","اتصال خواندنی گزارش‌های ProcessMaker در دسترس نیست، اما این مرحله برای ارسال به تأیید صورت‌جلسه فقط از REST و مجوز شخصی همان حساب استفاده می‌کند.");
   add(fallback,note("پرونده "+fmt(t.number)+" · همان Case موجود؛ پرونده جدید ساخته نمی‌شود."));
   const advance=link("ارسال همین صورت‌جلسه به تأیید",checked(async()=>{
    advance.disabled=true;
    try{
     await post("/tasks/"+encodeURIComponent(t.case_uid)+"/"+encodeURIComponent(t.index)+"/advance-minutes?pack_id="+encodeURIComponent(t.pack_id),{revision:1,confirmed:true});
     editor.replaceChildren(note("صورت‌جلسه ثبت‌شده با موفقیت به مرحله «تأیید صورت‌جلسه» ارسال شد."));
    }finally{advance.disabled=false}
   }),"button primary");
   add(fallback,advance);add(editor,fallback);
  }
 }
 async function session(id){const r=await request(base+"/sessions/"+encodeURIComponent(id));render({...r,draft:r.session,task:{stage:"invitation",title:r.session.values.MTG_MeetingTitle||"جلسه جدید"}},true)}
 function render(r,isSession){
  editor.replaceChildren();editor.dataset.editing="true";out.hidden=true;
  add(editor,link("← بازگشت به میز کار",checked(async()=>{editor.replaceChildren();editor.dataset.editing="false";out.hidden=false;await load()}),"button secondary secretary-back"));
  const d=r.draft,t=r.task,values=structuredClone(d.values||{});let assistant=r.assistant||{};
  const stageLabels={invitation:"دعوت‌نامه",invitation_approval:"تأیید دعوت‌نامه",minutes:"صورت‌جلسه",minutes_approval:"تأیید صورت‌جلسه",action_execution:"گزارش اجرای اقدام",action_review:"بررسی اقدام",monitoring:"پایش و اختتام"};
  const p=card(t.title||"دبیر هوشمند",isSession?"ایجاد دعوت‌نامه با گفت‌وگو":"مرحله: "+(stageLabels[t.stage]||t.stage));p.classList.add("secretary-editor-card");
  const requirednessLive=r.requiredness?.live!==false;
  if(!requirednessLive)add(p,note(r.requiredness?.warning||"تنظیم Required زنده ProcessMaker فعلاً قابل خواندن نیست. می‌توانید اطلاعات را ویرایش کنید، اما ارسال نهایی تا بازیابی metadata متوقف است."));
  const stageProgress=el("div","secretary-editor-progress");stageProgress.setAttribute("aria-label","مرحله جاری پرونده");
  stages.forEach(([key,label],i)=>{const step=el("span",key===t.stage?"is-current":"",fmt(i+1)+" · "+label);if(key===t.stage)step.setAttribute("aria-current","step");add(stageProgress,step)});add(editor,stageProgress);
  const path=isSession?"/sessions/"+encodeURIComponent(d.id):"/tasks/"+t.case_uid+"/"+t.index;
  const query=isSession?"":"?pack_id="+encodeURIComponent(t.pack_id);
  const status=el("div"),controls=[],locked=d.status!=="draft"&&!(t.stage==="minutes"&&d.status==="reconciliation_required");let dirty=false;
  let send;
  function changed(){
   dirty=true;
   if(send)send.disabled=true;
   if(chatMinutesSend)chatMinutesSend.disabled=true;
   if(chatStageSend)chatStageSend.disabled=true;
   if(sessionStart)sessionStart.disabled=true;
   status.replaceChildren(note("تغییرات فرم ذخیره نشده‌اند؛ ابتدا ذخیره کنید."));
  }
  function workflowDateKey(key){
   return /DateTime|FormDate|persiandate|ActualDate/i.test(String(key||""));
  }
  function workflowDisplayValue(key,value){
   if(value==null||value==="")return value??"";
   if(workflowDateKey(key)&&typeof value==="string")return dateOnlyText(value);
   if(Array.isArray(value))return value.map(x=>workflowDisplayValue(key,x));
   if(typeof value==="object"){
    const mapped={};for(const [childKey,childValue] of Object.entries(value))mapped[childKey]=workflowDisplayValue(childKey,childValue);
    return JSON.stringify(mapped);
   }
   return String(value);
  }
  function control(key,spec,value,change){
   const baseLabel=spec.label||key,label=workflowDateKey(key)?baseLabel+" ("+calendarName()+")":baseLabel,wrap=el("label","field secretary-field");wrap.classList.add("field-"+String(spec.type||"text"));add(wrap,el("span","",label));let input;
   let options=spec.options||[];
   if(key.endsWith("UID"))options=(r.people||[]).map(x=>({value:x.uid,label:x.name}));
   if(key==="MTG_InvitationApproval"||key==="MTG_MinutesApproval")options=[{value:"Approved",label:"تأیید"},{value:"NeedsRevision",label:"نیاز به اصلاح"}];
   if(options.length){input=el("select");add(input,el("option","","انتخاب کنید"));for(const x of options){const o=el("option","",x.label||x.value);o.value=x.value;add(input,o)}input.value=value||""}
   else if(workflowDateKey(key)){
    const picker=dateControl(value,{storage:"jalali"});input=picker.input;
    picker.display.setAttribute("aria-label",label);picker.display.disabled=locked||key==="MTG_MonActionNo";picker.toggle.disabled=picker.display.disabled;
    input.addEventListener("input",()=>{change(input.value);changed()});add(wrap,picker.control);controls.push(picker.display);return wrap;
   }
   else{input=el(spec.type==="textarea"?"textarea":"input");input.value=value??"";input.maxLength=14000}
   input.setAttribute("aria-label",label);input.disabled=locked||key==="MTG_MonActionNo";input.addEventListener("input",()=>{change(input.value);changed()});add(wrap,input);controls.push(input);return wrap;
  }

  const conversation=card("گفت‌وگو با دبیر هوشمند","مثل یک چت معمولی پیام بدهید؛ متن، صوت و فایل در همین گفتگو پردازش می‌شوند.");
  conversation.classList.add("secretary-conversation");
  const chat=el("div","secretary-chat");
  const history=d.history||[];
  let chatPinned=true;
  function nearChatBottom(){
   return chat.scrollHeight-chat.scrollTop-chat.clientHeight<90;
  }
  function scrollChat({force=false,smooth=true}={}){
   if(!force&&!chatPinned)return;
   requestAnimationFrame(()=>{
    if(!chat.isConnected)return;
    chat.scrollTo({top:chat.scrollHeight,behavior:smooth?"smooth":"auto"});
   });
  }
  chat.addEventListener("scroll",()=>{chatPinned=nearChatBottom()},{passive:true});
  function secretaryDisplayText(role,text){
   let value=String(text||"");
   if(role!=="assistant")return value;
   const labels={
    MTG_ActionOwnerUID:"مسئول اصلی اقدام",
    MTG_MeetingEndTime:"ساعت پایان واقعی جلسه",
    MTG_PlannedActionEndTime:"ساعت پایان برنامه‌ریزی‌شده",
    MTG_MeetingEndDateTime:"تاریخ پایان برنامه‌ریزی‌شده",
    MTG_ParticipantUserUID:"شرکت‌کننده",
    MTG_AgendaPresenterUID:"ارائه‌دهنده",
    MTG_ChairUserUID:"رئیس جلسه",
    MTG_SecretaryUserUID:"دبیر جلسه"
   };
   for(const [key,label] of Object.entries(labels)){
    value=value.replace(new RegExp("`?"+key+"`?","g"),label);
   }
   return value;
  }
  function addChatBubble(role,text,extra="",options={}){
   const bubble=el("div","chat-bubble "+role+(extra?" "+extra:""));
   add(bubble,el("small","",role==="user"?"شما":"دبیر هوشمند"),secretaryRichText(secretaryDisplayText(role,text)));
   const messageTools=el("div","chat-message-tools");
   add(messageTools,link("کپی",async()=>{try{await navigator.clipboard.writeText(text)}catch{toast("کپی خودکار ممکن نشد؛ متن را انتخاب و کپی کنید.")}},"button secondary compact-action"));
   if(role==="user")add(messageTools,link("ویرایش و ارسال دوباره",()=>{notes.value=text;autosize();notes.focus()},"button secondary compact-action"));
   add(bubble,messageTools);add(chat,bubble);
   if(options.summary){
    const details=el("details","chat-summary-details"),summary=el("summary","","خلاصه اطلاعات استخراج‌شده");
    add(details,summary,el("pre","chat-summary",options.summary));add(bubble,details);
   }
   if(options.scroll)scrollChat({force:!!options.force,smooth:options.smooth!==false});
   return bubble;
  }
  if(history.length){
   for(const turn of history){
    const bubble=addChatBubble(turn.role==="user"?"user":"assistant",turn.text||"","",{summary:turn.summary||""});
    if(turn.source==="file")bubble.querySelector("small").textContent="فایل شما";
   }
  }else if(assistant.message)addChatBubble("assistant",assistant.message);
  // Initial history is positioned once, without replaying an animated scroll for
  // every old message. Subsequent turns are appended incrementally.
  requestAnimationFrame(()=>{if(chat.isConnected){chat.scrollTop=chat.scrollHeight;chatPinned=true}});
  add(conversation,chat);

  let missing=assistant.missing||r.missing||[],chatMinutesSend=null,chatStageSend=null,chatMinutesHint=null,sessionStart=null,sessionStartHint=null;
  const progress=el("div","secretary-progress"),receiptPanel=el("details","secretary-change-receipt");
  const undoButton=link("بازگردانی آخرین تغییر",checked(async()=>{
   if(sending||dirty)throw Error("ابتدا پردازش یا اصلاحات دستی را تمام کنید.");
   undoButton.disabled=true;
   try{await applyResult(await post(path+"/undo"+query,{revision:d.revision}))}
   finally{undoButton.disabled=locked||!d.can_undo}
  }),"button secondary compact-action");
  undoButton.classList.add("secretary-undo");
  function refreshReceipt(){
   receiptPanel.replaceChildren();const change=d.last_change||{};
   receiptPanel.hidden=!change.count;
   add(receiptPanel,el("summary","",(d.agent_receipt?.label||"تغییرات پیش‌نویس")+" · "+(change.count||0)+" تغییر"));
   for(const item of change.items||[])add(receiptPanel,el("p","",item.label+": "+item.before+" ← "+item.after));
   if(change.truncated)add(receiptPanel,el("p","","برای مشاهده همه تغییرات، فرم را باز کنید."));
   undoButton.hidden=!d.can_undo;undoButton.disabled=locked||!d.can_undo;
  }
  refreshReceipt();add(conversation,receiptPanel,undoButton);
  add(conversation,progress);
  // Stage transition CTA lives next to completion status so it cannot disappear
  // below the chat composer after a successful extraction.
  const stageReadyActions=el("div","secretary-stage-ready-actions");
  add(conversation,stageReadyActions);
  const contextSummary=el("details","secretary-context-summary"),summaryTitle=el("summary","",["invitation_approval","minutes_approval"].includes(t.stage)?"خلاصه برای تصمیم شما":"خلاصه اطلاعات استخراج‌شده"),summaryBody=el("pre");
  add(contextSummary,summaryTitle,summaryBody);add(conversation,contextSummary);
  function refreshConversationMeta(){
   progress.textContent=missing.length?("برای تکمیل این مرحله "+missing.length+" مورد باقی مانده؛ دبیر آن‌ها را یکی‌یکی می‌پرسد."):"اطلاعات این مرحله کامل است.";
   summaryBody.textContent=assistant.summary||"";
   contextSummary.hidden=!assistant.summary;
   if(chatMinutesSend)chatMinutesSend.disabled=locked||dirty||missing.length>0||!info.oauth_connected||!requirednessLive;
   if(chatStageSend)chatStageSend.disabled=locked||dirty||missing.length>0||!info.oauth_connected||!requirednessLive;
   if(sessionStart){sessionStart.hidden=missing.length>0;sessionStart.disabled=locked||dirty||missing.length>0||!info.oauth_connected||!requirednessLive}
   if(sessionStartHint){
    sessionStartHint.textContent=!requirednessLive?"قبل از ایجاد پرونده، AVAN باید تنظیم Required زنده ProcessMaker را بخواند. دسترسی SELECT جدول DYNAFORM را بررسی کنید.":"پیش‌نویس کامل است؛ برای ایجاد پرونده و ارسال آن به کارتابل رئیس، ابتدا «اتصال حساب خودم» را فعال کنید.";
    sessionStartHint.hidden=missing.length>0||(!!info.oauth_connected&&requirednessLive);
   }
   if(chatMinutesHint){
    chatMinutesHint.textContent=missing.length?(missing.length+" مورد باید قبل از ارسال تکمیل شود؛ دبیر آن‌ها را یکی‌یکی می‌پرسد."):"صورت‌جلسه کامل است و آماده ارسال برای تأیید است.";
    chatMinutesHint.classList.toggle("ok",!missing.length);
   }
  }
  refreshConversationMeta();

  const composer=el("div","secretary-composer"),composerBox=el("div","secretary-composer-box"),notes=el("textarea","secretary-composer-input");
  notes.maxLength=18000;notes.rows=1;notes.setAttribute("aria-label","پیام به دبیر هوشمند");
  notes.placeholder=isSession?"پیامتان را بنویسید؛ مثلاً زمان، مکان، رئیس، شرکت‌کنندگان و دستور جلسه...":"تصمیم، اصلاحات یا اطلاعات این مرحله را بنویسید...";
  const tools=el("div","secretary-composer-tools"),statusLine=el("div","secretary-send-status muted");
  let sending=false,sendMessage,stopButton=null,currentController=null,currentOperationId=null;
  function autosize(){notes.style.height="auto";notes.style.height=Math.min(notes.scrollHeight,180)+"px"}
  notes.addEventListener("input",autosize);
  function beginOperation(kind){
   const id=makeRequestId(),controller=new AbortController();
   currentOperationId=id;currentController=controller;app.activeOperation={id,kind,controller};
   return {id,controller};
  }
  function clearOperation(id){
   if(currentOperationId===id){currentOperationId=null;currentController=null}
   if(app.activeOperation?.id===id)app.activeOperation=null;
  }
  function setSending(value,label=""){
   sending=value;composer.classList.toggle("is-sending",value);notes.disabled=value;
   if(sendMessage)sendMessage.disabled=value||locked;
   if(sessionStart)sessionStart.disabled=value||locked||dirty||missing.length>0||!info.oauth_connected||!requirednessLive;
   if(chatStageSend)chatStageSend.disabled=value||locked||dirty||missing.length>0||!info.oauth_connected||!requirednessLive;
   if(stopButton)stopButton.hidden=!value;
   statusLine.textContent=label;
  }
  async function cancelCurrent(){
   if(!sending||!currentOperationId)return;
   const id=currentOperationId,controller=currentController;
   statusLine.textContent="در حال توقف پردازش در سرور...";
   if(stopButton)stopButton.disabled=true;
   try{
    await request("/api/operations/"+encodeURIComponent(id)+"/cancel",{method:"POST",audit:false});
    statusLine.textContent="پردازش متوقف شد.";
    controller?.abort();
   }catch(e){
    statusLine.textContent="توقف پردازش تأیید نشد: "+errorDescription(e);
    if(stopButton)stopButton.disabled=false;
   }
  }
  function renderMessageError(error,text,fromVoice,errorBubble=null){
   if(errorBubble)errorBubble.remove();
   const stopped=error?.code==="ABORTED";
   const message=String(error?.message||"");
   const externalMutation=!stopped&&/ProcessMaker/.test(message)&&/(Trigger بعد از فرم|ثبت نهایی اطلاعات مرحله|ارسال پرونده به مرحله بعد)/.test(message);
   const bubble=addChatBubble("assistant",stopped?"پردازش به درخواست شما متوقف شد.":"خطا در پردازش پیام: "+errorDescription(error),stopped?"cancelled":"error");
   const actions=el("div","chat-error-actions");
   if(externalMutation){
    add(actions,link("↻ بررسی وضعیت پرونده",checked(async()=>{
     if(isSession)await session(d.id);else await open(t,false);
    }),"button secondary"));
   }else{
    add(actions,link("↻ تلاش مجدد",()=>sendTurn(text,fromVoice,true,bubble),"button secondary"));
   }
   const editButton=link("✎ ویرایش پیام",()=>{notes.value=text;autosize();notes.focus()},"button secondary");
   const logsButton=link("☷ مشاهده لاگ",()=>{app.pendingLogRequestId=error?.requestId||"";select("support-logs")},"button secondary");
   const dismissButton=link("× بستن",()=>bubble.remove(),"button secondary");
   add(actions,editButton,logsButton,dismissButton);add(bubble,actions);
   return bubble;
  }
  function thinkingBubble(label="دبیر در حال بررسی پیام شماست"){
   const bubble=el("div","chat-bubble assistant thinking"),row=el("div","typing-row"),dots=el("span","typing-dots");
   add(dots,el("i"),el("i"),el("i"));add(row,el("span","typing-label",label),dots);
   add(bubble,el("small","","دبیر هوشمند"),row);add(chat,bubble);
   scrollChat({smooth:true});return bubble;
  }

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
    editor.dataset.editing="false";
    editor.replaceChildren(note(result.assistant?.message||"پرونده به مرحله بعد منتقل شد."));
    await load();return
   }
   const nextDraft=isSession?result.session:result.draft;
   const nextAssistant=result.assistant||{};
   if(!nextDraft){
    if(nextAssistant.message)addChatBubble("assistant",nextAssistant.message,"",{scroll:true});
    return;
   }

   // Keep this editor and chat DOM alive. Only merge the new server state and
   // append the newest assistant turn, like a normal chat application.
   const previousRevision=Number(d.revision||0);
   const serverHistory=Array.isArray(nextDraft.history)?nextDraft.history:[];
   const latestAssistant=[...serverHistory].reverse().find(x=>x?.role==="assistant");
   const assistantText=latestAssistant?.text||nextAssistant.message||"";
   const assistantSummary=latestAssistant?.summary||nextAssistant.summary||"";
   const wait=chat.querySelector(".chat-bubble.thinking");if(wait)wait.remove();
   if(assistantText)addChatBubble("assistant",assistantText,"",{summary:assistantSummary,scroll:true});

   d.revision=nextDraft.revision;d.status=nextDraft.status;
   d.history=serverHistory;d.questions=nextDraft.questions||[];
   d.attachments=nextDraft.attachments||[];d.pending_confirmation=nextDraft.pending_confirmation||null;
   d.values=nextDraft.values||{};
   d.last_change=nextDraft.last_change;d.agent_receipt=nextDraft.agent_receipt;d.can_undo=nextDraft.can_undo;refreshReceipt();
   for(const key of Object.keys(values))delete values[key];
   Object.assign(values,structuredClone(nextDraft.values||{}));
   renderFormFields();
   assistant=nextAssistant;
   missing=nextAssistant.missing||result.missing||[];
   refreshConversationMeta();
   dirty=false;
   status.replaceChildren();
   if(send)send.disabled=locked||missing.length>0||!info.oauth_connected||!requirednessLive;
   if(chatMinutesSend)chatMinutesSend.disabled=locked||dirty||missing.length>0||!info.oauth_connected||!requirednessLive;
   if(chatStageSend)chatStageSend.disabled=locked||dirty||missing.length>0||!info.oauth_connected||!requirednessLive;
   if(app.preferences.secretary_auto_play_voice)await detachedSpeech();

   // If the form is currently open, tell the user that its values changed
   // without destroying/rebuilding the conversation DOM.
   if(formDetails?.open&&Number(nextDraft.revision||0)!==previousRevision){
    formSummary.textContent="مشاهده / اصلاح فرم استخراج‌شده · اطلاعات جدید ثبت شد";
   }
  }
  async function latestConversationState(){
   if(isSession){
    const fresh=await request(base+"/sessions/"+encodeURIComponent(d.id),{audit:false});
    return {revision:fresh.session?.revision||d.revision,payload:fresh};
   }
   const fresh=await post("/tasks/load",{case_uid:t.case_uid,index:t.index,pack_id:t.pack_id},{audit:false});
   return {revision:fresh.draft?.revision||d.revision,payload:fresh};
  }
  async function sendTurn(textValue=null,fromVoice=false,retry=false,errorBubble=null){
   if(locked||sending)return false;
   if(dirty)throw Error("ابتدا اصلاحات دستی فرم را ذخیره کنید.");
   const text=(textValue??notes.value).trim();if(!text)throw Error("پیامی برای ارسال وارد کنید.");
   if(!retry){notes.value="";autosize();chatPinned=true;addChatBubble("user",text,"",{scroll:true,force:true})}
   if(errorBubble)errorBubble.remove();
   thinkingBubble(retry?"دبیر دوباره در حال بررسی همین پیام است":"دبیر در حال بررسی پیام شماست");
   let operation=beginOperation("secretary_turn");
   setSending(true,retry?"در حال تلاش مجدد...":"در حال پردازش پیام... برای توقف از دکمه «توقف» استفاده کنید.");
   const submit=async revision=>post(path+"/turn"+query,{
     revision,text,auto_advance:!!info.oauth_connected,request_id:operation.id
    },{signal:operation.controller.signal,requestId:operation.id});
   try{
    let result;
    try{
     result=await submit(d.revision);
    }catch(e){
     const conflict=e?.status===409&&/پیش.?نویس.*تغییر|revision|نسخه/i.test(String(e?.message||""));
     if(!conflict||e?.code==="ABORTED")throw e;
     // A stale browser revision must not trap the conversation in repeated 409s.
     // The failed attempt did not mutate the draft, so refresh the current draft
     // and replay this same user message once with a new operation id.
     const wait=chat.querySelector(".chat-bubble.thinking");if(wait)wait.remove();
     thinkingBubble("پیش‌نویس تازه شد؛ همان پیام را روی نسخه جدید اعمال می‌کنم");
     clearOperation(operation.id);
     const fresh=await latestConversationState();
     operation=beginOperation("secretary_turn_resync");
     currentOperationId=operation.id;currentController=operation.controller;
     result=await submit(fresh.revision);
    }
    await applyResult(result,fromVoice);return true;
   }catch(e){
    const wait=chat.querySelector(".chat-bubble.thinking");if(wait)wait.remove();
    renderMessageError(e,text,fromVoice,errorBubble);return false;
   }finally{
    clearOperation(operation.id);
    if(composer.isConnected)setSending(false,"");
   }
  }

  const file=el("input","secretary-hidden-input");file.type="file";
  file.accept=".pdf,.docx,.txt,.md,.csv,.json,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document,text/plain,text/csv,application/json";
  file.setAttribute("aria-label","افزودن فایل به گفت‌وگوی دبیر");
  const attachButton=link("فایل",()=>file.click(),"button icon-button");attachButton.title="افزودن فایل";
  add(tools,attachButton,file);

  attachVoiceInput(tools,notes,false,sourceId,async text=>{if(app.preferences.voice_auto_send)await sendTurn(text,true)},true);
  stopButton=link("■ توقف",cancelCurrent,"button danger secretary-stop");stopButton.hidden=true;stopButton.title="توقف پردازش جاری";
  sendMessage=link("↑",()=>sendTurn().catch(e=>toast(errorDescription(e))),"button primary secretary-send");sendMessage.title="ارسال پیام";add(tools,stopButton,sendMessage);
  notes.addEventListener("keydown",e=>{if(e.key==="Enter"&&!e.shiftKey){e.preventDefault();sendTurn().catch(err=>toast(err.message))}});

  async function uploadConversationFile(selected){
   if(!selected||sending)return;
   if(dirty){statusLine.textContent="ابتدا اصلاحات دستی فرم را ذخیره کنید.";file.value="";return}
   chatPinned=true;addChatBubble("user","📎 "+selected.name,"",{scroll:true,force:true});thinkingBubble("دبیر در حال خواندن فایل است");
   const operation=beginOperation("secretary_attachment");
   setSending(true,"در حال خواندن و استخراج اطلاعات فایل... برای توقف از دکمه «توقف» استفاده کنید.");
   try{
    const sep=query?"&":"?";
    const result=await request(base+path+"/attachment"+query+sep+"revision="+encodeURIComponent(d.revision),{
     method:"POST",requestId:operation.id,signal:operation.controller.signal,
     headers:{"Content-Type":selected.type||"application/octet-stream","X-AVAN-Filename":encodeURIComponent(selected.name)},
     body:selected
    });
    await applyResult(result,false);
   }catch(e){
    const wait=chat.querySelector(".chat-bubble.thinking");if(wait)wait.remove();
    const bubble=addChatBubble("assistant",e.code==="ABORTED"?"پردازش فایل به درخواست شما متوقف شد.":"خطا در پردازش فایل: "+errorDescription(e),e.code==="ABORTED"?"cancelled":"error");
    add(bubble,add(el("div","chat-error-actions"),link("☷ مشاهده لاگ",()=>select("support-logs"),"button secondary")));
   }finally{
    clearOperation(operation.id);file.value="";if(composer.isConnected)setSending(false,"");
   }
  }
  file.addEventListener("change",()=>uploadConversationFile(file.files?.[0]).catch(e=>toast(e.message)));
  composerBox.addEventListener("dragover",e=>{e.preventDefault();composerBox.classList.add("dragging")});
  composerBox.addEventListener("dragleave",()=>composerBox.classList.remove("dragging"));
  composerBox.addEventListener("drop",e=>{e.preventDefault();composerBox.classList.remove("dragging");uploadConversationFile(e.dataTransfer?.files?.[0]).catch(err=>toast(err.message))});

  const audio=el("audio","secretary-audio");audio.controls=true;audio.hidden=true;let audioPart=0,audioUrl=null;
  const speech=link("شنیدن",async()=>{
   if(dirty||sending)return;
   try{
    const speechQuery=isSession?("?part="+audioPart):(query+"&part="+audioPart);
    const response=await request(base+path+"/speech"+speechQuery,{method:"POST",binary:true});
    if(audioUrl)URL.revokeObjectURL(audioUrl);audioUrl=URL.createObjectURL(await response.blob());audio.src=audioUrl;audio.hidden=false;
    const count=Number(response.headers.get("X-AVAN-Audio-Parts"))||1;audioPart=(audioPart+1)%count;await audio.play();
   }catch(e){toast(e.message)}
  },"button icon-button");speech.title="شنیدن پاسخ دبیر";add(tools,speech);
  app.cleanup.push(()=>{audio.pause();if(audioUrl)URL.revokeObjectURL(audioUrl)});

  add(composerBox,notes,tools);add(composer,composerBox,statusLine,audio);

  if(["invitation_approval","minutes_approval"].includes(t.stage)){
   const quick=el("div","secretary-quick-actions");
   const approveText=t.stage==="invitation_approval"?"دعوت‌نامه را تأیید می‌کنم":"صورت‌جلسه را تأیید می‌کنم";
   const approve=link("✓ تأیید و ارسال",()=>sendTurn(approveText).catch(e=>toast(e.message)),"button primary");approve.disabled=!info.oauth_connected||!requirednessLive;
   add(quick,approve,link("↩ نیاز به اصلاح",()=>{notes.value="نیاز به اصلاح: ";notes.focus();autosize()},"button secondary"));
   add(composer,quick);
  }
  if(!isSession&&t.stage==="minutes"){
   const quick=el("div","secretary-quick-actions secretary-minutes-submit");
   chatMinutesSend=link("ارسال صورت‌جلسه به تأیید",checked(async()=>{
    if(dirty)throw Error("ابتدا اصلاحات دستی فرم را ذخیره کنید.");
    chatMinutesSend.disabled=true;
    try{
     await post(path+"/advance-minutes"+query,{revision:d.revision||1,confirmed:true});
     editor.dataset.editing="false";
     editor.replaceChildren(note("صورت‌جلسه با موفقیت به مرحله «تأیید صورت‌جلسه» ارسال شد."));
     setTimeout(()=>load().catch(()=>{}),400);
    }finally{
     if(chatMinutesSend?.isConnected)chatMinutesSend.disabled=locked||dirty||missing.length>0||!info.oauth_connected||!requirednessLive;
    }
   }),"button primary");
   chatMinutesSend.disabled=locked||dirty||!info.oauth_connected||!requirednessLive;
   add(quick,chatMinutesSend);
   if(missing.length)add(quick,el("small","muted","کنترل نهایی الزامات هنگام ارسال توسط خود ProcessMaker انجام می‌شود."));
   add(composer,quick);
  }
  if(!isSession&&["action_execution","action_review","monitoring"].includes(t.stage)){
   const quick=el("div","secretary-quick-actions secretary-stage-submit");
   function stageSubmitLabel(){
    if(t.stage==="action_execution")return "ارسال گزارش اقدام برای بررسی دبیر";
    if(t.stage==="action_review"){
     const decision=String(values.MTGA_ReviewStatus2||"");
     if(decision==="Closed")return "تأیید و بستن اقدام";
     if(decision==="Rework")return "بازگشت اقدام برای اصلاح";
     return "ثبت بررسی و ارسال";
    }
    return "ثبت پایش و اختتام جلسه";
   }
   chatStageSend=link(stageSubmitLabel(),checked(async()=>{
    if(dirty)throw Error("ابتدا اصلاحات دستی فرم را ذخیره کنید.");
    if(missing.length)throw Error("ابتدا موارد الزامی این مرحله را تکمیل کنید.");
    chatStageSend.disabled=true;
    try{
     const submitEndpoint=["action_execution","action_review"].includes(t.stage)?"/advance-action":"/submit";
     await post(path+submitEndpoint+query,{revision:d.revision||1,confirmed:true});
     editor.dataset.editing="false";
     editor.replaceChildren(note(
      t.stage==="action_execution"?"گزارش اقدام ثبت و برای بررسی دبیر ارسال شد.":
      t.stage==="action_review"?(String(values.MTGA_ReviewStatus2||"")==="Rework"?"اقدام برای اصلاح به مجری بازگردانده شد.":"بررسی اقدام ثبت و پرونده به مسیر بعدی ارسال شد."):
      "پایش ثبت و پرونده به مسیر بعدی ارسال شد."
     ));
     await load();
    }finally{
     if(chatStageSend?.isConnected)chatStageSend.disabled=locked||dirty||missing.length>0||!info.oauth_connected||!requirednessLive;
    }
   }),"button primary");
   chatStageSend.disabled=locked||dirty||missing.length>0||!info.oauth_connected||!requirednessLive;
   add(quick,chatStageSend);
   if(missing.length)add(quick,el("small","muted",missing.length+" مورد باید قبل از ارسال تکمیل شود."));
   add(stageReadyActions,quick);
  }
  if(isSession&&d.status==="draft"){
   sessionStart=link("ایجاد گام اول و ارسال به رئیس",()=>sendTurn("بله، ایجاد و ارسال کن").catch(e=>toast(e.message)),"button primary secretary-session-start");
   sessionStartHint=note("پیش‌نویس کامل است؛ برای ایجاد پرونده و ارسال آن به کارتابل رئیس، ابتدا «اتصال حساب خودم» را فعال کنید.");
   add(composer,sessionStart,sessionStartHint);refreshConversationMeta();
  }
  if(isSession&&d.status==="reconciliation_required"){
   const warning=note("این دعوت قبلاً یک Case در ProcessMaker ساخته است، اما ادامه عملیات کامل نشده. برای جلوگیری از پرونده تکراری، AVAN Case جدید نمی‌سازد.",true);
   add(composer,warning);
   if(d.case_uid)add(composer,el("small","muted","شناسه پرونده موجود: "+d.case_uid));
   if(d.last_error)add(composer,note("آخرین خطا: "+d.last_error,true));
   const resume=link("ادامه همان پرونده و تطبیق اطلاعات",checked(async()=>{
    resume.disabled=true;
    try{
     const result=await post(path+"/reconcile",{revision:d.revision,confirmed:true});
     editor.dataset.editing="false";editor.replaceChildren(note("همان پرونده ProcessMaker تکمیل و برای رئیس جلسه ارسال شد."));
     await load();
    }finally{resume.disabled=!info.oauth_connected}
   }),"button primary");
   resume.disabled=!info.oauth_connected;add(composer,resume);
  }

  if(!isSession&&Object.keys(r.file_controls||{}).length){
   const nativeTitle=t.stage==="minutes"?"پیوست صورت‌جلسه":
    t.stage==="minutes_approval"?"مشاهده پیوست صورت‌جلسه":
    t.stage==="action_execution"?"مستندات اجرای اقدام":
    t.stage==="action_review"?"مشاهده مستندات اجرای اقدام":"پیوست‌های ProcessMaker";
   const nativeFiles=card(nativeTitle,"فایل‌ها مستقیماً در همان Case و Input Document تعریف‌شده در PMX ذخیره می‌شوند و در مرحله بررسی بعدی قابل مشاهده‌اند.");
   nativeFiles.classList.add("secretary-native-files");
   function nativeFileUrl(field,suffix=""){
    return base+path+"/native-files"+suffix+query+"&field="+encodeURIComponent(field);
   }
   async function downloadNativeFile(field,doc){
    const url=nativeFileUrl(field,"/"+encodeURIComponent(doc.app_doc_uid)+"/download")+"&version="+encodeURIComponent(doc.app_doc_version);
    const response=await request(url,{method:"GET",binary:true});
    const blob=await response.blob(),objectUrl=URL.createObjectURL(blob),a=document.createElement("a");
    a.href=objectUrl;a.download=doc.app_doc_filename||"document";document.body.appendChild(a);a.click();a.remove();
    setTimeout(()=>URL.revokeObjectURL(objectUrl),1500);
   }
   for(const [field,spec] of Object.entries(r.file_controls||{})){
    const section=el("div","secretary-native-file-control"),head=el("div","secretary-native-file-head"),list=el("div","secretary-native-file-list");
    add(head,el("strong","",spec.label||field));
    if(spec.mode!=="view"&&spec.mode!=="disabled"){
     const picker=el("input");picker.type="file";picker.setAttribute("aria-label","انتخاب "+(spec.label||"فایل"));
     const upload=link("بارگذاری فایل در ProcessMaker",checked(async()=>{
      const selected=picker.files?.[0];if(!selected)throw Error("ابتدا فایل را انتخاب کنید.");
      upload.disabled=true;
      try{
       await request(nativeFileUrl(field),{
        method:"POST",
        headers:{"Content-Type":selected.type||"application/octet-stream","X-AVAN-Filename":encodeURIComponent(selected.name)},
        body:selected
       });
       toast("فایل با موفقیت در ProcessMaker ثبت شد.");
       picker.value="";await loadFiles();
      }finally{upload.disabled=false}
     }),"button secondary");
     add(head,picker,upload);
    }else add(head,el("span","badge","فقط مشاهده"));
    async function loadFiles(){
     list.replaceChildren(el("span","muted","در حال دریافت فایل‌ها..."));
     try{
      const data=await request(nativeFileUrl(field),{method:"GET",audit:false});
      list.replaceChildren();
      for(const doc of data.documents||[]){
       const row=el("div","secretary-native-file-row");
       add(row,el("span","",doc.app_doc_filename||"فایل"),
        el("small","muted","نسخه "+(doc.app_doc_version||"1")+(doc.app_doc_create_date?" · "+doc.app_doc_create_date:"")),
        link("مشاهده / دریافت",()=>downloadNativeFile(field,doc).catch(e=>toast(e.message)),"button secondary compact-action"));
       add(list,row);
      }
      if(!(data.documents||[]).length)add(list,note("هنوز فایلی برای این بخش ثبت نشده است."));
     }catch(e){list.replaceChildren(note("دریافت فایل‌ها انجام نشد: "+errorDescription(e),true))}
    }
    add(section,head,list);add(nativeFiles,section);loadFiles();
   }
   add(composer,nativeFiles);
  }

  if((d.attachments||[]).length){
   const attachments=el("div","secretary-attachments");add(attachments,el("strong","","فایل‌های استفاده‌شده"));
   for(const a of d.attachments)add(attachments,el("span","badge",(a.name||"فایل")+" · "+(a.type||"")));
   add(composer,attachments);
  }
  add(conversation,composer);add(p,conversation);

  const formDetails=el("details","secretary-form-details"),formSummary=el("summary","","مشاهده / اصلاح فرم استخراج‌شده"),formBody=el("div","secretary-form-body"),fieldsHost=el("div","secretary-fields-host");
  add(formDetails,formSummary,formBody);add(formBody,fieldsHost);
  function renderFormFields(){
  fieldsHost.replaceChildren();const scalarGrid=el("div","secretary-form-grid");add(fieldsHost,scalarGrid);
  for(const [key,spec] of Object.entries(r.form||{})){
   if(["file","multipleFile"].includes(spec.type))continue;
   if(spec.type==="grid"){
    const box=card(spec.label||key),rows=el("div","secretary-grid-rows");box.classList.add("secretary-grid-card");
    let data=values[key]&&typeof values[key]==="object"?values[key]:{};values[key]=data;
    function draw(){rows.replaceChildren();for(const [no,row] of Object.entries(data)){
     const item=card("ردیف "+no);item.classList.add("secretary-grid-row");
     const fields=el("div","secretary-grid-row-fields");
     for(const col of spec.columns||[])add(fields,control(col.id,col,row[col.id]||"",v=>row[col.id]=v));
     add(item,fields);
     if(key!=="MTG_ActionSummary")add(item,link("حذف ردیف",()=>{delete data[no];changed();draw()},"button secondary compact-action"));add(rows,item);
    }}draw();add(box,rows);
    if(key!=="MTG_ActionSummary"&&!locked)add(box,link("+ افزودن ردیف",()=>{const n=String(Math.max(0,...Object.keys(data).map(Number))+1);data[n]={};draw();changed()},"button secondary compact-action"));add(fieldsHost,box);
   }else add(scalarGrid,control(key,spec,values[key],v=>values[key]=v));
  }
  }
  renderFormFields();
  const context=el("details");add(context,el("summary","","شرح ثبت‌شده در فرایند"));
  for(const [k,v] of Object.entries(r.context||{})){const label=r.form?.[k]?.label||k;add(context,el("p","",label+": "+workflowDisplayValue(k,v)))}add(formBody,context);
  const save=link("ذخیره اصلاحات",checked(async()=>{await post(path+"/edit"+query,{revision:d.revision,values});if(isSession)await session(d.id);else await open(t,false)}));save.disabled=locked;
  send=link(t.stage==="minutes"?"ارسال صورت‌جلسه به تأیید":"تأیید بازبینی و ارسال به مرحله بعد",checked(async()=>{
   send.disabled=true;
   try{
    const endpoint=t.stage==="minutes"?(path+"/advance-minutes"+query):(path+"/submit"+query);
    await post(endpoint,{revision:d.revision||1,confirmed:true});
    editor.dataset.editing="false";
    editor.replaceChildren(note(t.stage==="minutes"?"صورت‌جلسه با موفقیت به مرحله «تأیید صورت‌جلسه» ارسال شد.":"اطلاعات در BPMS ثبت و به مرحله بعد ارسال شد."));
    if(t.stage==="minutes"){setTimeout(()=>load().catch(()=>{}),500)}
    else await load();
   }finally{if(send?.isConnected)send.disabled=locked||dirty||missing.length>0||!info.oauth_connected||!requirednessLive}
  }),"button primary");
  send.disabled=locked||missing.length>0||!info.oauth_connected||!requirednessLive;
  add(formBody,save,send,status);add(p,formDetails);

  if(!isSession&&t.stage==="monitoring")add(p,link("پیشنهاد جلسه پیگیری اقدامات باز",checked(async()=>{const row=await post(path+"/followup"+query);await session(row.id);await load()})));
  if(!isSession&&["action_review","monitoring"].includes(t.stage)){
   const evidence=card("اسناد و پیشنهاد بررسی","اسناد TXT و PDF دارای متن، با مجوز حساب BPMS شما خوانده می‌شوند. پیشنهاد هوش مصنوعی نیازمند تصمیم دبیر است."),list=el("div"),advice=el("div");
   add(evidence,link("دریافت اسناد پرونده",checked(async()=>{const docs=await post(path+"/documents"+query);list.replaceChildren();for(const doc of docs.documents)add(list,link(doc.app_doc_filename+" · نسخه "+doc.app_doc_version,checked(async()=>{if(dirty)throw Error("ابتدا اصلاحات را ذخیره کنید.");await post(path+"/evidence"+query,{revision:d.revision,doc_id:doc.app_doc_uid,version:Number(doc.app_doc_version)});await open(t,false)})));if(!docs.documents.length)add(list,note("سندی با مجوز فعلی در دسترس نیست؛ نبود سند به معنی تکمیل اقدام نیست."))})),list,
    link("پیشنهاد دبیر براساس گزارش و اسناد",checked(async()=>{const result=await post(path+"/advice"+query);advice.replaceChildren(el("p","",result.summary),note("پیشنهاد برای تصمیم شما: "+result.proposal),el("small","muted","تعداد اسناد خوانده‌شده: "+result.document_count));for(const q of result.quotes)add(advice,el("blockquote","",q));for(const q of result.missing)add(advice,note(q));})),advice);add(p,evidence);
  }
  if(!isSession&&d.status==="reconciliation_required"&&t.stage!=="minutes"){
   let recovery;
   if(d.recovery==="route_only"){
    recovery=card("ادامه امن همان پرونده","اطلاعات و Trigger این مرحله ثبت شده‌اند و فقط Route نهایی کامل نشده است. برای جلوگیری از اجرای دوباره Triggerها، AVAN فقط انتقال همین پرونده را تکرار می‌کند.");
    if(d.last_error)add(recovery,note("آخرین خطا: "+d.last_error,true));
    const routeOnly=link("ادامه Route همین پرونده",checked(async()=>{
     routeOnly.disabled=true;
     try{
      await post(path+"/reconcile-route"+query,{revision:d.revision,confirmed:true});
      editor.dataset.editing="false";
      editor.replaceChildren(note("همان پرونده بدون اجرای دوباره Triggerها به مرحله بعد ارسال شد."));
      await load();
     }finally{routeOnly.disabled=!info.oauth_connected}
    }),"button primary");
    routeOnly.disabled=!info.oauth_connected;add(recovery,routeOnly);
   }else{
    recovery=card("نیازمند بررسی پرونده","بخشی از عملیات ProcessMaker شروع شده اما نقطه توقف برای اجرای خودکار دوباره قطعی نیست. برای جلوگیری از ثبت تکراری، ارسال مجدد خودکار غیرفعال است.");
    if(d.last_error)add(recovery,note("آخرین خطا: "+d.last_error,true));
    add(recovery,link("☷ مشاهده لاگ مرتبط",()=>select("support-logs"),"button secondary"));
   }
   add(p,recovery);
  }
  add(editor,p);editor.scrollIntoView({behavior:"smooth"});
 }
 await load();let busy=false;const timer=setInterval(async()=>{if(busy||!m.isConnected)return;busy=true;try{await load()}catch{}finally{busy=false}},60000);app.cleanup.push(()=>clearInterval(timer));
}
function inputField(label,value,type="text"){
 const wrap=el("label","field");
 if(type==="date"){
  const picker=dateControl(value);picker.display.setAttribute("aria-label",label);picker.input.setAttribute("aria-label",label);
  add(wrap,el("span","",label),picker.control);return {wrap,input:picker.input,picker};
 }
 const input=el(type==="textarea"?"textarea":"input");
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
  for(const [key,label,type] of [["description","شرح اقدام","textarea"],["source_quote","عبارت مستند از متن اولیه","textarea"],["suggested_role","سمت پیشنهادی","text"],["owner_reason","دلیل انتخاب مسئول","text"],["proposed_due_date","موعد "+calendarName(),"date"],["due_reason","دلیل موعد پیشنهادی","text"]]){
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
function attachVoiceInput(target,input,platform=false,sourceId=null,onTranscript=null,compact=false){
 const wrap=el("div","voice-bar"+(compact?" compact":"")),status=el("span","muted");
 let recorder=null,stream=null,timer=null,discard=false,busy=false,pendingBlob=null;
 const manualConvert=link("تبدیل به متن",async()=>{
  if(!pendingBlob||busy)return;
  const blob=pendingBlob;pendingBlob=null;manualConvert.hidden=true;await convert(blob);
 },"button secondary voice-convert");
 manualConvert.hidden=true;
 const cleanup=()=>{
  discard=true;pendingBlob=null;manualConvert.hidden=true;
  if(timer)clearTimeout(timer);
  if(recorder?.state==="recording")recorder.stop();
  stream?.getTracks().forEach(t=>t.stop());
 };app.cleanup.push(cleanup);
 function readyForTranscription(blob){
  if(discard||!blob)return;
  if(app.preferences.voice_auto_transcribe){
   void convert(blob);return;
  }
  pendingBlob=blob;manualConvert.hidden=false;
  status.textContent="صوت آماده است؛ برای تبدیل به متن، «تبدیل به متن» را بزنید.";
 }
 async function convert(blob){
  if(busy||discard)return;
  if(blob.size>8*1024*1024){status.textContent="حداکثر حجم صوت ۸ مگابایت است.";return}
  busy=true;button.disabled=true;upload.disabled=true;manualConvert.disabled=true;
  status.textContent="در حال تبدیل صوت به متن...";
  try{
   const endpoint=platform?"/api/platform/voice/transcribe":sourceApi(sourceId,"/voice/transcribe");
   const r=await request(endpoint,{method:"POST",headers:{"Content-Type":blob.type||"audio/mpeg"},body:blob});
   if(!input.isConnected)return;
   if(r.text.length>input.maxLength){status.textContent="متن از ظرفیت این کادر بیشتر است؛ فایل کوتاه‌تری انتخاب کنید.";return}
   input.value=r.text;input.dispatchEvent(new Event("input",{bubbles:true}));
   status.textContent=app.preferences.voice_auto_send&&onTranscript
    ?"متن آماده شد و طبق تنظیم حساب در حال ارسال است..."
    :"متن آماده است؛ قبل از ارسال بازبینی کنید.";
   if(onTranscript)await onTranscript(r.text);
  }catch(e){
   status.textContent="تبدیل صوت انجام نشد: "+errorDescription(e);
  }finally{
   busy=false;button.disabled=false;upload.disabled=false;manualConvert.disabled=false;upload.value="";
  }
 }
 const button=link(compact?"ضبط":"ضبط سؤال / یادداشت",async()=>{
  if(recorder?.state==="recording"){recorder.stop();return}
  if(!window.isSecureContext||!navigator.mediaDevices?.getUserMedia||!window.MediaRecorder){
   status.textContent="ضبط به HTTPS یا localhost نیاز دارد؛ می‌توانید فایل صوت انتخاب کنید.";return
  }
  try{
   stream=await navigator.mediaDevices.getUserMedia({audio:true});
   if(discard){stream.getTracks().forEach(t=>t.stop());return}
   const mime=["audio/webm;codecs=opus","audio/mp4"].find(x=>MediaRecorder.isTypeSupported(x));
   if(!mime)throw Error("قالب ضبط مرورگر پشتیبانی نمی‌شود؛ فایل صوت انتخاب کنید.");
   recorder=new MediaRecorder(stream,{mimeType:mime});const chunks=[];
   recorder.ondataavailable=e=>{if(e.data.size)chunks.push(e.data)};
   recorder.onstop=()=>{
    clearTimeout(timer);stream?.getTracks().forEach(t=>t.stop());
    button.textContent=compact?"ضبط":"ضبط سؤال / یادداشت";
    if(!discard)readyForTranscription(new Blob(chunks,{type:mime.split(";")[0]}));
   };
   recorder.start();button.textContent=compact?"■":"پایان ضبط";
   status.textContent="در حال ضبط؛ حداکثر ۹۰ ثانیه";
   timer=setTimeout(()=>{if(recorder.state==="recording")recorder.stop()},90000);
  }catch(e){stream?.getTracks().forEach(t=>t.stop());status.textContent=errorDescription(e)}
 });
 const upload=el("input");upload.type="file";
 upload.accept="audio/webm,audio/ogg,audio/wav,audio/mpeg,audio/mp4,.m4a";
 upload.setAttribute("aria-label","انتخاب فایل صوت برای تبدیل به متن");
 upload.addEventListener("change",()=>{if(upload.files[0])readyForTranscription(upload.files[0])});
 if(compact){
  upload.className="secretary-hidden-input";button.classList.add("icon-button");button.title="ضبط صوت";
  status.classList.add("voice-compact-status");add(wrap,button,upload,manualConvert,status);
 }else{
  add(wrap,button,upload,manualConvert,
   el("small","muted",app.preferences.voice_auto_transcribe
    ?"پس از ضبط، صوت طبق تنظیم حساب شما خودکار به متن تبدیل می‌شود."
    :"پس از ضبط، تبدیل به متن فقط با تأیید شما انجام می‌شود."),
   status);
 }
 add(target,wrap);
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
  ["period","بازه",[["all","همه زمان‌ها"],["this_month","ماه جاری "+calendarName()],["last_month","ماه قبل "+calendarName()],["last_30_days","۳۰ روز گذشته"],["last_7_days","۷ روز گذشته"]]],
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
 for(const [v,t] of [["last_30_days","۳۰ روز گذشته"],["this_month","ماه جاری "+calendarName()],["last_month","ماه قبل"],["all","همه زمان‌ها"]]){const o=el("option","",t);o.value=v;add(period,o)}
 const from=inputField("از تاریخ "+calendarName()+" (اختیاری)","","date"),to=inputField("تا تاریخ "+calendarName()+" (غیرشامل)","","date");
 add(controls,add(el("label"),el("span","","فرایند"),process),add(el("label"),el("span","","بازه"),period),from.wrap,to.wrap);
 let offset=0,known=new Set();const query=()=>({process_uid:process.value||null,period:period.value,start:from.input.value||null,end:to.input.value||null,offset,limit:30});
 function table(headers,rows){const t=el("table"),h=el("tr");headers.forEach(x=>add(h,el("th","",x)));add(t,h);for(const values of rows){const r=el("tr");values.forEach(x=>add(r,el("td","",x==null?"—":x)));add(t,r)}return add(el("div","table-scroll"),t)}
 function bars(title,rows){const p=card(title),max=Math.max(1,...rows.map(x=>x[1]));for(const [label,value] of rows){const r=el("div","bi-bar-row"),meter=el("meter");meter.min=0;meter.max=max;meter.value=value;meter.setAttribute("aria-label",label);add(r,el("span","",label),meter,el("strong","",fmt(value)));add(p,r)}return p}
 async function load(reset=true){if(reset)offset=0;out.replaceChildren(note("در حال خواندن اطلاعات گردش کار..."));try{const r=await request(biBase+"/processes",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(query())});if(!out.isConnected)return;out.replaceChildren();
  for(const p of r.processes){if(known.has(p.process_uid))continue;known.add(p.process_uid);const o=el("option","",p.title);o.value=p.process_uid;add(process,o)}
  const metrics=el("div","stats");for(const [key,label] of [["cases","کل پرونده"],["open_cases","پرونده باز"],["completed_cases","تکمیل‌شده"],["open_tasks","وظیفه باز"],["overdue_tasks","وظیفه تأخیردار"],["median_cycle_hours","میانه چرخه (ساعت)"]])add(metrics,add(el("div","stat"),el("span","",label),el("strong","",r.metrics[key]==null?"نامشخص":fmt(r.metrics[key]))));add(out,metrics);
  if(!r.coverage_complete)add(out,note("بیش از ۲۰هزار پرونده در دامنه وجود دارد؛ دوره را محدود کنید. آمار حاضر فقط زیرمجموعه بازیابی‌شده است.",true));
  const charts=el("div","bi-charts");add(charts,bars("وضعیت پرونده‌ها",Object.entries(r.statuses).map(([k,v])=>[statusName(k),v])),bars("پرونده‌های ایجادشده در ماه "+calendarName(),r.monthly.map(x=>[x.month,x.count])));add(out,charts);
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
  for(const p of result.processes){const title=p.renderer==="meeting"?("مدیریت جلسات · "+p.title):("کارتابل عمومی · "+p.title);const o=el("option","",title);o.value=p.id;add(choice,o)}
  if(!result.processes.length){choice.disabled=true;message.textContent=(source.capabilities||[]).includes("secretary")?"بسته «مدیریت جلسات» برای این اتصال هنوز در مدیریت سامانه فعال نشده است.":"ماژول مدیریت جلسات برای این حساب فعال نیست.";return}
  const previous=app.processChoices[source.source_id]?.packId;
  choice.value=result.processes.some(p=>p.id===previous)?previous:result.processes[0].id;
  await apply(false);
 }catch(e){choice.disabled=true;message.textContent=e.message;add(group,link("دریافت دوباره فرایندها",()=>{choice.remove();message.remove();sections.remove();loadProcessChoices(source,group)}))}
}
async function intelligentMeetingPage(){
 const sourceId=app.selectedSourceId,m=root();
 heading(m,"اجرای هوشمند فرایند جلسات","محیط مکالمه‌ای نقش‌محور برای دبیر، رئیس جلسه، اقدام‌کننده و بررسی‌کننده؛ متصل به Task واقعی ProcessMaker.");
 if(!sourceId){add(m,note("ابتدا اتصال ProcessMaker را انتخاب کنید.",true));return}
 let list;
 try{list=await request(sourceApi(sourceId,"/process-workspace"))}catch(e){add(m,note(e.message,true));return}
 const meeting=(list.processes||[]).find(p=>p.adapter==="meeting_v2"&&p.renderer==="meeting");
 if(!meeting){
  let status=null;
  try{status=await request(sourceApi(sourceId,"/process-workspace/status"),{background:true})}catch{}
  const generic=(list.processes||[]).filter(p=>p.adapter==="native_tasks_v1");
  add(m,note("فرایندهای جلسه روی ProcessMaker متصل هستند، اما هنوز به بسته تخصصی «meeting_v2» آوان تبدیل نشده‌اند؛ بنابراین Chat/Voice/File نباید با کارتابل عمومی اشتباه نمایش داده شود.",true));
  if(generic.length){
   const box=card("فرایندهای فعلی","این موارد فعلاً فقط کارتابل عمومی هستند.");
   for(const p of generic)add(box,el("p","",p.title+" · native_tasks_v1"));
   add(m,box);
  }
  if(status?.promotion_warning)add(m,note(status.promotion_warning,true));
  add(m,note("پس از فعال شدن meeting_v2، همین صفحه به‌صورت خودکار محیط گفت‌وگوی هوشمند را برای وظیفه نقش فعلی باز می‌کند."));
  return
 }
 const current=app.processChoices[sourceId];
 app.processChoices[sourceId]={
  packId:meeting.id,
  section:(current?.packId===meeting.id&&current.section)?current.section:"inbox"
 };
 await processWorkspacePage();
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
