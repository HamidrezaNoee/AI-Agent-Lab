"use strict";
const state={csrf:null,user:null,settings:null,stage:"login",page:"agentdb"};
const $=id=>document.getElementById(id);
function node(tag,cls,text){const n=document.createElement(tag);if(cls)n.className=cls;if(text!==undefined)n.textContent=String(text);return n}
function append(parent,...items){for(const item of items.flat())if(item!==null&&item!==undefined)parent.append(item);return parent}
function field(title,name,value="",options={}){
 const label=node("label","",title),input=node(options.multiline?"textarea":"input");
 input.name=name;if(!options.multiline)input.type=options.secret?"password":options.type||"text";
 if(options.multiline)input.value=value||"";else input.value=value||"";
 input.required=options.required!==false;input.autocomplete="off";
 if(options.placeholder)input.placeholder=options.placeholder;
 append(label,input);
 return label;
}
function formValue(form,name){return form.elements.namedItem(name)?.value.trim()||""}
function btn(label,callback,cls=""){const b=node("button",cls,label);b.type="button";b.addEventListener("click",callback);return b}
function panel(title,description){return append(node("section","panel"),node("h2","",title),node("p","intro",description))}
function info(text,bad=false){return node("div","notice"+(bad?" error":""),text)}
function main(){const m=$("main");m.replaceChildren();return m}
function busy(form,b){for(const c of form.querySelectorAll("button"))c.disabled=b}
async function api(path,body){
 const headers={"Accept":"application/json"};
 const opts={credentials:"same-origin",cache:"no-store",headers};
 if(body!==undefined){headers["Content-Type"]="application/json";opts.method="POST";opts.body=JSON.stringify(body)}
 if(state.csrf)headers["X-AVAN-ADMIN-CSRF"]=state.csrf;
 const response=await fetch("/admin/api/"+path,opts);
 let result={};try{result=await response.json()}catch{}
 if(!response.ok)throw Error(typeof result.detail==="string"?result.detail:"دسترسی یا تنظیمات معتبر نیست.");
 return result;
}
function showError(out,err){out.replaceChildren(info(err.message||String(err),true))}
async function start(){
 try{
  const s=await api("state");
  state.csrf=s.csrf;
  if(!s.authenticated)showLogin(s.mfa_enrolled);
  else if(!s.password_changed)showChangePassword();
  else if(!s.mfa_enrolled)showTotpEnroll();
  else if(!s.mfa_authenticated)showLogin(true);
  else await showSettings();
 }catch(err){main().append(info(err.message||String(err),true))}
}
function showLogin(withMfa){
 const m=main(),p=panel("ورود مدیر کل سامانه","برای راه‌اندازی و مدیریت تنظیمات آوان، با حساب GodAdmin وارد شوید.");
 p.classList.add("login");const f=node("form");
 append(f,field("نام کاربری","username","godadmin"),
   field("رمز عبور","password","",{secret:true}));
 if(withMfa)append(f,field("کد شش‌رقمی برنامه Authenticator","otp","",{required:true}));
 const out=node("div");
 const loginBtn=node("button","","ورود به تنظیمات");loginBtn.type="submit";
 append(f,loginBtn,out);append(p,f);append(m,p);
 f.addEventListener("submit",async e=>{
  e.preventDefault();busy(f,true);out.replaceChildren();
  try{const result=await api("login",{username:formValue(f,"username"),
    password:formValue(f,"password"),otp:withMfa?formValue(f,"otp"):null});
    state.csrf=result.csrf;await start()
  }catch(err){showError(out,err)}finally{busy(f,false)}
 });
}
function showChangePassword(){
 const m=main(),p=panel("تغییر رمز اولیه GodAdmin",
  "برای امنیت حساب، رمز موقت نصب را به یک رمز قوی و اختصاصی تغییر دهید. رمز جدید حداقل ۱۶ کاراکتر باشد.");
 const f=node("form"),output=node("div");
 append(f,field("رمز فعلی","current","",{secret:true}),
   field("رمز جدید","updated","",{secret:true}),
   node("button","","ثبت رمز جدید"),output);
 append(p,f);append(m,p);
 f.addEventListener("submit",async e=>{
  e.preventDefault();busy(f,true);
  try{await api("change-password",{current:formValue(f,"current"),
    updated:formValue(f,"updated")});state.csrf=null;await start()
  }catch(err){showError(output,err)}finally{busy(f,false)}
 });
}
function showTotpEnroll(){
 const m=main(),p=panel("فعال‌سازی تأیید دومرحله‌ای",
  "کد QR را با Google Authenticator یا Microsoft Authenticator اسکن کنید، سپس کد شش‌رقمی برنامه را وارد کنید.");
 const qrCard=node("div","totp-qr-card");
 const qr=node("img","totp-qr");
 qr.alt="کد QR راه‌اندازی تأیید دومرحله‌ای آوان";
 qr.width=224;qr.height=224;
 const qrHint=node("p","hint","در برنامه Authenticator گزینه افزودن حساب و سپس اسکن QR Code را انتخاب کنید.");
 append(qrCard,qr,qrHint);
 const manual=node("details","totp-manual");
 const summary=node("summary","","در صورت عدم امکان اسکن، ورود دستی کلید");
 const secret=node("div","secret","در حال آماده‌سازی...");
 append(manual,summary,secret);
 const f=node("form"),out=node("div");
 const code=field("کد شش‌رقمی Authenticator","code");
 const otp=code.querySelector("input");
 otp.inputMode="numeric";otp.pattern="[0-9]{6}";otp.maxLength=6;
 otp.autocomplete="one-time-code";otp.placeholder="000000";
 append(f,code,node("button","","تأیید و فعال‌سازی"),out);
 function renderEnrollment(result){
  if(!result.qr_data_uri?.startsWith("data:image/svg+xml;base64,") || !result.secret)
   throw Error("کد QR قابل دریافت نیست.");
  qr.src=result.qr_data_uri;
  secret.textContent=result.secret;
 }
 const rotate=btn("ایجاد QR و کلید جدید",async()=>{
  if(!confirm("با تولید کلید جدید، QR و کلید قبلی نامعتبر می‌شوند. ادامه می‌دهید؟"))return;
  rotate.disabled=true;out.replaceChildren();
  try{
   const result=await api("totp/rotate",{});
   renderEnrollment(result);
   append(out,info("کلید قبلی نامعتبر شد. حساب جدید را در Authenticator اسکن کنید."));
  }catch(err){showError(out,err)}finally{rotate.disabled=false}
 },"secondary");
 append(p,qrCard,manual,info("اگر کلید قبلی را در اختیار دیگران قرار داده‌اید، قبل از اسکن یا تأیید کد روی «ایجاد QR و کلید جدید» بزنید."),rotate,f);
 append(m,p);
 api("totp/enrollment",{}).then(renderEnrollment).catch(err=>showError(out,err));
 f.addEventListener("submit",async e=>{
   e.preventDefault();busy(f,true);out.replaceChildren();
   try{await api("totp/confirm",{code:formValue(f,"code")});
     state.csrf=null;await start()
   }catch(err){showError(out,err)}finally{busy(f,false)}
 });
}

const menu=[
 ["agentdb","بانک اختصاصی Agent"],["mysql","داده‌های ProcessMaker"],["company","اطلاعات سازمان"],["identity","هویت سازمانی"],["processmaker","ProcessMaker"],
 ["ai","هوش مصنوعی"],["license","لایسنس و شناسه نصب"],["users","کاربران و سازمان"]
];
async function showSettings(page=state.page){
 const settings=await api("settings");state.settings=settings;state.page=page;
 const m=main();
 append(m,node("h1","","مدیریت سامانه"),
   node("p","intro","تنظیمات زیر از داخل آوان ذخیره می‌شوند؛ رمزها به مرورگر برگردانده نمی‌شوند و برای تغییر مجدد باید رمز تازه وارد شود."));
 const tabs=node("nav","tabs");
 for(const [code,title] of menu)append(tabs,btn(title,()=>showSettings(code),state.page===code?"active":""));
 append(tabs,btn("خروج امن",async()=>{
   try{await api("logout",{})}catch{}state.csrf=null;await start()
 },"secondary"));append(m,tabs);
 if(page==="agentdb")await renderAgentDatabase(m);
 else if(page==="mysql")renderMysql(m,settings.mysql||{});
 else if(page==="company")await renderCompany(m);
 else if(page==="identity")await renderIdentity(m);
 else if(page==="processmaker")renderPm(m,settings.processmaker||{});
 else if(page==="ai")renderAI(m,settings.ai||{});
 else if(page==="license")await renderLicense(m,settings);
 else if(page==="users")await renderUsers(m);
 else await renderCompany(m);
}
function renderMysql(m,config){
 const p=panel("داده‌های ProcessMaker", "اتصال فقط‌خواندنی به MySQL فرایندها؛ اطلاعات جلسه در خود ProcessMaker نگهداری می‌شود.");
 const f=node("form","grid");
 append(f,field("نشانی MySQL","host",config.host||"host.docker.internal"),
  field("پورت","port",String(config.port||3306)),field("بانک Workspace","database",config.database||"wf_workflow"),
  field("کاربر فقط‌خواندنی","username",config.username||"avan_reader"),
  field("رمز اتصال","password","",{secret:true}),field("اتصال TLS: yes یا no","tls",config.tls===false?"no":"yes"),field("گواهی CA داخلی MySQL (PEM، اختیاری)","ca_pem",config.ca_pem||"",{required:false}),field("منطقه زمانی ثبت تاریخ در ProcessMaker","timezone",config.timezone||"Asia/Tehran"));
 const out=node("div","full"),actions=node("div","actions full");
 async function execute(action){
  busy(f,true);out.replaceChildren();
  try{await api("mysql/"+action,{host:formValue(f,"host"),port:Number(formValue(f,"port")),
    database:formValue(f,"database"),username:formValue(f,"username"),password:formValue(f,"password"),tls:formValue(f,"tls").toLowerCase()==="yes",ca_pem:formValue(f,"ca_pem"),timezone:formValue(f,"timezone")});
    append(out,info(action==="save"?"تنظیمات اتصال ذخیره شد.":"اتصال و وجود هر دو فرایند تأیید شد."));
    if(action==="save")f.querySelector('[name="password"]').value="";
  }catch(e){showError(out,e)}finally{busy(f,false)}
 }
 append(actions,btn("بررسی اتصال",()=>execute("check"),"secondary"),btn("ذخیره اتصال",()=>execute("save")));
 append(f,actions,out);append(p,f);append(m,p);
}
async function renderIdentity(m){
 const p=panel("هویت سازمانی آوان",
  "Keycloak و تنظیمات OIDC جزو زیرساخت داخلی آوان هستند و نیازی به واردکردن Issuer، JWKS یا Client Secret توسط کاربر ندارند.");
 const result=node("div");
 append(p,info("Secretهای داخلی هنگام نصب امن Docker ساخته می‌شوند و هیچ‌وقت در این پنل یا فایل .env به کاربر نمایش داده نمی‌شوند."),result);
 try{
   const status=await api("identity/status");
   append(result,info(status.connected?
      "سرویس هویت داخلی آوان فعال است · Realm: "+status.realm:
      "سرویس هویت داخلی هنوز آماده نیست.",!status.connected));
 }catch(err){showError(result,err)}
 append(m,p);
}

function renderPm(m,config){
 const p=panel("اتصال ProcessMaker",
   "آوان فقط فهرست کاربران را با درخواست GET می‌خواند. حساب administrator نیز قابل استفاده است؛ محدودیتی روی سطح دسترسی خود حساب اعمال نمی‌شود.");
 const f=node("form","grid"),specs=[
  ["نشانی اصلی ProcessMaker","base_url",config.base_url||"http://host.docker.internal:84"],
  ["Workspace","workspace",config.workspace||"workflow"],
  ["توکن OAuth حساب ProcessMaker","bearer_token",""]
 ];
 append(p,info("برای نصب آزمایشی ProcessMaker روی همین لپ‌تاپ، نشانی http://host.docker.internal:84 و Workspace برابر workflow است. رمز ورود یا Client Secret را جای توکن وارد نکنید."));
 for(const [title,name,value] of specs)append(f,field(title,name,value||"",{secret:name==="bearer_token"}));
 const out=node("div","full"),actions=node("div","actions full");
 async function run(mode){
  const body={};for(const [,name] of specs)body[name]=formValue(f,name);
  out.replaceChildren();busy(f,true);
  try{await api("processmaker/"+mode,body);append(out,info(
    mode==="check"?"دسترسی API کاربران ProcessMaker تأیید شد.":
    "تنظیمات اتصال ذخیره شد؛ دسترسی کارکنان فقط پس از نگاشت و تأیید هویت فعال می‌شود."));
  }catch(err){showError(out,err)}finally{busy(f,false)}
 }
 append(actions,btn("بررسی اتصال",()=>run("check"),"secondary"),
   btn("ذخیره تنظیمات",()=>run("save")));
 append(f,actions,out);append(p,f);append(m,p);
}
async function renderLicense(m,settings){
 const p=panel("شناسه نصب و مجوز نرم‌افزار",
   "لایسنس باید توسط ناشر امضا شده و برای همین نصب و سازمان صادر شده باشد.");
 append(p,node("p","hint","شناسه نصب پایدار این سرور:"),
   node("div","secret",settings.installation_id||"موجود نیست"));
 append(p,info(settings.publisher_public_key_installed?
   "کلید عمومی ناشر روی سرور موجود است. کلید خصوصی صادرکننده هرگز وارد این برنامه نمی‌شود.":
   "کلید عمومی ناشر هنوز نصب نشده است. ناشر باید کلید اصلی مورد اعتماد را به نسخه نصب تحویل دهد."));
 const form=node("form"),result=node("div");
 append(form,field("کلید عمومی تأییدشده ناشر با فرمت PEM","pem","",{multiline:true}),
   node("button","","ثبت کلید عمومی ناشر"),result);
 form.addEventListener("submit",async e=>{
  e.preventDefault();busy(form,true);
  try{await api("license/public-key",{pem:formValue(form,"pem")});
    append(result,info("کلید عمومی ثبت شد."));await showSettings("license");
  }catch(err){showError(result,err)}finally{busy(form,false)}
 });
 append(p,form);
 const licenseForm=node("form");
 const licenseResult=node("div");
 append(licenseForm,
   field("شناسه UUID سازمانِ تأییدشده در آوان","tenant_id",""),
   field("متن لایسنس امضاشده ناشر","token","",{multiline:true}),
   node("button","","بررسی و فعال‌سازی لایسنس"),licenseResult);
 licenseForm.addEventListener("submit",async e=>{
   e.preventDefault();busy(licenseForm,true);
   try{
     const answer=await api("license/activate",{
       tenant_id:formValue(licenseForm,"tenant_id"),
       token:formValue(licenseForm,"token")
     });
     licenseForm.reset();
     licenseResult.replaceChildren();
     append(licenseResult,info("لایسنس امضاشده فعال شد. شناسه: "+answer.license_id+
       " · کاربران فعال: "+answer.active_users+" از "+answer.max_users+
       " · ماژول‌ها: "+answer.modules.join("، ")));
   }catch(err){showError(licenseResult,err)}finally{busy(licenseForm,false)}
 });
 append(p,node("h2","","فعالسازی مجوز سازمان"),licenseForm);
 append(m,p);
 try{const status=await api("license/status");if(status.valid)append(p,info(status.mode==="local_evaluation"?
   "حالت آزمایشی محلی · فقط همین رایانه · حداکثر "+status.max_users+" کاربر · بدون لایسنس فروش":
   "کاربران فعال: "+status.active_users+" از "+status.max_users+" · ظرفیت باقی‌مانده: "+status.remaining_seats+" · اعتبار: "+(status.remaining_days===null?"بدون انقضا":status.remaining_days+" روز")+" · پایان: "+(status.expires_at||"بدون انقضا")));else append(p,info(status.reason,true))}catch(e){append(p,info(e.message,true))}
}
async function renderUsers(m){
 const p=panel("کاربران و سازمان",
   "تنها حسابی قابل اتصال است که قبلاً با هویت امضاشده وارد آوان شده، ایمیل تأییدشده آن با کاربر فعال ProcessMaker مطابقت دارد و GodAdmin ارتباط را تصویب کند.");
 append(m,p);
 const refresh=btn("به‌روزرسانی درخواست‌های دسترسی",()=>showSettings("users"),"secondary");
 append(p,refresh);
 const syncResult=node("div");
 append(p,btn("تازه‌سازی وضعیت کاربران از ProcessMaker",async()=>{
   syncResult.replaceChildren();
   if(!confirm("فهرست کامل کاربران ProcessMaker دریافت شود و دسترسی کاربران غیرفعال/حذف‌شده در آوان مسدود گردد؟"))return;
   try{
     const r=await api("processmaker/refresh-users",{});
     append(syncResult,info("کاربران فعال بازبینی‌شده: "+r.refreshed_active_users+
         " · حساب‌های غیرفعال‌شده: "+r.disabled_unverified_users));
   }catch(err){showError(syncResult,err)}
 },"secondary"),syncResult);
 try{const mapped=await api("users/mapped");const list=panel("حساب‌های ثبت‌شده","کاربر غیرفعال از ظرفیت لایسنس خارج می‌شود و دسترسی اطلاعات ندارد.");
 for(const u of mapped.users){const row=node("div","actions");append(row,node("span","",(u.name||u.subject)+" · "+u.role+" · "+(u.enabled?"فعال":"غیرفعال")),btn(u.enabled?"غیرفعال‌کردن":"فعال‌کردن",async()=>{try{await api("users/enabled",{subject:u.subject,enabled:!u.enabled});await showSettings("users")}catch(e){showError(syncResult,e)}}));append(list,row)}append(p,list)}catch(e){append(p,info(e.message,true))}
 let pending=[];
 try{
   const response=await api("users/pending");
   pending=response.pending||[];
 }catch(err){append(p,info(err.message,true));return}
 if(!pending.length){
   append(p,info("درخواست تأییدشده‌ای در انتظار ثبت نیست. شخص موردنظر باید یک‌بار از فضای کاری آوان با حساب هویت سازمانی خود وارد شود تا درخواست او اینجا ظاهر شود."));
 }
 const link=node("a","visit","باز کردن ورود سازمانی در برگه جدید");
 link.href="/auth/login";link.target="_blank";link.rel="noopener noreferrer";
 append(p,link);
 let users=[];
 try{
   users=(await api("processmaker/users")).users||[];
 }catch(err){
   append(p,info("فهرست کاربران ProcessMaker در دسترس نیست. ابتدا تنظیمات آن بخش را ثبت و بررسی کن.",true));
   return;
 }
 for(const account of pending){
   const section=panel("درخواست "+account.name,
      "زمان ورود: "+account.seen_at_utc+" · شناسه سازمان: "+account.tenant_id);
   append(section,node("p","hint","حساب امضاشده: "+account.subject+
      " · ایمیل تأییدشده: "+(account.email_verified?account.email||"ثبت نشده":"خیر")+
      " · نقش‌های امضاشده: "+(account.roles||[]).join("، ")));
   const form=node("form","grid");
   append(form,field("نام حقوقی سازمان (مطابق لایسنس)","company_name",""));
   const pmLabel=node("label","full","کاربر فعال ProcessMaker");
   const select=node("select");select.name="pm_uid";
   const placeholder=node("option","","انتخاب کاربر با ایمیل برابر");placeholder.value="";
   append(select,placeholder);
   for(const user of users){
     if(!user.email||!account.email_verified||!account.email||
        user.email.toLowerCase()!==account.email.toLowerCase())continue;
     const opt=node("option","",user.name+" · "+user.email+" · "+user.pm_uid);
     opt.value=user.pm_uid;append(select,opt);
   }
   append(pmLabel,select);append(form,pmLabel);
   const roleLabel=node("label","","نقش سازمانی");
   const roleSelect=node("select");roleSelect.name="role";
   for(const [value,label] of [["Expert","کارشناس"],["Manager","مدیر"],["SysAdmin","مدیر سیستم"]]){
     if(value==="SysAdmin" && !(account.roles||[]).includes("SysAdmin"))continue;
     const opt=node("option","",label);opt.value=value;append(roleSelect,opt);
   }
   append(roleLabel,roleSelect);
   append(form,roleLabel,
     field("نام واحد سازمانی تأییدشده","department_name","",{required:false}),
     field("شناسه PM مدیر مستقیم (در صورت وجود)","manager_pm_uid","",
       {required:false}));
   const result=node("div","full");
   const submit=node("button","","تأیید و اتصال امن کاربر");submit.type="submit";
   append(form,submit,result);
   form.addEventListener("submit",async e=>{
     e.preventDefault();busy(form,true);result.replaceChildren();
     try{
       const mapped=await api("users/approve",{
         tenant_id:account.tenant_id,subject:account.subject,
         company_name:formValue(form,"company_name"),
         pm_uid:formValue(form,"pm_uid"),
         role:formValue(form,"role"),
         manager_pm_uid:formValue(form,"manager_pm_uid")||null,
         department_name:formValue(form,"department_name")||null
       });
       append(result,info("کاربر "+mapped.name+" به سازمان "+mapped.company_name+
           " متصل شد. برای استفاده از ماژول‌های سازمان، لایسنس امضاشده نیز لازم است."));
       await showSettings("users");
     }catch(err){showError(result,err)}finally{busy(form,false)}
   });
   append(section,form);append(p,section);
 }
}
async function renderCompany(m){
 const p=panel("اطلاعات سازمان",
  "نام سازمان و شناسه Tenant از داخل آوان مدیریت می‌شوند. شناسه سازمان در اولین ذخیره توسط خود سیستم ساخته و ثابت می‌شود.");
 const current=await api("company");
 const form=node("form"),out=node("div");
 append(form,field("نام رسمی سازمان","company_name",current.company_name||""),
   node("button","","ذخیره اطلاعات سازمان"),out);
 if(current.tenant_id)append(p,info("شناسه ثابت سازمان: "+current.tenant_id));
 form.addEventListener("submit",async e=>{
   e.preventDefault();busy(form,true);out.replaceChildren();
   try{
     const saved=await api("company/save",{company_name:formValue(form,"company_name")});
     append(out,info("اطلاعات سازمان ذخیره شد · Tenant ID: "+saved.tenant_id));
   }catch(err){showError(out,err)}finally{busy(form,false)}
 });
 append(p,form);append(m,p);
}

document.addEventListener("DOMContentLoaded",start);


function renderAI(m,config){
 const p=panel("اتصال هوش مصنوعی","تحلیل فقط روی داده‌های مجاز انجام می‌شود. با فعال‌سازی، پرسش و بخش‌های مرتبط سوابق برای پردازش به OpenAI ارسال می‌شوند.");
 const f=node("form"),out=node("div");f.addEventListener("submit",e=>e.preventDefault());
 const enabled=node("input");enabled.type="checkbox";enabled.checked=!!config.enabled;
 const label=node("label");append(label,enabled,node("span","","فعال‌سازی دستیار هوشمند"));
 const voiceEnabled=node("input");voiceEnabled.type="checkbox";voiceEnabled.checked=!!config.voice_enabled;
 const voiceLabel=node("label");append(voiceLabel,voiceEnabled,node("span","","فعال‌سازی تبدیل صوت به متن و خواندن پاسخ (مصرف API جداگانه)"));
 append(f,label,voiceLabel,field("نام مدل","model",config.model||"gpt-4.1-mini"),
  field("کلید API؛ برای حفظ کلید قبلی خالی بگذارید","api_key","",{type:"password"}),
  field("مدل تبدیل صوت (gpt-4o-mini-transcribe / gpt-4o-transcribe / whisper-1)","transcription_model",config.transcription_model||"gpt-4o-mini-transcribe"),
  field("مدل خواندن پاسخ (gpt-4o-mini-tts / tts-1 / tts-1-hd)","speech_model",config.speech_model||"gpt-4o-mini-tts"),
  field("صدا (alloy / coral / onyx / nova / shimmer)","voice",config.voice||"alloy"));
 append(f,btn("ذخیره تنظیمات",async()=>{
  busy(f,true);try{await api("ai/save",{enabled:enabled.checked,model:formValue(f,"model"),api_key:formValue(f,"api_key"),voice_enabled:voiceEnabled.checked,transcription_model:formValue(f,"transcription_model"),speech_model:formValue(f,"speech_model"),voice:formValue(f,"voice")});
   f.elements.namedItem("api_key").value="";out.replaceChildren(info("تنظیمات ذخیره شد."));
  }catch(e){showError(out,e)}finally{busy(f,false)}
 }),btn("بررسی اتصال ذخیره‌شده",async()=>{
  busy(f,true);try{const r=await api("ai/check",{});out.replaceChildren(info("اتصال و دسترسی به مدل "+r.model+" تأیید شد. اجرای تحلیل از صفحه دستیار انجام می‌شود."))}
  catch(e){showError(out,e)}finally{busy(f,false)}
 },"secondary"),out);append(p,f);append(m,p);
}

async function renderAgentDatabase(m){
 const p=panel("بانک اختصاصی آوان", "SQL Server داخلی Docker به‌صورت خودکار ساخته می‌شود. از این صفحه می‌توانید اتصال سازمانی دیگری را ثبت، ویرایش یا فعال کنید؛ اطلاعات جلسات همچنان فقط از MySQL پروسس‌میکر خوانده می‌شود.");
 const statusOut=node("div");append(p,statusOut);append(m,p);
 let status;
 try{status=await api("agent-db/connections")}catch(err){showError(statusOut,err);return}
 if(!status.active_id)append(statusOut,info("در حال حاضر هیچ بانک فعالی وجود ندارد؛ قابلیت‌های Agent تا فعال‌سازی یک اتصال متوقف هستند.",true));
 const list=panel("اتصال‌های ثبت‌شده","تنها یک اتصال می‌تواند فعال باشد. فعال‌سازی فقط پس از تست ساختار و دسترسی حساب محدود انجام می‌شود.");
 for(const c of status.connections){
  const row=node("div","connection-row"),details=node("div");
  append(details,node("strong","",c.name),node("p","hint",c.server+" · AVANAgent · "+(c.managed?"مدیریت‌شده توسط Docker":"اتصال خارجی")+(c.active?" · فعال":"")));
  const actions=node("div","actions");
  append(actions,btn("بررسی",async()=>{
   try{await api("agent-db/connections/check",{connection_id:c.id});statusOut.replaceChildren(info("اتصال «"+c.name+"» و سطح دسترسی حساب محدود تأیید شد."))}catch(err){showError(statusOut,err)}
  },"secondary"));
  if(!c.active)append(actions,btn("فعال‌سازی",async()=>{
   try{await api("agent-db/connections/activate",{connection_id:c.id});await showSettings("agentdb")}catch(err){showError(statusOut,err)}
  }));
  if(!c.managed)append(actions,btn("ویرایش",()=>showConnectionEditor(p,c),"secondary"));
  if(!c.managed&&!c.active)append(actions,btn("حذف",async()=>{
   if(!confirm("این اتصال ذخیره‌شده حذف شود؟ داده‌های خود SQL Server حذف نمی‌شوند."))return;
   try{await api("agent-db/connections/delete",{connection_id:c.id});await showSettings("agentdb")}catch(err){showError(statusOut,err)}
  },"secondary"));
  append(row,details,actions);append(list,row);
 }
 append(p,list,btn("افزودن اتصال خارجی",()=>showConnectionEditor(p,null),"secondary"));
 if(status.active_id)append(p,btn("قطع اتصال فعال",async()=>{
  if(!confirm("با قطع اتصال، گفتگو، پایش، پیش‌نویس و گزارش‌های Agent تا فعال‌سازی مجدد در دسترس نخواهند بود. ادامه می‌دهید؟"))return;
  try{await api("agent-db/connections/disconnect",{confirmation:"DISCONNECT"});await showSettings("agentdb")}catch(err){showError(statusOut,err)}
 },"secondary"));
 const manual=panel("ساخت AVANAgent روی SQL Server خارجی","این بخش فقط برای بانک سازمانی خارجی است. برای SQL Server داخلی Docker هیچ حساب مدیری لازم نیست.");
 const install=node("form","grid"),installOut=node("div","full");
 append(install,field("نشانی SQL Server","server","host.docker.internal,1433"),
  field("اعتماد به گواهی داخلی: yes یا no","trust","no"),
  field("حساب مدیر SQL","install_user","",{required:false}),
  field("رمز مدیر SQL؛ ذخیره نمی‌شود","install_password","",{secret:true,required:false}),
  field("برای تأیید ساخت، AVANAgent را وارد کنید","confirmation","",{required:false}),
  btn("ساخت بانک خارجی و فعال‌سازی",async()=>{
   busy(install,true);installOut.replaceChildren();
   try{await api("agent-db/prepare",{server:formValue(install,"server"),trust_server_certificate:formValue(install,"trust").toLowerCase()==="yes",username:formValue(install,"install_user"),password:formValue(install,"install_password"),confirmation:formValue(install,"confirmation")});await showSettings("agentdb")}
   catch(err){showError(installOut,err)}finally{const password=install.querySelector('[name="install_password"]');if(password)password.value="";busy(install,false)}
  }),installOut);append(manual,install);append(p,manual);
}

function showConnectionEditor(parent,current){
 const existing=parent.querySelector(".connection-editor");if(existing)existing.remove();
 const box=panel(current?"ویرایش اتصال خارجی":"اتصال خارجی جدید","حساب باید AVAN_AgentApp و بانک باید AVANAgent باشد. رمز خالی هنگام ویرایش، رمز قبلی را حفظ می‌کند.");
 box.classList.add("connection-editor");const f=node("form","grid"),out=node("div","full");
 append(f,field("نام اتصال","name",current?.name||"SQL Server سازمان"),
  field("نشانی SQL Server","server",current?.server||"host.docker.internal,1433"),
  field(current?"رمز جدید؛ برای حفظ رمز قبلی خالی بگذارید":"رمز AVAN_AgentApp","password","",{secret:true,required:!current}),
  field("اعتماد به گواهی داخلی: yes یا no","trust",current?.trust_server_certificate?"yes":"no"),
  btn("تست و ذخیره اتصال",async()=>{
   busy(f,true);out.replaceChildren();
   try{await api("agent-db/connections/save",{connection_id:current?.id||null,name:formValue(f,"name"),server:formValue(f,"server"),password:formValue(f,"password"),trust_server_certificate:formValue(f,"trust").toLowerCase()==="yes"});await showSettings("agentdb")}
   catch(err){showError(out,err)}finally{busy(f,false)}
  }),btn("انصراف",()=>box.remove(),"secondary"),out);append(box,f);parent.append(box);
}
