"use strict";
const state={csrf:null,user:null,settings:null,stage:"login",page:"sql"};
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
  "کلید زیر را در برنامه Authenticator وارد کنید و کد شش‌رقمی جدید را برای تأیید بفرستید. این کلید را در اختیار دیگران قرار ندهید.");
 const secret=node("div","secret","در حال آماده‌سازی کلید...");
 append(p,secret);
 const f=node("form"),out=node("div");
 append(f,field("کد شش‌رقمی Authenticator","code"),
   node("button","","تأیید و فعال‌سازی"),out);
 append(p,f);append(m,p);
 api("totp/enrollment",{}).then(result=>{
   secret.textContent=result.secret;
 }).catch(err=>showError(out,err));
 f.addEventListener("submit",async e=>{
   e.preventDefault();busy(f,true);
   try{await api("totp/confirm",{code:formValue(f,"code")});
     state.csrf=null;await start()
   }catch(err){showError(out,err)}finally{busy(f,false)}
 });
}
const menu=[
 ["install","نصب بانک اطلاعاتی"],["sql","اتصال SQL Server"],["oidc","هویت سازمانی"],["processmaker","ProcessMaker"],
 ["license","لایسنس و شناسه نصب"],["company","اطلاعات سازمان"]
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
 if(page==="install")renderInstall(m,settings.sql||{});
 else if(page==="sql")renderSql(m,settings.sql||{});
 else if(page==="oidc")renderOidc(m,settings.oidc||{});
 else if(page==="processmaker")renderPm(m,settings.processmaker||{});
 else if(page==="license")renderLicense(m,settings);
 else renderCompany(m,settings.company||{});
}
function renderInstall(m,config){
 const p=panel("راه‌اندازی کنترل‌شده بانک اصلی",
   "این مرحله جداول جدید AVAN و حساب SQL فقط‌خواندنی را در EnterpriseProcess2 اضافه می‌کند؛ جداول MTG و داده‌های جلسات تغییر نمی‌کنند.");
 append(p,info("قبل از اجرا از بانک EnterpriseProcess2 نسخه پشتیبان سالم و قابل بازیابی تهیه و توسط DBA تأیید کن. اگر ساختار MTG با انتظار برنامه تفاوت دارد، اجرای مهاجرت متوقف خواهد شد."));
 const f=node("form","grid");
 append(f,field("نشانی و پورت SQL Server","server",config.server||"host.docker.internal,1433"),
   field("حساب DBA با مجوز اجرای مهاجرت","dba_username",""),
   field("رمز موقت اتصال DBA؛ ذخیره نمی‌شود","dba_password","",{secret:true}),
   field("اعتماد به گواهی داخلی SQL Server: yes یا no","trust_server_certificate",
      config.trust_server_certificate?"yes":"no"));
 const backup=node("label","full"),checked=node("input");
 checked.type="checkbox";checked.name="backup_confirmed";checked.required=true;
 append(backup,checked,node("span","","تهیه نسخه پشتیبان قابل بازیابی از بانک اصلی توسط DBA تأیید شده است."));
 append(f,backup,field("برای تأیید نهایی نام بانک را عیناً وارد کن","confirmation","",
   {placeholder:"EnterpriseProcess2"}),field(
   "رمز حساب AVAN_Reader (فقط اگر این حساب قبلاً ساخته شده است)","existing_reader_password","",{secret:true,required:false}),
   field("رمز حساب AVAN_ConfigWriter (فقط اگر این حساب قبلاً ساخته شده است)",
     "existing_writer_password","",{secret:true,required:false}));
 const actions=node("div","actions full"),result=node("div","full");
 let inventoryDone=false;
 function data(){
  return {server:formValue(f,"server"),dba_username:formValue(f,"dba_username"),
   dba_password:formValue(f,"dba_password"),
   trust_server_certificate:formValue(f,"trust_server_certificate").toLowerCase()==="yes"};
 }
 async function inventory(){
  busy(f,true);result.replaceChildren();inventoryDone=false;
  try{
   const report=await api("sql/inventory",data());
   inventoryDone=report.required_columns_missing.length===0 && report.has_server_dba_permission;
   append(result,info("بانک: "+report.database+" · ساختار AVAN: "+
      (report.avan_tables_present?"ایجاد شده":"نیازمند نصب")+
      " · مجوز DBA: "+(report.has_server_dba_permission?"تأیید شده":"کافی نیست")));
   if(report.required_columns_missing.length)append(result,info(
       "اختلاف ساختار MTG: "+report.required_columns_missing.join("، "),true));
   else append(result,info("ستون‌های الزامی MTG موجودند؛ پس از تأیید نسخه پشتیبان می‌توان مهاجرت افزودنی را اجرا کرد."));
  }catch(err){showError(result,err)}finally{busy(f,false)}
 }
 async function install(){
  result.replaceChildren();
  if(!inventoryDone){append(result,info("ابتدا ساختار بانک و سطح دسترسی DBA را بررسی کن.",true));return}
  if(!checked.checked||formValue(f,"confirmation")!=="EnterpriseProcess2"){
   append(result,info("تأیید نسخه پشتیبان و ورود نام دقیق بانک الزامی است.",true));return
  }
  if(!confirm("مهاجرت افزودنی AVAN و ایجاد یا اعطای مجوز حساب AVAN_Reader روی EnterpriseProcess2 اجرا شود؟"))return;
  busy(f,true);
  try{
   const body={...data(),backup_confirmed:true,
      confirmation:formValue(f,"confirmation"),
      existing_reader_password:formValue(f,"existing_reader_password")||null,
      existing_writer_password:formValue(f,"existing_writer_password")||null};
   const output=await api("sql/prepare",body);
   f.reset();inventoryDone=false;
   append(result,info(output.dedicated_reader_ready?
      "ساختار AVAN و حساب صرفاً خواندنی ایجاد/تأیید شد و اطلاعات اتصال به شکل رمزگذاری‌شده داخل آوان ذخیره شد.":
      "نتیجه مهاجرت قطعی نیست؛ جزییات سرور را بررسی کن."));
  }catch(err){showError(result,err)}finally{busy(f,false)}
 }
 append(actions,btn("۱. بررسی اختلاف بانک",inventory,"secondary"),
   btn("۲. اجرای نصب بعد از تأیید پشتیبان",install));
 append(f,actions,result);append(p,f);append(m,p);
}
function renderSql(m,config){
 const p=panel("اتصال بانک اطلاعاتی جلسات",
   "بانک عملیاتی EnterpriseProcess2 · حساب SQL فقط‌خواندنی AVAN_Reader. اجرای این بخش هیچ جدول یا مصوبه‌ای را تغییر نمی‌دهد.");
 const form=node("form","grid");
 append(form,field("نشانی SQL Server و پورت","server",config.server||"host.docker.internal,1433"),
   field("نام دیتابیس","database","EnterpriseProcess2",{required:true}),
   field("نام کاربری SQL","username","AVAN_Reader"),
   field("رمز عبور حساب SQL (هنگام ذخیره دوباره وارد شود)","password","",{secret:true}),
   field("تأیید گواهی SQL Server","trust_server_certificate",
     config.trust_server_certificate?"yes":"no",{placeholder:"no یا yes"}));
 const out=node("div","full");
 const actions=node("div","actions full");
 const body=()=>({server:formValue(form,"server"),database:formValue(form,"database"),
   username:formValue(form,"username"),password:formValue(form,"password"),
   trust_server_certificate:formValue(form,"trust_server_certificate").toLowerCase()==="yes"});
 async function execute(action){
   out.replaceChildren();busy(form,true);
   try{const result=await api("sql/"+action,body());append(out,
     info(action==="check"?"اتصال برقرار است؛ وضعیت ساختار AVAN: "+(result.avan_schema_present?"موجود":"هنوز ایجاد نشده"):
       "اتصال بانک با موفقیت در تنظیمات امن آوان ثبت شد."));
   }catch(err){showError(out,err)}finally{busy(form,false)}
 }
 append(actions,btn("بررسی اتصال",()=>execute("check"),"secondary"),
   btn("ذخیره تنظیمات اتصال",()=>execute("save")));
 append(form,actions,out);append(p,form,
   info("اگر ساختار AVAN هنوز وجود ندارد، فایل مهاجرت افزودنی بانک اصلی باید با مجوز DBA و نسخه پشتیبان تأییدشده اعمال شود. اطلاعات DBA در آوان ذخیره نمی‌شود."));
 append(m,p);
}
function renderOidc(m,config){
 const p=panel("اتصال هویت سازمانی (Keycloak / OIDC)",
  "نشانی Realm با HTTPS و شناسه برنامه محرمانه را ثبت کنید. ورود سازمانی پس از تطبیق شناسه کاربر با ProcessMaker فعال می‌شود.");
 const f=node("form","grid"),specs=[
  ["نشانی صادرکننده OIDC (Issuer)","issuer",config.issuer],
  ["Audience توکن","audience",config.audience],
  ["نشانی کلیدهای امضا JWKS","jwks_url",config.jwks_url],
  ["شناسه برنامه محرمانه","client_id",config.client_id],
  ["رمز محرمانه برنامه","client_secret",""]
 ];
 for(const [label,name,value] of specs)append(f,field(label,name,value||"",{secret:name==="client_secret"}));
 const result=node("div","full"),buttons=node("div","actions full");
 async function run(action){
  const body={};for(const [,name] of specs)body[name]=formValue(f,name);
  busy(f,true);result.replaceChildren();
  try{await api("oidc/"+action,body);append(result,info(
    action==="check"?"نشانی‌های Realm و کلیدهای امضا تأیید شدند.":
    "تنظیمات هویت سازمانی رمزگذاری و ذخیره شدند."));
  }catch(err){showError(result,err)}finally{busy(f,false)}
 }
 append(buttons,btn("بررسی سرویس هویت",()=>run("check"),"secondary"),
   btn("ذخیره هویت سازمانی",()=>run("save")));
 append(f,buttons,result);append(p,f,info(
  "نکته امنیتی: ساخت حساب کاربر، نقش SysAdmin و نگاشت PMUserUID با sub توکن کاربر پس از تأیید هویت واقعی انجام می‌شود؛ ورود کاربران صرفاً با ذخیره این تنظیمات باز نخواهد شد."));
 append(m,p);
}
function renderPm(m,config){
 const p=panel("اتصال ProcessMaker","تنظیمات سرویس فقط‌خواندنی برای دریافت فهرست کاربران فرایند.");
 const f=node("form","grid"),specs=[
  ["نشانی HTTPS ProcessMaker","base_url",config.base_url],
  ["Workspace","workspace",config.workspace],
  ["توکن دسترسی فقط‌خواندنی","bearer_token",""]
 ];
 for(const [title,name,value] of specs)append(f,field(title,name,value||"",{secret:name==="bearer_token"}));
 const out=node("div","full"),actions=node("div","actions full");
 async function run(mode){
  const body={};for(const [,name] of specs)body[name]=formValue(f,name);
  out.replaceChildren();busy(f,true);
  try{await api("processmaker/"+mode,body);append(out,info(
    mode==="check"?"اتصال کاربران ProcessMaker برقرار شد.":
    "تنظیمات اتصال ذخیره شد؛ دسترسی کاربران فقط پس از نگاشت و تأیید هویت فعال می‌شود."));
  }catch(err){showError(out,err)}finally{busy(f,false)}
 }
 append(actions,btn("بررسی اتصال",()=>run("check"),"secondary"),
   btn("ذخیره تنظیمات",()=>run("save")));
 append(f,actions,out);append(p,f);append(m,p);
}
function renderLicense(m,settings){
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
   field("شناسه UUID سازمانِ تأییدشده در EnterpriseProcess2","tenant_id",""),
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
}
function renderCompany(m,config){
 const p=panel("اطلاعات سازمان",
  "نام و هویت بصری سازمان بعد از تأیید ارتباط پایگاه داده و مجوزها قابل ثبت است.");
 append(p,info("نمایش نام سازمان در بخش کارکنان از بانک EnterpriseProcess2 و مجوز سازمانی تأییدشده خوانده می‌شود. تنظیمات هویتی که داده‌های مشتری را تغییر دهند، بدون مجوز مستقل اعمال نمی‌شوند."));
 append(m,p);
}
document.addEventListener("DOMContentLoaded",start);
