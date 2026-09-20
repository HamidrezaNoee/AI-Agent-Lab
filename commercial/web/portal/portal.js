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
let directoryProfile=null, platformAdmin=false, tenantAdmin=false;
let page="overview", selectedMeeting=null, config=null;
const $=id=>document.getElementById(id);
const titles={overview:"نمای کلی",meetings:"جلسات مجاز",assistant:"جست‌وجوی مستندات",
  secretary:"دبیر هوشمند",analytics:"تحلیل مدیریتی",monitoring:"پایش اقدامات",modules:"ماژول‌های سازمان",
  directory:"کاربران و چارت سازمانی",settings:"تنظیمات سازمان",godadmin:"GodAdmin و لایسنس‌ها"};
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
  directoryProfile=null;platformAdmin=false;tenantAdmin=false;
  $("tenant-admin-nav").hidden=true;$("admin-heading").hidden=true;
  $("platform-admin-nav").hidden=true;$("godadmin-heading").hidden=true;
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
  // A verified GodAdmin may administer platform metadata without belonging
  // to any customer tenant. Never grant meeting access from that global role.
  try{
    await api("/v2/godadmin/status");
    platformAdmin=true;
  }catch(err){
    platformAdmin=false;
  }
  try{
    profile=await api("/v1/me");
    modules=(await api("/v1/modules")).modules;
    try{
      directoryProfile=await api("/v2/me/directory");
      if(directoryProfile.org_role==="SysAdmin"){
        await api("/v2/admin/system/connections");
        tenantAdmin=true;
      }
    }catch(_){directoryProfile=null;tenantAdmin=false;}
  }catch(err){
    if(!platformAdmin)throw err;
    // Platform-only session: show GodAdmin metadata, not tenant content.
    profile={subject:"GodAdmin",role:"GodAdmin",plan:"Platform",tenant_id:"—"};
    modules=[];directoryProfile=null;tenantAdmin=false;
    document.querySelectorAll("#nav [data-page]").forEach(item=>item.hidden=true);
  }
  if(config?.hierarchy_only && !directoryProfile && !platformAdmin){
    profile=null;modules=[];
    throw Error("حساب شما هنوز به دایرکتوری فعال ProcessMaker و چارت سازمانی متصل نشده است.");
  }
  $("tenant-admin-nav").hidden=!tenantAdmin;$("admin-heading").hidden=!tenantAdmin;
  $("platform-admin-nav").hidden=!platformAdmin;$("godadmin-heading").hidden=!platformAdmin;
  $("user-name").textContent=profile.subject;
  $("user-role").textContent=profile.role+" · "+profile.plan;
  if(directoryProfile){
    try{
      const brand=await api("/v2/branding");
      const workspace=document.querySelector(".workspace strong");
      if(workspace)workspace.textContent=brand.company_name;
      if(/^#[0-9A-Fa-f]{6}$/.test(brand.primary_color)){
        document.documentElement.style.setProperty("--teal",brand.primary_color);
      }
    }catch(_){/* Never block login because optional branding is missing. */}
  }
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
  if(target==="godadmin"&&!platformAdmin)return;
  if(["directory","settings"].includes(target)&&!tenantAdmin)return;
  if(profile.role==="GodAdmin"&&!directoryProfile&&target!=="godadmin")return;
  page=target;$("where").textContent=titles[target];
  document.querySelectorAll(".nav-item").forEach(x=>x.classList.toggle("active",x.dataset.page===target));
  document.querySelector(".sidebar").classList.remove("open");
  const main=root();append(main,e("div","loading","در حال دریافت اطلاعات مجاز..."));
  try{
    switch(target){
      case "meetings": await showMeetings();break;
      case "assistant": await showAssistant();break;
      case "secretary": await showSecretary();break;
      case "analytics": await showAnalytics();break;
      case "monitoring": await showMonitoring();break;
      case "modules": await showModules();break;
      case "directory": await showDirectory();break;
      case "settings": await showSystemSettings();break;
      case "godadmin": await showGodAdmin();break;
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
  const data=await api((directoryProfile?"/v2":"/v1")+"/meetings/page?limit=5");
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
      const result=await api((directoryProfile?"/v2":"/v1")+"/meetings/page?"+params.toString());
      meetings.push(...result.meetings);nextCursor=result.next_cursor;
      result.meetings.forEach(m=>append(list,meetingRow(m)));
      more.hidden=!result.has_more;
      if(!meetings.length)append(list,e("p","empty","جلسه‌ای با مجوز دسترسی شما ثبت نشده است."));
    }catch(err){append(panel,e("p","note",err.message))}
    finally{more.disabled=false}
  }
  append(panel,list,more);append(main,panel);await loadPage();
}
async function showAssistant(){
  const main=root();
  title(main,"MODULE 01 / MANAGEMENT INTELLIGENCE","پرسش‌های تخصصی جلسات",
    "هشت گزارش مستند درباره مصوبات و عملکرد؛ نتایج فقط از جلسات مجاز حساب فعلی دریافت می‌شوند.");
  notice(main,"این بخش فعلاً گزارش‌گیری محاسباتیِ فقط‌خواندنی است، نه گفت‌وگوی آزاد با OpenAI. برای گزارش‌های تجمیعی، دبیر و پایش، مجوز ماژول مربوط باید فعال باشد. تاریخ جلسه و متن ریسک در نمایه SQL فعلی هنوز وجود ندارند.");
  if(!directoryProfile){
    append(main,e("p","empty",
      "ابتدا ورود واقعی و اتصال هویت شما به کاربر فعال ProcessMaker لازم است. تا آن زمان فقط پیش‌نمایش ۸۰۹۰ قابل بررسی است."));
    return;
  }
  const catalog=await api("/v2/assistant/questions");
  const section=box("سؤال خود را بپرسید","منابع و حدود پوشش هر جواب در پاسخ نمایش داده می‌شود");
  const input=e("textarea","textarea");
  input.placeholder="مثلاً: کدام اقدامات مصوب جلسات عقب‌افتاده‌اند؟";
  input.setAttribute("aria-label","پرسش تخصصی جلسات");input.maxLength=350;
  const result=e("div");
  let requestSequence=0;
  async function runQuestion(text){
    const sequence=++requestSequence;
    result.replaceChildren();
    if(text.trim().length<3){
      append(result,e("p","note","پرسش باید حداقل سه کاراکتر داشته باشد."));return;
    }
    append(result,e("p","note","در حال محاسبه گزارش از جلسات مجاز..."));
    try{
      const answer=await api("/v2/assistant/ask",{
        method:"POST",headers:{"Content-Type":"application/json"},
        body:JSON.stringify({question:text.trim()})
      });
      if(sequence!==requestSequence||!result.isConnected)return;
      result.replaceChildren();
      const panel=box("نتیجه مستند",num(answer.meetings_considered)+" جلسه بررسی شده");
      append(panel,e("p","content-text",answer.answer),
        e("p","note","دامنه: فقط جلسات مجاز همین کاربر · اقدامات بررسی‌شده: "+
           num(answer.actions_considered)+" · زمان بررسی (UTC): "+answer.as_of_utc));
      for(const item of answer.items||[]){
        const row=e("div","detail-group");
        const source=item.source||{};
        append(row,e("strong","content-title",item.text),
          e("p","note",String(source.meeting_no||"")+
            (source.action_no?" · "+source.action_no:"")+
            (item.owner_unit?" · "+item.owner_unit:"")));
        if(source.meeting_no){
          append(row,btn("پرسش درباره اقدامات این جلسه",()=>{
            const q="اقدامات جلسه شماره "+source.meeting_no+" در چه وضعیتی هستند؟";
            input.value=q;runQuestion(q);
          },"button secondary"));
        }
        append(panel,row);
      }
      if(!answer.items?.length)append(panel,e("p","note",
        "منبعی مطابق معیار پرسش در داده‌های مجاز یافت نشد یا نمایه دارای داده کافی نیست."));
      for(const note of answer.notes||[]){
        append(panel,e("p","note","• "+note));
      }
      if(answer.coverage_complete===false)append(panel,e("p","note",
        "پوشش اطلاعات کامل نیست؛ نتیجه را گزارش تمام جلسات تلقی نکنید."));
      append(result,panel);
    }catch(err){
      if(sequence!==requestSequence||!result.isConnected)return;
      result.replaceChildren();
      append(result,e("p","note",err.message),
        e("p","note",
          "اگر ماژول خریداری نشده، منقضی یا خاموش است، مدیر سازمان باید مجوز آن را بررسی کند. دسترسی با دورزدن مجوز فعال نمی‌شود."));
    }
  }
  append(section,input,btn("دریافت پاسخ مستند",()=>runQuestion(input.value),"button teal"),result);
  append(main,section);
  const suggestions=box("پرسش‌های مدیریتی آماده","انتخاب هر پرسش آن را روی دامنه جلسات مجاز اجرا می‌کند");
  const buttons=e("div","bars");
  (catalog.questions||[]).forEach((question,index)=>{
    const button=btn(num(index+1)+". "+question,()=>{
      input.value=question;runQuestion(question);
    },"button secondary");
    button.style.textAlign="right";button.style.width="100%";
    append(buttons,button);
  });
  append(suggestions,buttons);append(main,suggestions);
}
async function showSecretary(){
  const main=root();title(main,"MODULE 02 / SECRETARY","دبیر هوشمند",
    "پیش‌نویس قابل بررسی براساس جلسه‌ای که کاربر مجوز مشاهده آن را دارد.");
  if(!moduleActive(2))return showLocked(main,2);
  const id=selectedMeeting;
  if(!id){append(main,e("p","empty","ابتدا از فهرست جلسات یک پرونده را انتخاب کنید."),
    btn("رفتن به جلسات",()=>changePage("meetings")));return;}
  const data=await api((directoryProfile?"/v2":"/v1")+"/secretary/preparation/"+encodeURIComponent(id));
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
  const data=await api(directoryProfile?"/v2/analytics/action-overview":"/v1/analytics/status-overview");
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
  const data=await api(directoryProfile?"/v2/monitoring/overdue":"/v1/monitoring/overdue");
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

async function showDirectory(){
  const main=root();title(main,"TENANT SYSADMIN / PROCESSMAKER","مدیریت کاربران و چارت سازمانی",
    "نمایه کاربران ProcessMaker، نقش‌های سازمانی و مدیر مستقیم؛ بدون کپی رمز عبور.");
  notice(main,"این صفحه فقط برای SysAdmin دارای نقش امضاشده در Keycloak و عضویت مدیریتی معتبر SQL فعال است. کاربران تازه Syncشده غیرفعال و بدون اتصال خودکار به هویت باقی می‌مانند.");
  const status=await api("/v2/admin/system/connections");
  const p=box("وضعیت اتصال‌ها","هیچ رمز یا توکنی به مرورگر ارسال نمی‌شود");
  append(p,e("p","content-text","ProcessMaker: "+(status.processmaker.configured?"تنظیم شده":"تنظیم نشده")+
      " · فضای کاری: "+(status.processmaker.workspace||"—")),
    e("p","content-text","SQL Server آزمایشی: "+(status.commercial_sql.configured?"تنظیم شده":"تنظیم نشده")));
  const buttons=e("div","flex");
  append(buttons,btn("پیش‌نمایش کاربران ProcessMaker",async()=>{
    const output=e("div","result");append(p,output);
    try{const data=await api("/v2/admin/processmaker/users/preview");
      append(output,e("p","content-text","کاربران دیده‌شده: "+num(data.count)+" · فعال: "+num(data.active)),
        e("p","note","این مرحله فقط خواندن API است؛ هیچ داده‌ای ذخیره نشده است."));
    }catch(err){append(output,e("p","note",err.message))}
  },"button secondary"));
  append(buttons,btn("همگام‌سازی کنترل‌شده",async()=>{
    if(!confirm("پس از دریافت فهرست کامل کاربران ProcessMaker، فقط اطلاعات پروفایل مجاز Sync شود؟ هیچ رمز و هیچ نقش مدیریتی خودکار انتقال نمی‌یابد."))return;
    const output=e("div","result");append(p,output);
    try{const d=await api("/v2/admin/processmaker/users/sync",
      {method:"POST",headers:{"Content-Type":"application/json"},
       body:JSON.stringify({deactivate_missing:false})});
      append(output,e("p","content-text","بررسی شد: "+num(d.seen)+
        " · حساب جدید غیرفعال: "+num(d.new_disabled_unbound)+
        " · پروفایل به‌روزرسانی‌شده: "+num(d.existing_profiles)));
    }catch(err){append(output,e("p","note",err.message))}
  },"button teal"));append(p,buttons);append(main,p);
  const data=await api("/v2/admin/directory/users");
  const roster=box("کاربران ثبت‌شده در دایرکتوری",num(data.returned)+" نفر · حداکثر ۵۰۰ رکورد");
  for(const user of data.users){
    const row=e("div","detail-group"),name=e("strong","content-title",user.display_name);
    append(row,name,e("p","note",user.username+" · "+user.pm_status+
      " · "+user.org_role+" · "+(user.linked_subject?"دارای هویت":"در انتظار اتصال هویت")));
    const actions=e("div","flex");
    if(user.org_role!=="SysAdmin"){
      const roles=e("select","select");
      [["Expert","کارشناس"],["Manager","مدیر (همه جلسات سازمان)"]].forEach(([value,label])=>{
        const opt=e("option","",label);opt.value=value;opt.selected=user.org_role===value;append(roles,opt);
      });
      const saveRole=btn("ثبت نقش",async()=>{
        try{await api("/v2/admin/directory/"+encodeURIComponent(user.pm_uid)+"/role",
          {method:"PUT",headers:{"Content-Type":"application/json"},
           body:JSON.stringify({role:roles.value})});await showDirectory();
        }catch(err){append(row,e("p","note",err.message))}
      },"button secondary");append(actions,roles,saveRole);
    }
    const managers=e("select","select");
    const unlinked=e("option","","بدون مدیر مستقیم");unlinked.value="";append(managers,unlinked);
    data.users.filter(other=>other.pm_uid!==user.pm_uid).forEach(other=>{
      const opt=e("option","",other.display_name);opt.value=other.pm_uid;
      opt.selected=user.manager_pm_uid===other.pm_uid;append(managers,opt);
    });
    append(actions,managers,btn("ثبت مدیر مستقیم",async()=>{
      try{await api("/v2/admin/directory/"+encodeURIComponent(user.pm_uid)+"/manager",
        {method:"PUT",headers:{"Content-Type":"application/json"},
         body:JSON.stringify({manager_pm_uid:managers.value||null})});await showDirectory();
      }catch(err){append(row,e("p","note",err.message))}
    },"button secondary"));
    if(user.linked_subject && user.enabled && user.pm_status==="ACTIVE" &&
       ["Expert","Manager"].includes(user.org_role)){
      append(actions,btn("ارسال لینک تغییر رمز",async()=>{
        if(!confirm("درخواست ارسال ایمیل تغییر رمز توسط Keycloak برای این کاربر ثبت شود؟ هیچ رمزی نمایش داده نمی‌شود."))return;
        try{
          const receipt=await api("/v2/admin/directory/"+encodeURIComponent(user.pm_uid)+
            "/send-password-update",{method:"POST"});
          append(row,e("p","content-text",
            receipt.status==="sent_to_identity_provider"?
            "درخواست ایمیل تغییر رمز به سامانه هویت ارسال شد.":"نتیجه درخواست نامشخص است."));
        }catch(err){append(row,e("p","note",err.message))}
      },"button secondary"));
    }
    append(row,actions);append(roster,row);
  }
  append(main,roster);
  const future=box("ایجاد حساب و تغییر رمز","نیازمند سرویس هویت سازمانی");
  append(future,e("p","content-text",
    "برای کاربر فعال و لینک‌شده، مدیر سیستم می‌تواند درخواست ارسال ایمیل تغییر رمز را به Keycloak بفرستد؛ این قابلیت فقط پس از تنظیم امن سرویس مدیریتی توسط IT فعال می‌شود. هیچ رمز یا توکن بازیابی در این پنل تولید یا نمایش داده نمی‌شود. ایجاد حساب تازه و اتصال UID پروسس‌میکر به هویت تأییدشده همچنان نیازمند فرایند رسمی مدیریت هویت است."));
  append(main,future);
}
async function showSystemSettings(){
  const main=root();title(main,"TENANT SYSADMIN / SETTINGS","تنظیمات سازمان",
    "نام، رنگ سازمان و وضعیت تنظیمات امن اتصال‌ها.");
  const [brand,status]=await Promise.all([
    api("/v2/branding"),api("/v2/admin/system/connections")
  ]);
  const form=box("هویت بصری سازمان","ذخیره در SQL با رویداد ممیزی");
  const name=e("input","search");name.value=brand.company_name;name.maxLength=200;
  name.setAttribute("aria-label","نام سازمان");
  const color=e("input","search");color.type="color";color.value=brand.primary_color;
  color.setAttribute("aria-label","رنگ اصلی سازمان");
  append(form,e("p","note","نام شرکت"),name,e("p","note","رنگ اصلی"),color,
    btn("ذخیره نام و رنگ",async()=>{
      try{const saved=await api("/v2/admin/branding",
          {method:"PUT",headers:{"Content-Type":"application/json"},
           body:JSON.stringify({company_name:name.value.trim(),primary_color:color.value})});
        append(form,e("p","content-text","تنظیمات «"+saved.company_name+"» ذخیره شد."));
      }catch(err){append(form,e("p","note",err.message))}
    },"button teal"));
  const logoPanel=box("لوگوی سازمان","PNG با حداکثر حجم ۲۵۶ کیلوبایت");
  const picker=e("input","search");picker.type="file";picker.accept="image/png";
  picker.setAttribute("aria-label","انتخاب تصویر لوگوی PNG");
  const logoResult=e("div");append(logoPanel,
    e("p","note",brand.logo_available?"لوگو قبلاً ثبت شده است.":"لوگویی ثبت نشده است."),
    picker,btn("بارگذاری لوگوی سازمان",async()=>{
      logoResult.replaceChildren();
      const file=picker.files?.[0];
      if(!file||file.type!=="image/png"||file.size>256*1024||file.size<33){
        append(logoResult,e("p","note","فایل PNG معتبر و کوچک‌تر از ۲۵۶ کیلوبایت انتخاب کنید."));return;
      }
      try{
        await api("/v2/admin/branding/logo",{
          method:"PUT",headers:{"Content-Type":"image/png"},body:file,
        });
        append(logoResult,e("p","content-text","لوگوی سازمان ذخیره و ثبت ممیزی شد."));
      }catch(err){append(logoResult,e("p","note",err.message))}
    },"button secondary"),logoResult);
  append(main,form,logoPanel);
  const con=box("تنظیمات اتصال","رمزها نمایش یا از مرورگر دریافت نمی‌شوند");
  append(con,e("p","content-text","SQL Server: "+status.commercial_sql.database+
    " · کاربر محدود: "+(status.commercial_sql.login_name||"تعریف نشده")),
    e("p","content-text","ProcessMaker: "+(status.processmaker.workspace||"تعریف نشده")+
    " · Sync "+(status.processmaker.sync_enabled?"فعال":"خاموش")),
    e("p","note","تغییر رمز و میزبان SQL و تنظیم OAuth ProcessMaker نیازمند سرویس مستقل مدیریت اسرار هستند؛ ویرایش مستقیم این اطلاعات از مرورگر عمداً غیرفعال است."));
  append(main,con);
}
async function showGodAdmin(){
  const main=root();title(main,"PLATFORM / GODADMIN","مدیریت کل آوان",
    "مدیریت فراداده سازمان‌ها، ایجاد سازمان و فعال‌سازی لایسنس دارای امضای لیماک.");
  notice(main,"نقش GodAdmin به‌تنهایی مجوز خواندن صورت‌جلسات و نامه‌های مشتریان نیست. حساب باید در Keycloak و فهرست اپراتورهای پلتفرم هم تأیید شده باشد.");
  const status=await api("/v2/godadmin/status");
  const meta=box("مرز دسترسی پلتفرم",status.scope);
  append(meta,e("p","content-text","دسترسی مستقیم به محتوای جلسات مشتریان: "+(status.customer_meetings_access?"دارد":"ندارد")),
    e("p","note","مدیریت لایسنس امضاشده با کلید عمومی انجام می‌شود؛ کلید خصوصی فقط روی سیستم صادرکننده لیماک باقی می‌ماند."));
  append(main,meta);
  const tenants=(await api("/v2/godadmin/tenants")).tenants;
  const p=box("سازمان‌های ثبت‌شده",num(tenants.length)+" سازمان");
  for(const t of tenants){
    const row=e("div","detail-group");
    append(row,e("strong","content-title",t.company_name),
      e("p","note","Tenant ID: "+t.tenant_id+" · "+(t.enabled?"فعال":"غیرفعال")+
        " · مجوز: "+(t.license_id||"صادر نشده")));
    const input=e("textarea","textarea");
    input.placeholder="توکن لایسنس امضاشده از LIMAK License Studio برای همین سازمان...";
    input.maxLength=16000;input.setAttribute("aria-label","کد لایسنس سازمان "+t.company_name);
    append(row,input,btn("اعتبارسنجی و فعال‌سازی لایسنس",async()=>{
      if(!confirm("لایسنس امضاشده برای این سازمان بررسی و فعال شود؟"))return;
      try{const result=await api("/v2/godadmin/tenants/"+encodeURIComponent(t.tenant_id)+"/license",
         {method:"POST",headers:{"Content-Type":"application/json"},
          body:JSON.stringify({token:input.value.trim()})});
        input.value="";append(row,e("p","content-text","مجوز "+result.license_id+" فعال شد."));
      }catch(err){append(row,e("p","note",err.message))}
    },"button teal"));append(p,row);
  }
  append(main,p);
  const create=box("ایجاد سازمان جدید","در ابتدا غیرفعال و فاقد لایسنس خواهد بود");
  const name=e("input","search");name.placeholder="نام سازمان";name.maxLength=200;
  append(create,name,btn("ایجاد سازمان غیرفعال",async()=>{
    if(!confirm("سازمان جدید بدون عضویت و لایسنس ساخته شود؟"))return;
    try{await api("/v2/godadmin/tenants",
      {method:"POST",headers:{"Content-Type":"application/json"},
       body:JSON.stringify({company_name:name.value.trim()})});await showGodAdmin();
    }catch(err){append(create,e("p","note",err.message))}
  }));append(main,create);
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
      await refreshIdentity();await changePage(profile.role==="GodAdmin"&&!directoryProfile?"godadmin":"overview");return;
    }
    renderLogin();
  }catch(err){
    clearAttempt();accessToken=null;
    showMessage(err.message||"پنل متصل هنوز پیکربندی نشده است.");
  }
}
document.addEventListener("DOMContentLoaded",init);
