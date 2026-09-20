"use strict";
/* Connected, opt-in localhost LAB SPA. NEVER issue a token locally, trust a
   tenant from user input, store access tokens, or bypass /v1 API authorization.
   OAuth Authorization Code + PKCE S256; ephemeral verifier/state in sessionStorage
   only across the IdP redirect; access token stays in JS closure memory ONLY.
   External HTTPS IdP must explicitly allow CORS for its public-client token
   endpoint, register http://127.0.0.1:8088/portal/ as SPA redirect, and issue
   RS256 API ACCESS tokens with aud, iss, sub, iat, exp and trusted tenant_id.
*/
let accessToken=null, profile=null, modules=[], meetings=[], nextCursor=null;
let page="overview", selectedMeeting=null, config=null;
const $=id=>document.getElementById(id);
const titles={overview:"نمای کلی",meetings:"جلسات مجاز",assistant:"جست‌وجوی مستندات",
  secretary:"دبیر هوشمند",analytics:"تحلیل مدیریتی",monitoring:"پایش اقدامات",modules:"ماژول‌های سازمان"};
function e(tag,cls="",txt){const v=document.createElement(tag);if(cls)v.className=cls;if(txt!==undefined)v.textContent=String(txt);return v}
function append(parent,...items){items.flat().filter(Boolean).forEach(x=>parent.append(x));return parent}
function btn(label,cb,cls="button"){const b=e("button",cls,label);b.type="button";b.addEventListener("click",cb);return b}
function root(){const main=$("main");main.replaceChildren();return main}
function title(main,kicker,headline,summary){const h=e("div","page-heading"),body=e("div");
  append(body,e("span","eyebrow",kicker),e("h1","",headline),e("p","",summary));append(h,body);append(main,h)}
function box(name,note=""){const c=e("section","panel"),head=e("div","panel-header");
  append(head,e("h2","",name),e("small","",note));append(c,head);return c}
function notice(main,txt){append(main,e("div","status-banner",txt))}
function badge(text,kind=""){return e("span","badge "+kind,text)}
function fmtDate(s){if(!s)return "—";const d=new Date(s);return Number.isNaN(d.getTime())?
  String(s):new Intl.DateTimeFormat("fa-IR",{dateStyle:"medium",timeZone:"UTC"}).format(d)}
function num(x){return new Intl.NumberFormat("fa-IR").format(x)}
function tokenString(n=32){const bytes=new Uint8Array(n);crypto.getRandomValues(bytes);
  return Array.from(bytes,v=>String.fromCharCode(v)).join("")}
function base64url(s){return btoa(s).replace(/\+/g,"-").replace(/\//g,"_").replace(/=+$/,"")}
async function challenge(verifier){const hash=await crypto.subtle.digest("SHA-256",new TextEncoder().encode(verifier));
  return base64url(Array.from(new Uint8Array(hash),v=>String.fromCharCode(v)).join(""))}
function redirectUri(){return location.origin+"/portal/"}
function clearAttempt(){try{sessionStorage.removeItem("avan_pkce_attempt")}catch(_){}}
async function login(){
  if(!config){showMessage("پیکربندی سامانه هویت معتبر نیست.");return}
  if(!crypto?.subtle){showMessage("مرورگر برای ورود امن از Web Crypto پشتیبانی نمی‌کند.");return}
  const verifier=base64url(tokenString(48)),state=base64url(tokenString(24)),nonce=base64url(tokenString(24));
  try{sessionStorage.setItem("avan_pkce_attempt",JSON.stringify({
    verifier,state,nonce,created:Date.now(),redirect_uri:redirectUri()
  }))}catch(_){showMessage("حافظه موقت مرورگر برای هدایت امن ورود در دسترس نیست.");return}
  const url=new URL(config.authorization_url);
  url.searchParams.set("response_type","code");url.searchParams.set("client_id",config.client_id);
  url.searchParams.set("redirect_uri",redirectUri());url.searchParams.set("scope",config.scopes);
  url.searchParams.set("state",state);url.searchParams.set("nonce",nonce);
  url.searchParams.set("code_challenge_method","S256");
  url.searchParams.set("code_challenge",await challenge(verifier));
  if(config.auth_audience)url.searchParams.set("audience",config.auth_audience);
  location.assign(url.href);
}
async function completeCallback(code,returnedState){
  let attempt;try{attempt=JSON.parse(sessionStorage.getItem("avan_pkce_attempt")||"null")}catch(_){}
  clearAttempt();
  if(!attempt||!returnedState||returnedState!==attempt.state
     ||!attempt.verifier||attempt.redirect_uri!==redirectUri()
     ||Date.now()-attempt.created>5*60*1000||Date.now()<attempt.created){
    throw Error("وضعیت بازگشت از سامانه ورود معتبر نیست. ورود را از ابتدا شروع کنید.")
  }
  const body=new URLSearchParams({
    grant_type:"authorization_code",code,client_id:config.client_id,
    redirect_uri:redirectUri(),code_verifier:attempt.verifier
  });
  const result=await fetch(config.token_url,{
    method:"POST",body,headers:{"Content-Type":"application/x-www-form-urlencoded"},
    cache:"no-store",credentials:"omit",redirect:"error"
  });
  if(!result.ok)throw Error("تبادل کد ورود با سامانه هویت ناموفق بود؛ تنظیمات CORS و PKCE را بررسی کنید.");
  const data=await result.json();
  if(typeof data.access_token!=="string"||!data.access_token||
     String(data.token_type).toLowerCase()!=="bearer")
    throw Error("سامانه هویت توکن دسترسی Bearer معتبر برنگرداند.");
  accessToken=data.access_token; // MEMORY ONLY, never localStorage/cookie/log.
}
function logout(){
  accessToken=null;profile=null;modules=[];meetings=[];nextCursor=null;
  clearAttempt();$("logout").hidden=true;$("user-name").textContent="وارد نشده";
  $("user-role").textContent="نشست مرورگر پایان یافت";renderLogin();
}
async function api(path,options={}){
  if(!accessToken)throw Error("ورود معتبر وجود ندارد.");
  const response=await fetch(path,{
    ...options,cache:"no-store",credentials:"omit",redirect:"error",
    headers:{...(options.headers||{}),Authorization:"Bearer "+accessToken}
  });
  if(response.status===401){logout();throw Error("نشست ورود منقضی یا نامعتبر شد. دوباره وارد شوید.");}
  if(response.status===403)throw Error("مجوز مشاهده این بخش برای کاربر فعلی وجود ندارد.");
  if(response.status===503)throw Error("سرویس آزمایشی یا مجوز دسترسی در دسترس نیست.");
  if(!response.ok)throw Error("درخواست مجاز انجام نشد (HTTP "+response.status+").");
  return response.json();
}
async function refreshIdentity(){
  profile=await api("/v1/me");
  modules=(await api("/v1/modules")).modules;
  $("user-name").textContent=profile.subject;
  $("user-role").textContent=profile.role+" · "+profile.plan;
  $("logout").hidden=false;
}
function currentModule(code){return modules.find(x=>x.module_code===code)}
function moduleActive(code){const m=currentModule(code);return Boolean(m&&m.active)}
function showMessage(message){
  const main=root();const p=e("div","locked");
  append(p,e("span","locked-icon","◈"),e("h2","","امکان ادامه وجود ندارد"),
    e("p","",message));append(main,p);
}
function renderLogin(){
  const main=root();$("where").textContent="ورود کاربر";
  const panel=e("div","hero");
  append(panel,e("span","eyebrow","SECURE ORGANIZATION SIGN-IN"),
    e("h1","","ورود امن به آوان"),
    e("p","","برای مشاهده جلسات و ماژول‌های مجاز، ورود با سامانه هویت سازمانی الزامی است. حساب ساختگی یا توکن آزمایشی برای این پنل صادر نمی‌شود."));
  const b=btn("ورود با حساب سازمانی",login,"button");b.disabled=!config;
  append(panel,b);append(main,panel);
  notice(main,"این مسیر به سرویس هویت HTTPS واقعی و عضویت فعال در SQL آزمایشی نیاز دارد. تا زمان تکمیل تنظیمات، فقط پیش‌نمایش مستقل در پورت ۸۰۹۰ قابل بازبینی است.");
  const p=box("نکات دسترسی","محیط آزمایشی");
  append(p,e("p","content-text","توکن در مرورگر ذخیره پایدار نمی‌شود و برای هر درخواست API روی سرور اعتبارسنجی می‌شود. نقش‌ها، مجوز جلسه و مجوز ماژول از دیتابیس تعیین می‌شوند. این پنل درگاه پرداخت یا دسترسی مستقیم به ProcessMaker ندارد."));
  append(main,p);
}
function showLocked(main,code){
  const mod=currentModule(code);const wrap=e("div","locked");
  append(wrap,e("span","locked-icon","◈"),e("h2","",mod?.title||"ماژول اختیاری"),
    e("p","",!mod?.licensed?"برای این سازمان مجوز معتبر این ماژول ثبت نشده است.":
      "این ماژول در سازمان شما غیرفعال است. مدیر مجاز می‌تواند آن را روشن کند."),
    btn("مشاهده وضعیت ماژول‌ها",()=>changePage("modules")));
  append(main,wrap);
}
async function changePage(target){
  if(!Object.hasOwn(titles,target)||!profile)return;
  page=target;$("where").textContent=titles[target];
  document.querySelectorAll(".nav-item").forEach(x=>x.classList.toggle("active",x.dataset.page===target));
  document.querySelector(".sidebar").classList.remove("open");
  const main=root();append(main,e("div","loading","در حال دریافت اطلاعات مجاز..."));
  try{
    switch(target){
      case "meetings": await showMeetings();break;
      case "assistant": showAssistant();break;
      case "secretary": await showSecretary();break;
      case "analytics": await showAnalytics();break;
      case "monitoring": await showMonitoring();break;
      case "modules": await showModules();break;
      default: await showOverview();
    }
  }catch(err){showMessage(err.message||"خطا در بارگذاری اطلاعات مجاز.")}
}
function meetingRow(c){
  const row=e("div","list-row"),left=e("div");
  append(left,e("strong","",c.title),e("small","",c.meeting_no+" · "+c.status));
  append(row,left,btn("پیش‌نویس دبیر",()=>{
    selectedMeeting=c.meeting_id;changePage("secretary")},"button secondary"));
  return row;
}
async function showOverview(){
  const main=root();title(main,"WORKSPACE / AUTHENTICATED","فضای کاری شما",
    "تمام داده‌ها از API آزمایشی و براساس هویت و مجوزهای کاربر دریافت می‌شوند.");
  notice(main,"محیط آزمایشی مستقل؛ هیچ داده عملیاتی ProcessMaker در این نما استفاده نمی‌شود.");
  const grid=e("div","stats");
  const active=modules.filter(m=>m.active).length;
  const p1=e("div","stat"),p2=e("div","stat"),p3=e("div","stat"),p4=e("div","stat");
  [[p1,"سازمان",profile.tenant_id],[p2,"نقش",profile.role],[p3,"ماژول فعال",num(active)],
   [p4,"اشتراک",profile.plan]].forEach(([el,k,v])=>{
    append(el,e("div","stat-label",k),e("strong","",String(v)));
  });
  append(grid,p1,p2,p3,p4);append(main,grid);
  const data=await api("/v1/meetings/page?limit=5");
  const panel=box("جلسات مجاز اخیر","فقط پنج جلسه آخر مجاز شما");
  data.meetings.forEach(m=>append(panel,meetingRow(m)));
  if(!data.meetings.length)append(panel,e("p","empty","جلسه مجازی برای این کاربر ثبت نشده است."));
  append(main,panel);
}
async function showMeetings(){
  const main=root();title(main,"WORKSPACE / MEETINGS","جلسات مجاز من",
    "صفحه‌بندی فهرست جلسات با فیلتر SQL بر اساس عضویت و مجوز هر کاربر.");
  const panel=box("فهرست جلسات","حداکثر ۲۰ ردیف در هر صفحه");
  meetings=[];nextCursor=null;
  const list=e("div");const more=btn("بارگذاری جلسات بعدی",loadPage,"button secondary");
  async function loadPage(){
    more.disabled=true;
    const params=new URLSearchParams({limit:"20"});
    if(nextCursor!==null)params.set("cursor",String(nextCursor));
    try{
      const result=await api("/v1/meetings/page?"+params.toString());
      meetings.push(...result.meetings);nextCursor=result.next_cursor;
      result.meetings.forEach(m=>append(list,meetingRow(m)));
      more.hidden=!result.has_more;
      if(!meetings.length)append(list,e("p","empty","جلسه‌ای با مجوز دسترسی شما ثبت نشده است."));
    }catch(err){append(panel,e("p","note",err.message))}
    finally{more.disabled=false}
  }
  append(panel,list,more);append(main,panel);await loadPage();
}
function showAssistant(){
  const main=root();title(main,"MODULE 01 / EVIDENCE","جست‌وجوی مستندات و صورت‌جلسات",
    "نسخه خواندنی: نمایش شواهد مجاز بدون فراخوانی OpenAI.");
  notice(main,"این صفحه فقط خروجی /v1/chat/preview را نمایش می‌دهد. پاسخ تولیدشده توسط مدل زبانی غیرفعال است.");
  const panel=box("پرسش فارسی","جست‌وجو با مجوز کاربر");
  const input=e("textarea","textarea");input.placeholder="مثلاً: موضوع گمرک و ترخیص جلسه چیست؟";
  input.maxLength=350;const result=e("div");
  append(panel,input,btn("جست‌وجوی شواهد",async()=>{
    result.replaceChildren();
    if(input.value.trim().length<3){append(result,e("p","note","حداقل سه کاراکتر وارد کنید."));return;}
    try{
      const data=await api("/v1/chat/preview",{
        method:"POST",headers:{"Content-Type":"application/json"},
        body:JSON.stringify({question:input.value.trim()})
      });
      const p=box("شواهد مجاز",num(data.evidence_count)+" منبع");data.evidence.forEach(v=>{
        const row=e("div","detail-group");
        append(row,e("strong","",v.title||v.source),
          e("p","content-text",v.excerpt||v.status||"جزئیات بیشتر در پرونده جلسه."),
          badge(v.source,"good"));append(p,row);
      });
      if(!data.evidence.length)append(p,e("p","empty","منبع مرتبط و مجازی یافت نشد."));
      append(result,p);
    }catch(err){append(result,e("p","note",err.message))}
  },"button teal"),result);append(main,panel);
}
async function showSecretary(){
  const main=root();title(main,"MODULE 02 / SECRETARY","دبیر هوشمند",
    "پیش‌نویس قابل بررسی براساس جلسه‌ای که کاربر مجوز مشاهده آن را دارد.");
  if(!moduleActive(2))return showLocked(main,2);
  const id=selectedMeeting;
  if(!id){append(main,e("p","empty","ابتدا از فهرست جلسات یک پرونده را انتخاب کنید."),
    btn("رفتن به جلسات",()=>changePage("meetings")));return;}
  const data=await api("/v1/secretary/preparation/"+encodeURIComponent(id));
  const panel=box("پیش‌نویس دستور جلسه",data.meeting?.meeting_no||"");
  data.draft_agenda.forEach((x,i)=>append(panel,e("p","content-text",num(i+1)+". "+x)));
  append(panel,e("p","note","برای ثبت یا تغییر در ProcessMaker، تأیید و اتصال کنترل‌شده جداگانه لازم است."));
  append(main,panel);const actions=box("اقدامات","محدود به جلسه مجاز");
  data.actions.forEach(a=>append(actions,e("div","list-row",
    a.action_no+" · "+a.title+" · "+num(a.progress_percent)+"٪")));
  append(main,actions);
}
async function showAnalytics(){
  const main=root();title(main,"MODULE 03 / ANALYTICS","تحلیل و گزارش",
    "شمارش جلسات و اقدامات مجاز شما، نه اطلاعات همه کاربران سازمان.");
  if(!moduleActive(3))return showLocked(main,3);
  const data=await api("/v1/analytics/status-overview");
  const grid=e("div","stats");
  [["جلسات مجاز",data.total_visible_meetings],["کل اقدامات مجاز",data.actions.total],
   ["اقدامات باز",data.actions.open],["اقدامات تأخیردار",data.actions.overdue]]
    .forEach(([k,v])=>{const el=e("div","stat");
      append(el,e("span","stat-label",k),e("strong","",num(v)));append(grid,el)});
  append(main,grid);
  const panel=box("وضعیت جلسات مجاز","آمار واقعی از نمایه SQL آزمایشی");
  data.status_breakdown.forEach(x=>append(panel,e("div","list-row",
    x.status+" : "+num(x.count))));append(main,panel);
}
async function showMonitoring(){
  const main=root();title(main,"MODULE 04 / MONITORING","هشدار و پیگیری اقدامات",
    "نمای درخواستی حداکثر ۵۰ اقدام تأخیردار در جلسات مجاز شما.");
  if(!moduleActive(4))return showLocked(main,4);
  const data=await api("/v1/monitoring/overdue");
  const panel=box("اقدامات دارای تأخیر",num(data.returned)+" مورد");
  data.alerts.forEach(a=>{
    const row=e("div","list-row"),left=e("div");
    append(left,e("strong","",a.action_no+" · "+a.title),
      e("small","",a.owner_unit+" · جلسه "+a.meeting_id+" · موعد "+fmtDate(a.due_at_utc)));
    append(row,left,badge(num(a.progress_percent)+"٪","bad"));append(panel,row);
  });
  if(!data.alerts.length)append(panel,e("p","empty","اقدام تأخیردار مجازی یافت نشد."));
  append(panel,e("p","note","این سرویس صرفاً هنگام درخواست کاربر گزارش می‌دهد؛ اعلان خودکار ارسال نمی‌شود."));
  append(main,panel);
}
async function showModules(){
  modules=(await api("/v1/modules")).modules;
  const main=root();title(main,"PRODUCT / LICENSES","ماژول‌های سازمان",
    "وضعیت معتبر هر ماژول از API و SQL دریافت شده است. فقط مدیر مجاز می‌تواند ماژول خریداری‌شده را تغییر دهد.");
  const grid=e("div","module-grid"),admin=["Admin","Owner"].includes(profile.role);
  for(const m of modules){
    const card=e("section","module-card"),foot=e("div","mod-foot");
    append(card,e("div","num",num(m.module_code)),e("h2","",m.title),
      e("p","",m.module_code===1?"دستیار پایه با دسترسی کنترل‌شده.":
        !m.licensed?"فاقد مجوز خرید معتبر":m.active?"ماژول روشن است.":"مجوز موجود است ولی ماژول خاموش است."));
    append(foot,badge(m.active?"فعال":m.licensed?"خاموش":"فاقد مجوز",m.active?"good":"warn"));
    if(m.module_code!==1){
      const toggle=btn(m.enabled?"خاموش‌کردن":"روشن‌کردن",async()=>{
        toggle.disabled=true;
        try{
          await api("/v1/admin/modules/"+m.module_code,{
            method:"PUT",headers:{"Content-Type":"application/json"},
            body:JSON.stringify({enabled:!m.enabled})
          });
          modules=(await api("/v1/modules")).modules;
          await showModules();
        }catch(err){append(card,e("p","note",err.message));toggle.disabled=false}
      },"button secondary");
      toggle.disabled=!admin||!m.licensed;append(foot,toggle);
    }
    append(card,foot);append(grid,card);
  }
  append(main,grid);
}
async function init(){
  document.querySelectorAll("[data-page]").forEach(b=>b.addEventListener("click",()=>changePage(b.dataset.page)));
  $("logout").addEventListener("click",logout);
  $("mobile-nav").addEventListener("click",()=>document.querySelector(".sidebar").classList.toggle("open"));
  const url=new URL(location.href),code=url.searchParams.get("code"),
    returnedState=url.searchParams.get("state"),failure=url.searchParams.get("error");
  if(code||failure||returnedState){history.replaceState(null,"",redirectUri());}
  try{
    const result=await fetch("/portal/config",{cache:"no-store",credentials:"omit"});
    if(!result.ok)throw Error("ارائه‌دهنده هویت HTTPS واقعی برای پنل متصل تنظیم نشده است.");
    config=await result.json();
    if(!config.ready)throw Error("ورود سازمانی آماده نیست.");
    if(failure)throw Error("ورود از سمت سامانه هویت تکمیل نشد.");
    if(code||returnedState){
      if(!code||!returnedState)throw Error("بازگشت ورود ناقص است.");
      await completeCallback(code,returnedState);
      await refreshIdentity();await changePage("overview");return;
    }
    renderLogin();
  }catch(err){
    clearAttempt();accessToken=null;
    showMessage(err.message||"پنل متصل هنوز پیکربندی نشده است.");
  }
}
document.addEventListener("DOMContentLoaded",init);
