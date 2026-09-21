"use strict";
const app={user:null,csrf:null,page:"overview",cursor:null,meetings:[],questions:[],sending:false,pendingQuestion:null};
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
 app.page=page;
 const labels={overview:"نمای کلی",meetings:"جلسات و مصوبات",assistant:"دستیار مدیریتی"};
 $("breadcrumb").textContent=labels[page]||"آوان";
 document.querySelectorAll("#nav button").forEach(b=>b.classList.toggle("active",b.dataset.page===page));
 const m=root();add(m,el("p","muted","در حال دریافت اطلاعات سازمان..."));
 const work={overview:overview,meetings:meetingPage,assistant:assistantPage}[page];
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
 const text=el("textarea");text.id="management-question";text.maxLength=350;
 text.placeholder="سؤال مدیریتی خود را وارد کنید، یا یکی از پرسش‌های آماده را انتخاب کنید.";
 text.setAttribute("aria-label","سؤال مدیریتی");
 const send=link("دریافت پاسخ",()=>askQuestion(text.value),"button primary");
 const result=el("div");result.id="management-result";
 add(form,text,send,result);add(m,form);
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
    body:JSON.stringify({question:question.trim()})
  });
  if(!target.isConnected)return;
  target.replaceChildren();
  add(target,el("p","answer",result.answer),
      el("p","muted","بررسی "+fmt(result.meetings_considered)+" جلسه و "+
      fmt(result.actions_considered)+" اقدام · آخرین بررسی: "+result.as_of_utc));
  const sources=card("مستندات پاسخ","ارجاع به سوابق ثبت‌شده در جلسات");
  for(const entry of result.items||[]){
   const ref=entry.source||{},item=el("div","source");
   add(item,el("strong","",entry.text),
       el("p","",String(ref.meeting_no||"")+(ref.action_no?" · اقدام "+ref.action_no:"")),
       el("small","","شماره شناسه جلسه: "+String(ref.meeting_id||"")));
   add(sources,item);
  }
  if(!result.items?.length)add(sources,el("p","muted","منبعی مطابق پرسش در داده‌های مجاز ثبت نشده است."));
  add(target,sources);
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
