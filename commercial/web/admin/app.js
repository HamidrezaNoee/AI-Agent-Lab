"use strict";
const state={csrf:null,user:null,settings:null,stage:"login",page:"connections",authMode:"bootstrap"};
const $=id=>document.getElementById(id);
function node(tag,cls,text){const n=document.createElement(tag);if(cls)n.className=cls;if(text!==undefined)n.textContent=String(text);return n}
function append(parent,...items){for(const item of items.flat())if(item!==null&&item!==undefined)parent.append(item);return parent}
const helpContent={
 connections:{steps:[
  "اینجا وضعیت ثبت‌شدهٔ اتصال‌ها دیده می‌شود؛ «تنظیم‌شده» نتیجهٔ بررسی زندهٔ سرویس نیست. برای اطمینان، دکمه بررسی همان اتصال را بزنید.",
  "SQL Server داخلی آوان با Docker ساخته می‌شود. اتصال ProcessMaker از MySQL خوانده می‌شود؛ برای موتورهای دیگر ابتدا آداپتر AVAN REST v1 آماده کنید.",
  "از این فهرست به صفحهٔ هر اتصال بروید: در BPMS می‌توانید چند منبع بسازید و هرکدام را مستقل غیرفعال کنید؛ برای Agent SQL فقط یک بانک هم‌زمان فعال است."
 ]},
 agentdb:{steps:[
  "برای SQL Server داخلی اطلاعاتی وارد نکنید: docker compose بانک AVANAgent و حساب AVAN_AgentApp را راه‌اندازی می‌کند؛ در فهرست «SQL Server داخلی Docker» را بررسی و فعال کنید.",
  "برای SQL Server خارجی، نشانی و پورت را از SQL Server Configuration Manager → SQL Server Network Configuration → TCP/IP → IPAll بگیرید. از داخل کانتینر، SQL Server روی همان ویندوز معمولاً host.docker.internal,1433 است.",
  "ساخت بانک خارجی فقط یک‌بار با حساب مدیر SQL و تأیید AVANAgent انجام می‌شود. پس از ساخت، اتصال را با رمز حساب محدود AVAN_AgentApp ثبت کنید؛ رمز مدیر ذخیره نمی‌شود.",
  "با «بررسی» دسترسی واقعی را بسنجید. ویرایش اتصال فعال پس از اعتبارسنجی اعمال می‌شود. قطع اتصال فعال دستیار و گزارش‌های ذخیره‌شدهٔ Agent را موقتاً از دسترس خارج می‌کند."
 ],fields:{name:"یک عنوان دلخواه برای تشخیص این بانک در فهرست، مثلاً SQL سازمان. نام سرور یا رمز را در عنوان ننویسید.",server:"آدرس قابل دسترس از کانتینر آوان با قالب server,port؛ نام یا IP و پورت ثابت را از مدیر SQL Server یا SQL Server Configuration Manager → TCP/IP → IPAll دریافت کنید.",password:"رمز SQL Login محدود AVAN_AgentApp در بانک AVANAgent را از مدیر بانک بگیرید. برای اتصال Docker داخلی این بخش لازم نیست؛ اگر نشانی سرور عوض نشود، رمز خالی در ویرایش رمز قبلی را نگه می‌دارد.",trust:"اگر گواهی TLS سرور در کانتینر مورد اعتماد است no بگذارید. yes فقط برای گواهی داخلی خودامضا پس از تأیید مدیر زیرساخت؛ اتصال SQL همچنان رمزگذاری می‌شود.",install_user:"نام حساب مدیر SQL با اختیار ساخت AVANAgent را از DBA بگیرید؛ فقط هنگام نصب خارجی استفاده می‌شود و ذخیره نمی‌شود.",install_password:"رمز همان حساب مدیر SQL؛ در فایل تنظیمات آوان ذخیره نمی‌شود.",confirmation:"برای جلوگیری از ساخت ناخواسته، دقیقاً AVANAgent بنویسید."}},
 bpms:{steps:[
  "هر BPMS غیر از ProcessMaker به یک مبدل HTTPS مستقل نیاز دارد که GET /avan/v1/identity و GET /avan/v1/bi/processes را مطابق راهنمای قرارداد آوان ارائه کند. اتصال مستقیم به پایگاه داده آن موتور اضافه نمی‌شود.",
  "نشانی، نام و توکن حساب فقط‌خواندنی را از تیم همان BPMS/آداپتر بگیرید. شناسه tenant پاسخ identity باید با «اطلاعات سازمان» برابر باشد.",
  "ابتدا بررسی، سپس ذخیره کنید. از فهرست، هر منبع را مستقل ویرایش، فعال/غیرفعال یا حذف کنید. هنگام ویرایش، کادر توکن را خالی بگذارید تا توکن قبلی حفظ شود.",
  "غیرفعال‌کردن بلافاصله گزارش آن منبع را می‌بندد؛ فعال‌سازی دوباره اتصال و شناسه سازمان را بررسی می‌کند. حذف فقط تنظیمات منبع در آوان را پاک می‌کند."
 ],fields:{name:"نام قابل‌فهم موتور، مثل «فرایند خرید شرکت الف»؛ این مقدار عنوان نمایشی است.",base_url:"آدرس ریشهٔ HTTPS مبدل را از تیم BPMS بگیرید؛ با پورت استاندارد 443 یا 8443، بدون /avan/v1/identity، پارامتر، نام کاربری یا رمز در URL.",bearer_token:"توکن اختصاصی حساب integration فقط‌خواندنی را تیم آداپتر می‌سازد. در ویرایش با همان آدرس می‌توانید آن را خالی بگذارید؛ تغییر نشانی آداپتر نیازمند توکن جدید است."}},
 mysql:{steps:[
  "در phpMyAdmin مربوط به ProcessMaker، زبانهٔ SQL را باز کنید و جداگانه SELECT DATABASE(); و SHOW VARIABLES LIKE 'port'; و SHOW VARIABLES LIKE 'have_ssl'; را اجرا کنید. این دستورها داخل PowerShell اجرا نمی‌شوند.",
  "کاربر SELECT روی جدول‌های لازم ProcessMaker را از مدیر MySQL بگیرید. نشانی را از دید کانتینر وارد کنید: برای MySQL روی همان ویندوز معمولاً host.docker.internal، نه 127.0.0.1 داخل کانتینر.",
  "اگر have_ssl برابر DISABLED است TLS را no بگذارید. تاریخ‌ها را با منطقه زمانی IANA مانند Asia/Tehran تفسیر کنید؛ مقدار Windows مانند Iran Standard Time را اینجا نگذارید.",
  "ابتدا بررسی اتصال، سپس ذخیره. بررسی افزون بر دسترسی خواندنی، وجود هر دو فرایند جلسه و اقدام مصوب را می‌سنجد."
 ],fields:{host:"نامی که کانتینر آوان از آن به MySQL می‌رسد؛ برای MySQL روی همان ویندوز host.docker.internal. آدرس phpMyAdmin و پورت وب، نشانی MySQL نیستند.",port:"در phpMyAdmin → SQL اجرا کنید: SHOW VARIABLES LIKE 'port'; غالباً 3306 است.",database:"در phpMyAdmin بانک Workspace را از ستون سمت چپ یا SELECT DATABASE(); ببینید؛ در نصب فعلی شما bitnami_pm گزارش شده است.",username:"یک کاربر دارای SELECT فقط روی جدول‌های موردنیاز ProcessMaker؛ نام و GRANTهای دقیق را از مدیر MySQL بگیرید، نه رمز root.",password:"رمز همان حساب فقط‌خواندنی MySQL. برای تغییر تنظیمات باید آن را دوباره وارد کنید؛ رمز ذخیره‌شده در مرورگر نمایش داده نمی‌شود.",tls:"در phpMyAdmin → SQL دستور SHOW VARIABLES LIKE 'have_ssl'; را اجرا کنید؛ اگر DISABLED است no، اگر TLS و گواهی درست نصب شده است yes.",ca_pem:"در صورت فعال بودن TLS، متن گواهی CA صادرکنندهٔ گواهی سرور MySQL را از مدیر زیرساخت بگیرید؛ وقتی TLS خاموش است خالی بماند.",timezone:"منطقه زمانی IANA محل ثبت تاریخ ProcessMaker، برای ایران Asia/Tehran. عبارت Iran Standard Time مخصوص Windows و برای این فیلد نامعتبر است."}},
 company:{steps:["نام رسمی سازمان را مطابق نام درج‌شده روی لایسنس بنویسید. پس از نخستین ذخیره، آوان Tenant ID ثابت می‌سازد.","Tenant ID نمایش‌داده‌شده در همین صفحه را برای حساب‌های Keycloak، آداپترهای BPMS و صدور لایسنس به تیم مربوط تحویل دهید. شناسه را حدس نزنید."],fields:{company_name:"نام حقوقی سازمان را از مدارک ثبتی یا قرارداد خرید و دقیقاً مطابق نام مشتری در لایسنس بگیرید."}},
 identity:{steps:["Keycloak همراه نصب Docker آوان راه‌اندازی می‌شود؛ Issuer و Client Secret داخل برنامه نصب و مدیریت می‌شوند و نیازی به گرفتن آن‌ها از ProcessMaker نیست.","در راه‌اندازی اولیه، پس از ثبت سازمان حساب سازمانی GodAdmin را اینجا بسازید یا با حساب موجود یک‌بار ورود کنید؛ سپس شناسهٔ امضاشدهٔ همان حساب را با کد تازهٔ Authenticator تأیید کنید.","پس از اتصال GodAdmin، ورود و خروج به فضای کار و تنظیمات با همان حساب سازمانی انجام می‌شود."],fields:{username:"نام کاربری اختصاصی برای حساب سازمانی GodAdmin در Keycloak؛ با نام ورود ProcessMaker یکی نیست.",email:"ایمیل قابل دسترس مدیر سامانه را از دفترچه تماس سازمان بگیرید؛ برای ساخت حساب هویت سازمانی لازم است.",name:"نام نمایشی مدیر سامانه در سرویس هویت سازمانی.",password:"رمز موقت قوی دست‌کم ۱۶ کاراکتری برای حساب تازه؛ پس از اولین ورود باید تغییر داده شود.",otp:"کد شش‌رقمی تازه از برنامه Authenticator متصل به حساب GodAdmin اولیه؛ کد منقضی‌شده را تکرار نکنید."}},
 processmaker:{steps:["آدرس اصلی ProcessMaker را از مرورگر بردارید: تنها پروتکل، نام میزبان و پورت؛ مسیر /sysworkflow یا نشانی phpMyAdmin را وارد نکنید. از کانتینر میزبان ویندوز معمولاً host.docker.internal است.","Workspace را از ابتدای مسیر ProcessMaker مانند /sysworkflow/ بردارید که در این مثال workflow است. توکن Bearer مجاز برای GET فهرست کاربران را از مسئول API/OAuth همان ProcessMaker دریافت کنید.","در محیط آزمایشی این نسخه، HTTP برای host.docker.internal روی پورت 84 یا 443 مجاز است؛ در نصب عملیاتی HTTPS لازم است. بررسی اتصال فقط GET کاربران را اجرا می‌کند."],fields:{base_url:"آدرس ریشهٔ ProcessMaker از مرورگر، مانند http://host.docker.internal:443؛ شمارهٔ پورت را مطابق وب‌سرور ProcessMaker بگذارید، نه پورت phpMyAdmin.",workspace:"از /sysworkflow/en/...، مقدار workflow را بردارید. اگر در URL شما /sysنامدیگر/ است، بخش بعد از sys را قرار دهید.",bearer_token:"توکن OAuth/Bearer معتبرِ حساب مجاز به خواندن کاربران از مسئول ProcessMaker؛ رمز ورود یا Client Secret را جای آن وارد نکنید. هنگام تغییر، توکن را دوباره وارد کنید."}},
 ai:{steps:["کلید API را از حساب رسمی ارائه‌دهندهٔ مدل که برای آوان فعال شده است دریافت کنید و آن را در چت، URL یا فایل عمومی قرار ندهید.","مدلی را وارد کنید که حساب API به آن دسترسی دارد. ابتدا ذخیره، سپس «بررسی اتصال ذخیره‌شده» را اجرا کنید؛ بررسی دسترسی مدل، تولید پاسخ واقعی را آزمایش نمی‌کند.","گزینهٔ صوت فقط وقتی نیاز است فعال شود؛ تبدیل صوت و تولید گفتار هر کدام مصرف API دارند."],fields:{model:"شناسهٔ مدل مجاز برای حساب API را از پنل ارائه‌دهنده یا قرارداد سرویس سازمان بگیرید؛ مقدار پیش‌فرض برنامه را تنها در صورت دسترسی حساب نگه دارید.",api_key:"کلید محرمانهٔ حساب API آوان از پنل ارائه‌دهنده؛ هنگام ویرایش خالی بماند تا کلید قبلی حفظ شود.",transcription_model:"شناسهٔ مدل صوت به متن را از فهرست مجاز این نسخه انتخاب کنید؛ مقدار پیش‌فرض قابل استفاده است اگر حساب دسترسی دارد.",speech_model:"مدل تبدیل متن به گفتار را از گزینه‌های مجاز همین فرم انتخاب کنید.",voice:"نام صدای پشتیبانی‌شده برای تولید گفتار؛ یکی از گزینه‌های نوشته‌شده در عنوان همین فیلد."}},
 license:{steps:["شناسه نصب را از بالای همین صفحه و Tenant ID را از صفحهٔ «اطلاعات سازمان» بردارید و برای صادرکنندهٔ مجوز ارسال کنید.","فقط کلید عمومی PEM تأییدشدهٔ ناشر را ثبت کنید؛ کلید خصوصی نباید وارد آوان شود. توکن لایسنس امضاشده را از ناشر بگیرید.","برای نصب آزمایشی محلی وضعیت مجوز را پایین همین صفحه ببینید؛ فعال‌سازی مجوز فروش باید برای همین نصب، سازمان، ظرفیت کاربران و تاریخ صادر شده باشد."],fields:{pem:"متن کامل کلید عمومی ECDSA P-256 با سطرهای BEGIN/END PUBLIC KEY را از ناشر معتبر نسخه دریافت کنید؛ کلید خصوصی هرگز لازم نیست.",tenant_id:"شناسه UUID تولیدشده در صفحه «اطلاعات سازمان»؛ همان شناسه ثبت‌شده در متن لایسنس.",token:"رشتهٔ کامل لایسنس امضاشدهٔ تحویلی از ناشر را بدون تغییر اینجا قرار دهید."}},
 users:{steps:["فرد ابتدا با حساب سازمانی خود از صفحهٔ ورود آوان وارد شود تا درخواست «در انتظار» شکل بگیرد؛ سپس درخواست‌ها را در همین صفحه به‌روزرسانی کنید.","برای اتصال کاربر، ایمیل تأییدشدهٔ حساب سازمانی باید با ایمیل یک کاربر فعال ProcessMaker برابر باشد. فهرست PM از بخش اتصال ProcessMaker خوانده می‌شود.","شناسه مسئول مستقیم را از همان فهرست کاربران PM بررسی کنید؛ پس از تصویب، وضعیت فعال و ظرفیت لایسنس را از فهرست کاربران کنترل کنید."],fields:{company_name:"نام رسمی سازمان مطابق «اطلاعات سازمان» و لایسنس فعال.",pm_uid:"کاربر فعال ProcessMaker با ایمیل برابر؛ از فهرست قابل انتخاب همین فرم بردارید، نه از نام نمایشی.",role:"نقش سازمانی را براساس مجوز واقعی فرد انتخاب کنید؛ نقش مدیر سیستم نیازمند نقش امضاشدهٔ SysAdmin است.",department_name:"نام واحد تأییدشده در ساختار سازمان یا پرونده پرسنلی؛ در صورت نامشخص بودن خالی بگذارید.",manager_pm_uid:"شناسه PM مدیر مستقیم از فهرست کاربران ProcessMaker؛ در صورت نبود مدیر مستقیم خالی بگذارید."}}
};
function helpLamp(title,lines,compact=false){
 if(!lines?.length)return null;
 const detail=node("details",compact?"help-lamp compact":"help-lamp");
 const summary=node("summary","",compact?"💡 راهنمای این فیلد":"💡 آموزش این بخش و محل دریافت اطلاعات");
 summary.setAttribute("aria-label","راهنمای "+title);append(detail,summary);
 const list=node("ol");for(const line of lines)append(list,node("li","",line));append(detail,list);
 return detail;
}
function field(title,name,value="",options={}){
 const wrap=node("div","form-field"),label=node("label","",title),input=node(options.multiline?"textarea":"input");
 input.name=name;if(!options.multiline)input.type=options.secret?"password":options.type||"text";
 if(options.multiline)input.value=value||"";else input.value=value||"";
 input.required=options.required!==false;input.autocomplete="off";
 if(options.placeholder)input.placeholder=options.placeholder;
 append(label,input);append(wrap,label);
 const hint=options.help||helpContent[state.page]?.fields?.[name];
 if(hint)append(wrap,helpLamp(title,[hint],true));
 return wrap;
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
  state.csrf=s.csrf;state.authMode=s.auth_mode;
  if(!s.authenticated && s.auth_mode==="oidc")window.location.assign("/auth/login");
  else if(!s.authenticated)showLogin(s.mfa_enrolled);
  else if(!s.password_changed)showChangePassword();
  else if(!s.mfa_enrolled)showTotpEnroll();
  else if(!s.mfa_authenticated)showLogin(true);
  else await showSettings();
 }catch(err){main().append(info(err.message||String(err),true))}
}
function showLogin(withMfa){
 const m=main(),p=panel("ورود به آوان","با حساب GodAdmin وارد شوید.");
 p.classList.add("login");const f=node("form");
 append(f,field("نام کاربری","username","godadmin"),
   field("رمز عبور","password","",{secret:true}));
 if(withMfa)append(f,field("کد شش‌رقمی برنامه Authenticator","otp","",{required:true}));
 const out=node("div");
 const captchaWrap=node("div","bootstrap-captcha");
 const captchaImage=node("img");captchaImage.alt="کد امنیتی تصویر";captchaImage.width=260;captchaImage.height=85;
 const answer=field("کد امنیتی تصویر","captcha_answer","",{required:true});
 const refresh=btn("تصویر جدید",()=>loadCaptcha(),"secondary");
 const challenge=node("input");challenge.type="hidden";challenge.name="challenge";
 append(captchaWrap,captchaImage,refresh,answer,challenge);append(f,captchaWrap);
 const loginBtn=node("button","","ورود به تنظیمات");loginBtn.type="submit";
 append(f,loginBtn,out);append(p,f);append(m,p);
 async function loadCaptcha(){
  loginBtn.disabled=true;challenge.value="";captchaImage.removeAttribute("src");
  try{const result=await api("captcha");captchaImage.src=result.image;challenge.value=result.challenge;
      answer.querySelector("input").value="";out.replaceChildren();}
  catch(err){showError(out,err)}finally{loginBtn.disabled=!challenge.value}
 }
 loadCaptcha();
 f.addEventListener("submit",async e=>{
  e.preventDefault();busy(f,true);out.replaceChildren();
  try{const result=await api("login",{username:formValue(f,"username"),
    password:formValue(f,"password"),otp:withMfa?formValue(f,"otp"):null,
    challenge:formValue(f,"challenge"),captcha_answer:formValue(f,"captcha_answer")});
    state.csrf=result.csrf;await start()
  }catch(err){await loadCaptcha();showError(out,err)}finally{busy(f,false);loginBtn.disabled=!challenge.value}
 });
}
function showChangePassword(){
 const m=main(),p=panel("تغییر رمز اولیه GodAdmin",
  "برای امنیت حساب، رمز موقت نصب را به یک رمز قوی و اختصاصی تغییر دهید. رمز جدید حداقل ۱۶ کاراکتر باشد.");
 const f=node("form"),output=node("div");
 append(p,helpLamp("تغییر رمز",["رمز فعلی همان رمز موقت دریافتی با --take-bootstrap پس از اجرای کانتینر است؛ از مسئول نصب آن را دریافت کنید.",
  "رمز جدید اختصاصی و طولانی انتخاب کنید و فقط در محل امن سازمان نگهداری کنید."]));
 append(f,field("رمز فعلی","current","",{secret:true,help:"رمز اولیهٔ تحویل‌شده توسط مسئول نصب."}),
   field("رمز جدید","updated","",{secret:true,help:"رمز اختصاصی دست‌کم ۱۶ کاراکتری برای GodAdmin اولیه."}),
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
 append(p,helpLamp("تأیید دومرحله‌ای",[
  "در برنامه Authenticator گزینه افزودن حساب و اسکن QR را بزنید؛ اگر دوربین در دسترس نیست کلید زیر QR را دستی وارد کنید.",
  "کد شش‌رقمی در همان برنامه نمایش داده می‌شود و زمان‌دار است. QR و کلید دستی را در اختیار دیگران قرار ندهید."
 ]));
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
 const code=field("کد شش‌رقمی Authenticator","code","",{help:"کد فعلی حساب تازه افزوده‌شده در Google یا Microsoft Authenticator."});
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
 ["connections","همه اتصال‌ها"],["agentdb","بانک اختصاصی Agent"],["bpms","اتصالات BPMS"],["mysql","داده‌های ProcessMaker"],["company","اطلاعات سازمان"],["identity","هویت سازمانی"],["processmaker","ProcessMaker"],
 ["ai","هوش مصنوعی"],["license","لایسنس و شناسه نصب"],["users","کاربران و سازمان"]
];
async function showSettings(page=state.page){
 const settings=await api("settings");state.settings=settings;state.page=page;
 const m=main();
 const hero=node("div","admin-hero");append(hero,node("span","eyebrow","AVAN · CONTROL CENTER"),
  node("h1","","مدیریت سامانه"),node("p","intro","اتصال‌ها و تنظیمات آوان از همینجا مدیریت می‌شوند. رمزها پس از ذخیره دوباره به مرورگر نمایش داده نمی‌شوند."));append(m,hero);
 const tabs=node("nav","tabs");
 tabs.setAttribute("aria-label","بخش‌های تنظیمات");
 for(const [code,title] of menu){const item=btn(title,()=>{state.bpmsEdit=null;showSettings(code)},state.page===code?"active":"");
   if(code===page)item.setAttribute("aria-current","page");append(tabs,item)}
 append(tabs,btn("خروج امن",async()=>{
   if(state.authMode==="oidc"){
    try{
     const response=await fetch("/auth/logout",{method:"POST",credentials:"same-origin",
       headers:{"X-AVAN-CSRF":state.csrf,"Accept":"application/json"}});
     if(!response.ok)throw Error("خروج انجام نشد؛ دوباره تلاش کنید.");
     const result=await response.json();state.csrf=null;
     try{localStorage.setItem("avan-logout",String(Date.now()))}catch(_){}
     window.location.assign(result.logout_url||"/auth/signed-out");
    }catch(err){append(m,info(err.message,true))}
   }else{
    try{await api("logout",{});state.csrf=null;await start()}
    catch(err){append(m,info(err.message,true))}
   }
 },"secondary"));append(m,tabs);
 const guide=helpLamp(menu.find(x=>x[0]===page)?.[1]||"تنظیمات",helpContent[page]?.steps);
 if(guide)append(m,guide);
 if(page==="connections")await renderConnections(m,settings);
 else if(page==="agentdb")await renderAgentDatabase(m);
 else if(page==="bpms")await renderBPMS(m);
 else if(page==="mysql")renderMysql(m,settings.mysql||{});
 else if(page==="company")await renderCompany(m);
 else if(page==="identity")await renderIdentity(m);
 else if(page==="processmaker")renderPm(m,settings.processmaker||{});
 else if(page==="ai")renderAI(m,settings.ai||{});
 else if(page==="license")await renderLicense(m,settings);
 else if(page==="users")await renderUsers(m);
 else await renderCompany(m);
}

function connectionItem(name,description,status,actions){
 const row=node("div","connection-card");
 const header=node("div","connection-card-head"),text=node("div","connection-info");
 append(text,node("strong","",name),node("p","hint",description));
 append(header,text,node("span","connection-pill "+(status.active?"is-active":"is-off"),status.label));
 append(row,header,actions);return row;
}
function verifyConnection(button,out,path,description){
 button.disabled=true;out.replaceChildren();
 return api(path,{}).then(()=>out.replaceChildren(info("ارتباط «"+description+"» بررسی شد.")))
  .catch(err=>showError(out,err)).finally(()=>{button.disabled=false});
}
function bpmsConnectionRow(source,returnPage){
 const actions=node("div","connection-actions"),out=node("div","full connection-feedback");
 const edit=btn("ویرایش",()=>{state.bpmsEdit=source.id;showSettings("bpms")},"secondary");
 const check=btn("بررسی",async()=>{
  check.disabled=true;out.replaceChildren();
  try{const result=await api("bpms/connections/check",{id:source.id,name:source.name,
     base_url:source.base_url,kind:source.kind,bearer_token:"",enabled:source.enabled});
   out.replaceChildren(info("اتصال معتبر است · شناسه سازمان: "+result.tenant_id))}
  catch(err){showError(out,err)}finally{check.disabled=false}
 },"secondary");
 const toggle=btn(source.enabled?"غیرفعال‌سازی":"فعال‌سازی",async()=>{
  if(source.enabled&&!confirm("دسترسی گزارش‌های «"+source.name+"» تا فعال‌سازی دوباره متوقف شود؟"))return;
  toggle.disabled=true;out.replaceChildren();
  try{await api("bpms/connections/enabled",{source_id:source.id,enabled:!source.enabled});
   await showSettings(returnPage)}catch(err){showError(out,err)}finally{toggle.disabled=false}
 },source.enabled?"secondary":"");
 const remove=btn("حذف",async()=>{
  if(!confirm("اتصال «"+source.name+"» و توکن ذخیره‌شدهٔ آن در آوان حذف شوند؟"))return;
  remove.disabled=true;out.replaceChildren();
  try{await api("bpms/connections/delete",{source_id:source.id});await showSettings(returnPage)}
  catch(err){showError(out,err)}finally{remove.disabled=false}
 },"secondary danger");
 append(actions,check,edit,toggle,remove);
 const row=connectionItem(source.name,source.base_url+" · آداپتر AVAN REST v1 · "+
    (source.has_token?"توکن ثبت‌شده":"بدون توکن"),
    {active:source.enabled,label:source.enabled?"فعال":"غیرفعال"},actions);
 append(row,out);return row;
}
async function renderConnections(m,settings){
 const p=panel("فهرست اتصال‌ها","برای هر اتصال، وضعیت پیکربندی و عملیات در دسترس را ببینید. وضعیت «تنظیم‌شده» به‌معنای آزمون زنده نیست.");
 append(m,p);
 const [dbResult,bpmsResult,identityResult]=await Promise.allSettled([
  api("agent-db/connections"),api("bpms/connections"),api("identity/status")]);
 if(state.page!=="connections")return;
 const db=dbResult.status==="fulfilled"?dbResult.value:{active_id:null,connections:[]};
 const bpms=bpmsResult.status==="fulfilled"?bpmsResult.value:{sources:[]};
 const stats=node("div","connection-stats");
 for(const [label,value] of [["منابع BPMS فعال",bpms.sources.filter(x=>x.enabled).length],
   ["بانک Agent",db.active_id?"فعال":"قطع"],["MySQL ProcessMaker",settings.mysql?.host?
    (settings.mysql.enabled===false?"غیرفعال":"فعال"):"ثبت‌نشده"]]){
  const card=node("div","connection-stat");append(card,node("small","",label),node("strong","",value));append(stats,card)}
 append(p,stats);
 if(dbResult.status==="rejected")append(p,info("دریافت فهرست بانک Agent ناموفق بود: "+dbResult.reason.message,true));
 if(bpmsResult.status==="rejected")append(p,info("دریافت منابع BPMS ناموفق بود: "+bpmsResult.reason.message,true));
 const list=node("div","connection-list");append(p,list);
 const singleton=(title,detail,configured,page,checkPath,options={})=>{
  const actions=node("div","connection-actions"),out=node("div","full connection-feedback");
  const edit=btn(configured?"به‌روزرسانی":"افزودن",()=>showSettings(page),"secondary");append(actions,edit);
  if(configured&&checkPath){const check=btn("بررسی اتصال",()=>verifyConnection(check,out,checkPath,title),"secondary");append(actions,check)}
  if(configured&&options.actions)options.actions(actions,out);
  const active=options.active===undefined?configured:options.active;
  const label=options.label||(configured?(active?"فعال":"غیرفعال"):"ثبت‌نشده");
  const row=connectionItem(title,detail,{active,label},actions);
  append(row,out);append(list,row);
 };
 singleton("ProcessMaker · MySQL",settings.mysql?.host?
  settings.mysql.host+":"+(settings.mysql.port||3306)+" · "+settings.mysql.database:
  "داده‌های فرایند از بانک Workspace خوانده می‌شوند.",!!settings.mysql?.host,"mysql","mysql/check-saved",{
   active:!!settings.mysql?.host&&settings.mysql.enabled!==false,
   actions:(actions,out)=>{
    const active=settings.mysql.enabled!==false;
    const toggle=btn(active?"غیرفعال‌سازی":"فعال‌سازی",async()=>{
     if(active&&!confirm("اتصال MySQL غیرفعال شود؟ دسترسی کاربران به داده‌های ProcessMaker تا فعال‌سازی مجدد متوقف می‌شود."))return;
     toggle.disabled=true;out.replaceChildren();
     try{await api("mysql/enabled",{enabled:!active});await showSettings("connections")}
     catch(err){showError(out,err)}finally{toggle.disabled=false}
    },active?"secondary":"");
    const remove=btn("حذف",async()=>{
     if(!confirm("تنظیمات و رمز اتصال MySQL در آوان حذف شوند؟ این کار داده‌های ProcessMaker را حذف نمی‌کند و تا ثبت دوباره اتصال، دسترسی جلسات متوقف می‌شود."))return;
     remove.disabled=true;out.replaceChildren();
     try{await api("mysql/remove",{confirmation:"REMOVE_MYSQL_SOURCE"});await showSettings("connections")}
     catch(err){showError(out,err)}finally{remove.disabled=false}
    },"secondary danger");append(actions,toggle,remove);
   }
  });
 singleton("ProcessMaker · API کاربران",settings.processmaker?.base_url?
  settings.processmaker.base_url+" · "+settings.processmaker.workspace:
  "اتصال تشخیصی API کاربران؛ داده‌های جلسه از MySQL خوانده می‌شوند.",!!settings.processmaker?.base_url,"processmaker","processmaker/check-saved",{
   label:settings.processmaker?.base_url?"تنظیم‌شده":"ثبت‌نشده",
   actions:(actions,out)=>append(actions,btn("حذف",async()=>{
    if(!confirm("تنظیمات و توکن API تشخیصی ProcessMaker از آوان حذف شوند؟ اتصال MySQL جلسات حفظ می‌شود."))return;
    try{await api("processmaker/remove",{confirmation:"REMOVE_PM_API"});await showSettings("connections")}
    catch(err){showError(out,err)}
   },"secondary danger"))
  });
 singleton("مدل هوش مصنوعی",settings.ai?.model||"مدل و کلید API از تنظیمات هوش مصنوعی تعیین می‌شوند.",
  !!settings.ai?.api_key,"ai",settings.ai?.enabled?"ai/check":null,{
   active:!!settings.ai?.enabled,
   actions:(actions,out)=>{
    const toggle=btn(settings.ai.enabled?"غیرفعال‌سازی":"فعال‌سازی",async()=>{
     toggle.disabled=true;out.replaceChildren();
     try{await api("ai/save",{enabled:!settings.ai.enabled,model:settings.ai.model||"gpt-4.1-mini",
      api_key:"",voice_enabled:!!settings.ai.voice_enabled,
      transcription_model:settings.ai.transcription_model||"gpt-4o-mini-transcribe",
      speech_model:settings.ai.speech_model||"gpt-4o-mini-tts",voice:settings.ai.voice||"alloy"});
      await showSettings("connections")}
     catch(err){showError(out,err)}finally{toggle.disabled=false}
    },settings.ai.enabled?"secondary":"");
    const remove=btn("حذف کلید",async()=>{
     if(!confirm("کلید API هوش مصنوعی حذف و دستیار غیرفعال شود؟ گفت‌وگوهای ذخیره‌شده حذف نمی‌شوند."))return;
     try{await api("ai/remove",{confirmation:"REMOVE_AI_KEY"});await showSettings("connections")}
     catch(err){showError(out,err)}
    },"secondary danger");append(actions,toggle,remove);
   }
  });
 if(identityResult.status==="fulfilled"){
  const identity=identityResult.value;
  singleton("هویت سازمانی · Keycloak",identity.connected?
   "Realm "+identity.realm+" · سرویس داخلی Docker":"سرویس هویت هنوز آماده نیست.",
   !!identity.connected,"identity",null);
 }
 const agentSection=node("section","connection-group");append(agentSection,
  node("h3","","بانک‌های اختصاصی Agent"),node("p","hint","فقط یک SQL Server هم‌زمان فعال است."));
 for(const connection of db.connections){
  const actions=node("div","connection-actions"),out=node("div","full connection-feedback");
  const check=btn("بررسی",async()=>{check.disabled=true;out.replaceChildren();
   try{await api("agent-db/connections/check",{connection_id:connection.id});out.replaceChildren(info("ساختار و حساب محدود تأیید شد."))}
   catch(err){showError(out,err)}finally{check.disabled=false}},"secondary");
  append(actions,check);
  if(!connection.managed)append(actions,btn("ویرایش",()=>{state.agentEditId=connection.id;showSettings("agentdb")},"secondary"));
  if(!connection.active)append(actions,btn("فعال‌سازی",async()=>{try{await api("agent-db/connections/activate",{connection_id:connection.id});await showSettings("connections")}catch(err){showError(out,err)}}));
  if(connection.active)append(actions,btn("قطع اتصال",async()=>{
   if(!confirm("قطع اتصال فعال، گفتگوها و گزارش‌های ذخیره‌شدهٔ Agent را تا فعال‌سازی مجدد از دسترس خارج می‌کند. ادامه می‌دهید؟"))return;
   try{await api("agent-db/connections/disconnect",{confirmation:"DISCONNECT"});await showSettings("connections")}
   catch(err){showError(out,err)}},"secondary"));
  if(!connection.managed&&!connection.active)append(actions,btn("حذف",async()=>{
   if(!confirm("پروفایل این اتصال حذف شود؟ بانک SQL Server حذف نمی‌شود."))return;
   try{await api("agent-db/connections/delete",{connection_id:connection.id});await showSettings("connections")}
   catch(err){showError(out,err)}},"secondary danger"));
  const row=connectionItem(connection.name,connection.server+" · AVANAgent"+(connection.managed?" · Docker":" · خارجی"),
   {active:connection.active,label:connection.active?"فعال":"غیرفعال"},actions);
  append(row,out);append(agentSection,row);
 }
 append(agentSection,btn("+ اتصال SQL Server خارجی",()=>{state.agentEditId="new";showSettings("agentdb")},"secondary"));append(list,agentSection);
 const bpmsSection=node("section","connection-group");append(bpmsSection,
  node("h3","","موتورهای BPMS دیگر"),node("p","hint","هر منبع جداگانه و فقط‌خواندنی است."));
 for(const source of bpms.sources)append(bpmsSection,bpmsConnectionRow(source,"connections"));
 if(!bpms.sources.length)append(bpmsSection,info("هنوز آداپتر BPMS دیگری ثبت نشده است."));
 append(bpmsSection,btn("+ افزودن BPMS",()=>{state.bpmsEdit="new";showSettings("bpms")},"secondary"));append(list,bpmsSection);
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
 if(state.authMode==="bootstrap"){
   const company=await api("company");
   const bind=panel("تکمیل ورود واحد GodAdmin",
     "پس از ثبت سازمان، با حساب سازمانی موردنظر یک‌بار وارد شوید. این حساب تا تأیید شما هیچ دسترسی ندارد؛ سپس آن را در اینجا با کد تازهٔ Authenticator به GodAdmin متصل کنید.");
   if(!company.tenant_id)append(bind,info("ابتدا در بخش اطلاعات سازمان نام سازمان را ثبت کنید.",true));
   else{
     append(bind,info("شناسه سازمانی که باید برای حساب Keycloak ثبت شده باشد: "+company.tenant_id));
     const create=node("form","grid"),created=node("div","full");
     append(create,field("نام کاربری جدید GodAdmin","username"),
       field("ایمیل حساب سازمانی","email"),field("نام مدیر سامانه","name"),
       field("رمز موقت حساب جدید (حداقل ۱۶ کاراکتر)","password","",{secret:true}),
       field("کد تازه Authenticator حساب اولیه","otp"));
     const createButton=node("button","","ساخت حساب سازمانی GodAdmin");
     createButton.type="submit";append(create,createButton,created);
     create.addEventListener("submit",async e=>{
       e.preventDefault();busy(create,true);
       try{const account=await api("identity/create-godadmin-account",{
         username:formValue(create,"username"),email:formValue(create,"email"),
         name:formValue(create,"name"),password:formValue(create,"password"),
         otp:formValue(create,"otp")});
         create.elements.namedItem("password").value="";
         created.replaceChildren(info(account.next));
       }catch(err){showError(created,err)}finally{busy(create,false)}
     });
     append(bind,info("اگر هنوز حساب سازمانی ندارید، آن را اینجا بسازید. پس از اولین ورود باید رمز موقت و تأیید دومرحله‌ای حساب جدید را تکمیل کنید."),create);
     const start=node("a","visit","ورود حساب سازمانی در پنجرهٔ جدید ←");
     start.href="/auth/login";start.target="_blank";start.rel="noopener noreferrer";
     append(bind,start,btn("به‌روزرسانی حساب‌های واردشده",()=>showSettings("identity"),"secondary"));
     const pending=(await api("users/pending")).pending||[];
     for(const account of pending.filter(u=>u.tenant_id===company.tenant_id)){
       const f=node("form"),out=node("div");
       const otp=field("کد جدید Authenticator حساب اولیه GodAdmin","otp","",{secret:false});
       append(f,node("p","",account.name+" · "+(account.email_verified?account.email||"":"ایمیل تأیید نشده")+" · "+account.subject),otp);
       const button=node("button","","تأیید این حساب به‌عنوان GodAdmin");button.type="submit";
       append(f,button,out);append(bind,f);
       f.addEventListener("submit",async e=>{
         e.preventDefault();if(!confirm("حساب «"+account.name+"» مدیر کل این نصب شود؟"))return;
         busy(f,true);
         try{await api("identity/bind-godadmin",{tenant_id:account.tenant_id,
           subject:account.subject,otp:formValue(f,"otp")});
           window.location.assign("/auth/login");
         }catch(err){showError(out,err)}finally{busy(f,false)}
       });
     }
     if(!pending.length)append(bind,info("پس از ورود حساب سازمانی، این صفحه را به‌روزرسانی کنید."));
   }
   append(m,bind);
 }
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
   append(form,helpLamp("انتخاب کاربر ProcessMaker",[helpContent.users.fields.pm_uid],true));
   const roleLabel=node("label","","نقش سازمانی");
   const roleSelect=node("select");roleSelect.name="role";
   for(const [value,label] of [["Expert","کارشناس"],["Manager","مدیر"],["SysAdmin","مدیر سیستم"]]){
     if(value==="SysAdmin" && !(account.roles||[]).includes("SysAdmin"))continue;
     const opt=node("option","",label);opt.value=value;append(roleSelect,opt);
   }
   append(roleLabel,roleSelect);
   append(form,helpLamp("نقش سازمانی",[helpContent.users.fields.role],true));
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
async function renderBPMS(m){
 const data=await api("bpms/connections");
 const section=panel("منابع فرایندی آوان",
  "ProcessMaker داخلی اتصال خواندنی جداگانه دارد. برای موتورهای دیگر، آداپتر HTTPS سازگار با AVAN REST v1 اضافه کنید؛ داده‌های آن‌ها در بانک Agent کپی نمی‌شوند.");
 append(section,info(data.processmaker_native_configured?
   "ProcessMaker داخلی تنظیم شده است. دسترسی داده‌های آن از مجوز خود کاربران ProcessMaker تبعیت می‌کند.":
   "ProcessMaker داخلی هنوز تنظیم نشده است. GodAdmin برای استفاده از دیگر BPMSها به آن نیاز ندارد."));
 const heading=node("div","section-head");append(heading,node("h3","","اتصال‌های ثبت‌شده"),
  node("span","connection-count",data.sources.length+" از ۱۲ منبع"));append(section,heading);
 for(const source of data.sources)append(section,bpmsConnectionRow(source,"bpms"));
 if(!data.sources.length)append(section,info("فعلاً BPMS دیگری ثبت نشده است. برای شروع، یک آداپتر AVAN REST v1 معرفی کنید."));
 const editor=node("div","editor-slot");
 const open=(source)=>{
  editor.replaceChildren();state.bpmsEdit=source?.id||"new";
  const p=panel(source?"ویرایش «"+source.name+"»":"افزودن BPMS جدید",
    "توکن و آدرس را از مسئول آداپتر همان BPMS بگیرید. با آدرس یکسان، توکن خالی یعنی حفظ توکن قبلی؛ برای تغییر آدرس، توکن تازه لازم است.");
  p.classList.add("connection-editor");
  const f=node("form","grid"),out=node("div","full"),actions=node("div","actions full");
  append(f,field("نام منبع","name",source?.name||""),
   field("آدرس HTTPS مبدل AVAN v1","base_url",source?.base_url||"",{placeholder:"https://bpms.example.com"}),
   field("توکن حساب فقط‌خواندنی","bearer_token","",{secret:true,required:!source}));
  const enabled=node("input");enabled.type="checkbox";enabled.checked=source?source.enabled:true;
  const toggle=node("label","checkbox-line full");append(toggle,enabled,node("span",""," پس از ذخیره فعال باشد"));append(f,toggle);
  append(f,helpLamp("فعال‌سازی منبع BPMS",[
   "اتصال فعال برای گزارش‌های همین منبع خوانده می‌شود. غیرفعال‌کردن آن را در فهرست نگه می‌دارد اما گزارش و دستیار دیگر آن را انتخاب نمی‌کنند."
  ],true));
  const body=()=>({id:source?.id||null,name:formValue(f,"name"),kind:"avan-rest-v1",
   base_url:formValue(f,"base_url"),bearer_token:formValue(f,"bearer_token"),enabled:enabled.checked});
  const check=btn("بررسی اتصال",async()=>{busy(f,true);out.replaceChildren();
   try{const result=await api("bpms/connections/check",body());out.replaceChildren(info("اتصال تأیید شد · شناسه سازمان: "+result.tenant_id))}
   catch(err){showError(out,err)}finally{busy(f,false)}},"secondary");
  const save=btn(source?"ثبت تغییرات":"ذخیره اتصال جدید",async()=>{busy(f,true);out.replaceChildren();
   try{await api("bpms/connections/save",body());f.elements.namedItem("bearer_token").value="";
    state.bpmsEdit=null;await showSettings("bpms")}
   catch(err){showError(out,err)}finally{busy(f,false)}});
  append(actions,check,save,btn("انصراف",()=>{state.bpmsEdit=null;editor.replaceChildren()},"secondary"));
  append(f,actions,out);append(p,f);append(editor,p);
  p.scrollIntoView({behavior:"smooth",block:"nearest"});
 };
 const add=btn("+ افزودن اتصال BPMS",()=>open(null));
 add.disabled=data.sources.length>=12;append(section,add,editor);append(m,section);
 if(state.bpmsEdit){const existing=data.sources.find(s=>s.id===state.bpmsEdit);
  if(existing||state.bpmsEdit==="new")open(existing||null);else state.bpmsEdit=null}
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
 if(state.agentEditId){
  const target=status.connections.find(c=>c.id===state.agentEditId);
  if(state.agentEditId==="new"||target&&!target.managed)showConnectionEditor(p,target||null);
  state.agentEditId=null;
 }
}

function showConnectionEditor(parent,current){
 const existing=parent.querySelector(".connection-editor");if(existing)existing.remove();
 const box=panel(current?"ویرایش اتصال خارجی":"اتصال خارجی جدید","حساب باید AVAN_AgentApp و بانک باید AVANAgent باشد. رمز خالی فقط هنگام ویرایش همان نشانی، رمز قبلی را حفظ می‌کند؛ برای تغییر سرور رمز تازه وارد کنید.");
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
