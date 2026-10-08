"use strict";
const $=id=>document.getElementById(id);
const topics={
 connections:{
  title:"وضعیت سامانه",lead:"این صفحه فقط Dashboard سلامت است؛ هیچ تنظیمی از اینجا تغییر نمی‌کند.",
  flow:["مشاهده وضعیت","انتخاب کارت سرویس","مدیریت در صفحه مالک تنظیم"],
  steps:[
   ["وضعیت را بخوان","کارت‌ها فقط نشان می‌دهند اتصال ثبت شده، فعال یا نیازمند بررسی است."],
   ["روی «مدیریت» بزن","هر سرویس فقط یک Owner Page دارد؛ Secretها در Dashboard ویرایش نمی‌شوند."],
   ["تست را در صفحه مالک انجام بده","نتیجه تست زنده را با وضعیت صرفاً ثبت‌شده اشتباه نگیر."]
  ],
  fields:[]
 },
 bpms:{
  title:"اتصالات BPMS",lead:"همه موتورهای فرایندی، از جمله ProcessMaker، از یک کاتالوگ اتصال مدیریت می‌شوند.",
  flow:["اتصال جدید","انتخاب نوع BPMS","ورود اطلاعات اختصاصی","تست اتصال","افزودن به لیست"],
  steps:[
   ["اتصال جدید","یک نام دلخواه انتخاب کن و نوع موتور را مشخص کن."],
   ["نوع BPMS","اگر ProcessMaker است فرم MySQL + OAuth باز می‌شود؛ برای موتورهای دیگر فرم AVAN REST v1 نمایش داده می‌شود."],
   ["تست و افزودن","اتصال فقط بعد از تست موفق ذخیره می‌شود."],
   ["مدیریت اتصال موجود","برای هر ردیف: تست، ویرایش، کپی تنظیمات، حذف و در صورت نیاز فعال‌سازی در دسترس است."],
   ["کپی امن","Secretها به Browser برنمی‌گردند؛ Clone در Backend انجام می‌شود."]
  ],
  fields:[
   ["ProcessMaker","اتصال بومی با MySQL فقط‌خواندنی + OAuth API."],
   ["Camunda / Appian / UiPath / ServiceNow / سایر","از آداپتر HTTPS مطابق قرارداد AVAN REST v1 استفاده می‌کنند."]
  ]
 },
 userbpms:{
  title:"اتصال کاربران به BPMS",lead:"هویت AVAN مستقل از BPMS می‌ماند؛ این صفحه فقط حساب متناظر هر کاربر را در هر اتصال فرایندی ثبت می‌کند.",
  flow:["انتخاب کاربر AVAN","انتخاب BPMS","ورود username همان کاربر در BPMS","تأیید اتصال","بررسی یا قطع اتصال"],
  steps:[
   ["کاربر AVAN","کاربری را انتخاب کن که قبلاً در AVAN ایجاد و فعال شده است."],
   ["BPMS","یکی از اتصال‌های فعال ProcessMaker/BPMS را انتخاب کن."],
   ["Username BPMS","نام کاربری دقیق همان شخص را در BPMS وارد کن؛ AVAN آن را در Directory همان اتصال بررسی می‌کند."],
   ["پیشنهادها","پیشنهادهای username، email یا نام فقط راهنما هستند و بدون تأیید مدیر اتصال ایجاد نمی‌کنند."],
   ["اتصال","فقط کاربر فعال BPMS قابل اتصال است و یک حساب BPMS در هر Source نمی‌تواند هم‌زمان به دو کاربر AVAN متصل شود."],
   ["قطع اتصال","قطع Binding فقط ارتباط AVAN↔BPMS را حذف می‌کند؛ کاربر و سوابق فرایندی در ProcessMaker حذف نمی‌شوند."]
  ],
  fields:[
   ["کاربر AVAN","هویت داخلی AVAN؛ مستقل از حساب BPMS."],
   ["BPMS / ProcessMaker","اتصال فرایندی که Directory کاربر از آن خوانده می‌شود."],
   ["نام کاربری BPMS","username دقیق حساب همان شخص در آن BPMS."]
  ]
 },
 "bpms-processmaker":{
  title:"اتصال ProcessMaker",lead:"اتصال بومی ProcessMaker دو کانال دارد: MySQL برای خواندن داده فرایند و OAuth API برای Directory/Identity.",
  flow:["ساخت کاربر MySQL فقط‌خواندنی","ساخت OAuth Application","ورود اطلاعات در آوان","تست MySQL","دریافت و تست Token","ذخیره و Refresh خودکار"],
  steps:[
   ["MySQL Read-Only","در ProcessMaker/MySQL یک حساب فقط SELECT بساز. برای نصب محلی Host از دید Docker معمولاً host.docker.internal و Port معمولاً 3306 است."],
   ["OAuth Application","در ProcessMaker 3.x به OAuth2 Applications برو و Client ID و Client Secret بساز/بردار."],
   ["فرم آوان","Host/Port/Database/User/Password MySQL و Base URL/Workspace/Client ID/Client Secret/Username/Password ProcessMaker را وارد کن."],
   ["تست و افزودن","آوان MySQL را بررسی می‌کند، خودش Password Grant را به /{workspace}/oauth2/token می‌فرستد و سپس GET کاربران را تست می‌کند."],
   ["ذخیره امن","Password حساب ProcessMaker ذخیره نمی‌شود. Client Secret، Access Token و Refresh Token داخل Store رمزگذاری‌شده آوان ذخیره می‌شوند."],
   ["تمدید","پیش از انقضای Access Token، Refresh Token برای تمدید استفاده و Refresh Token جدید جایگزین قبلی می‌شود."]
  ],
  fields:[
   ["MySQL Host","برای ProcessMaker همین ویندوز: معمولاً host.docker.internal."],
   ["Database","در نصب فعلی معمولاً bitnami_pm."],
   ["Workspace","در نصب فعلی workflow."],
   ["Base URL API","از داخل Docker معمولاً http://host.docker.internal:84 در محیط آزمایشی."],
   ["OAuth2 Applications","روی Host معمولاً http://127.0.0.1:84/sysworkflow/en/neoclassic/oauth2/applications"],
   ["Password ProcessMaker","فقط برای ساخت Token استفاده می‌شود و ذخیره نمی‌شود."]
  ]
 },
 "bpms-adapter":{
  title:"اتصال BPMS با AVAN REST v1",lead:"برای موتورهای غیر-ProcessMaker یک آداپتر فقط‌خواندنی HTTPS بین آوان و موتور BPMS قرار می‌گیرد.",
  flow:["آماده‌سازی Adapter","ساخت Integration Token","ثبت Base URL","تست Identity","تست BI","ذخیره"],
  steps:[
   ["آداپتر","آداپتر باید قرارداد AVAN REST v1 را پیاده کند و داده را فقط بخواند."],
   ["Identity","GET /avan/v1/identity باید tenant_id همین سازمان را برگرداند."],
   ["BI","GET /avan/v1/bi/processes باید پاسخ استاندارد آوان را برگرداند."],
   ["Token","یک Bearer Token اختصاصی فقط‌خواندنی بساز؛ Token را در URL قرار نده."],
   ["تست و افزودن","آوان قبل از ذخیره Identity و Tenant را بررسی می‌کند."]
  ],
  fields:[["Base URL","HTTPS، بدون Username/Password در URL."],["Bearer Token","توکن integration فقط‌خواندنی."],["Engine","نوع موتور برای نمایش و انتخاب Adapter مناسب."]]
 },
 agentdb:{
  title:"بانک Agent",lead:"بانک اختصاصی Agent مستقل از دیتابیس عملیاتی BPMS است.",
  flow:["SQL داخلی Docker یا خارجی","تست ساختار","ثبت پروفایل","فعال‌سازی یک اتصال"],
  steps:[
   ["SQL داخلی","در نصب استاندارد Docker خودکار ساخته می‌شود."],
   ["SQL خارجی","با حساب نصب بانک AVANAgent را ایجاد کن؛ رمز حساب مدیر ذخیره نمی‌شود."],
   ["حساب Runtime","آوان با حساب محدود AVAN_AgentApp کار می‌کند."],
   ["فعال‌سازی","فقط یک پروفایل بانک Agent هم‌زمان Active است."]
  ],
  fields:[["Server","server,port از دید کانتینر."],["AVAN_AgentApp","حساب محدود Runtime."],["TLS","برای Production گواهی معتبر توصیه می‌شود."]]
 },
 ai:{
  title:"هوش مصنوعی",lead:"تنظیم Provider/Model و قابلیت‌های صوتی دستیار آوان.",
  flow:["دریافت API Key","انتخاب مدل","ذخیره Secret","تست دسترسی مدل","فعال‌سازی"],
  steps:[
   ["API Key","کلید را فقط از حساب رسمی Provider بگیر و در چت یا URL قرار نده."],
   ["مدل","شناسه مدلی را انتخاب کن که همان API Key واقعاً به آن دسترسی دارد."],
   ["صوت","Transcription و TTS را فقط در صورت نیاز فعال کن؛ مصرف جداگانه دارند."],
   ["تست","پس از ذخیره، «بررسی اتصال ذخیره‌شده» را اجرا کن."]
  ],
  fields:[["API Key","پس از ذخیره دوباره به Browser نمایش داده نمی‌شود."],["Model","مدل مجاز حساب API."],["Voice","صدای TTS پشتیبانی‌شده."]]
 },
 "organization-company":{
  title:"اطلاعات سازمان",lead:"هویت Tenant سازمان از این بخش تعریف می‌شود.",
  flow:["نام رسمی سازمان","ساخت Tenant ID","استفاده در Identity و License"],
  steps:[
   ["نام رسمی","نام را مطابق قرارداد/لایسنس ثبت کن."],
   ["Tenant ID","در اولین ذخیره توسط آوان ساخته و ثابت می‌شود."],
   ["همسانی","همین Tenant ID باید در هویت، لایسنس و Adapterهای BPMS استفاده شود."]
  ],fields:[]
 },
 "organization-identity":{
  title:"هویت و ورود",lead:"Keycloak داخلی آوان مسئول حساب سازمانی، OIDC و MFA است.",
  flow:["Keycloak داخلی","ساخت/ورود حساب سازمانی","MFA","Bind GodAdmin"],
  steps:[
   ["زیرساخت","Keycloak همراه Docker آوان راه‌اندازی می‌شود."],
   ["GodAdmin","حساب سازمانی را بساز/وارد شو و MFA را کامل کن."],
   ["Bind","پس از ورود تأییدشده، همان Subject به عنوان GodAdmin این نصب Bind می‌شود."],
   ["امنیت","Client Secretهای داخلی توسط Docker Secret مدیریت می‌شوند."]
  ],fields:[]
 },
 "organization-users":{
  title:"کاربران و دسترسی",lead:"دسترسی سازمانی از Identity + Mapping + License تشکیل می‌شود.",
  flow:["ورود کاربر","تأیید Identity","تطبیق کاربر BPMS","انتخاب نقش","کنترل License","فعال‌سازی"],
  steps:[
   ["درخواست","کاربر ابتدا با هویت سازمانی وارد می‌شود."],
   ["Mapping","برای ProcessMaker، کاربر فعال Directory با هویت سازمانی تطبیق داده می‌شود."],
   ["Role","نقش و واحد سازمانی را براساس مجوز واقعی انتخاب کن."],
   ["License","فعال‌سازی نهایی باید ظرفیت لایسنس را رعایت کند."]
  ],fields:[]
 },
 appearance:{
  title:"ویرایشگر کامل ظاهر Login",lead:"Scene Editor V4 کنترل کامل Background، Globe، Orbit، Hover و هر Node را بدون تغییر منطق امنیتی Login در اختیار GodAdmin می‌گذارد.",
  flow:["انتخاب Background","تنظیم Crop و نور","تنظیم Globe","تنظیم Orbit و Hover","ویرایش تک‌تک Nodeها","ذخیره امن","همگام‌سازی با Keycloak"],
  steps:[
   ["Background","PNG/JPG/WebP را انتخاب کن. Browser تصویر را حداکثر تا ۱۹۲۰×۱۰۸۰ به WebP تبدیل می‌کند. Fit، موقعیت X/Y، Brightness، Contrast، Saturation، Blur، Dark Layer، Overlay Color/Opacity و Parallax مستقل هستند."],
   ["Globe","کره از Background جداست. می‌توانی Sprite پیش‌فرض آوان را نگه داری یا تصویر کره خودت را بدهی؛ X/Y، Scale، Opacity، Brightness، Contrast، Saturation، Hue، Glow و Wobble مستقل‌اند."],
   ["شبکه کره","Rotation Speed، تراکم نقاط، اندازه نقاط و Opacity نقاط Canvas قابل تنظیم‌اند؛ این تنظیمات روی تصویر کره اعمال نمی‌شوند و لایه شبکه را جدا کنترل می‌کنند."],
   ["Orbit","سرعت کلی حرکت، ضخامت و Opacity خطوط، Glow و دو رنگ اصلی/ثانویه Orbit قابل تنظیم‌اند. نمایش خطوط Orbit را هم می‌توان خاموش کرد بدون اینکه Nodeها متوقف شوند."],
   ["Hover","Mode می‌تواند Card، Tooltip، Label، Glow یا None باشد. Scale و Duration سراسری تعریف می‌شوند و هر Node می‌تواند Scale اختصاصی داشته باشد."],
   ["Node مستقل","برای هر Node: فعال/غیرفعال، ترتیب، عنوان، Subtitle، Description، Tags، SVG، Accent Color، Size، Hover Scale، Glow، Opacity، Radius، Ellipse، Start Angle، Speed/Direction، Card Side و Label Mode مستقل است."],
   ["جهت حرکت","Speed مثبت و منفی جهت حرکت را تعیین می‌کند؛ عدد صفر Node را روی موقعیت فعلی ثابت می‌کند. Orbit Speed سراسری نیز روی همه Speedها ضرب می‌شود."],
   ["Card Side","Auto بسته به محل Node سمت مناسب را انتخاب می‌کند؛ Left/Right/Top/Bottom برای طراحی ثابت قابل اجبار است."],
   ["SVG امن","فایل SVG یا کد SVG پذیرفته می‌شود ولی Preview خام قبل از Sanitise اجرا نمی‌شود. Backend فقط تگ‌ها و Attributeهای گرافیکی مجاز را نگه می‌دارد."],
   ["Persistence","تنظیمات در Store رمزگذاری‌شده آوان ذخیره و نسخه Sanitised عمومی در Volume avan-ui منتشر می‌شود تا Keycloak همان ظاهر را بخواند."]
  ],
  fields:[
   ["Background Fit","cover / contain / stretch / auto"],
   ["Background X/Y","۰ تا ۱۰۰ درصد؛ محل کانون تصویر داخل صفحه."],
   ["Blur","۰ تا ۲۰px؛ برای تصویر مرجع بهتر است معمولاً ۰ تا ۲ بماند."],
   ["Parallax","۰ تا ۳۰px؛ میزان حرکت آرام Background با Mouse."],
   ["Globe X/Y","محل مرکز کره در صفحه؛ پیش‌فرض نزدیک سمت چپ است."],
   ["Globe Scale","۰٫۵۵ تا ۱٫۸۵ برابر."],
   ["Globe Hue","از ‎-۱۸۰ تا +۱۸۰ درجه برای تغییر تون رنگ."],
   ["Point Density","۰٫۵ تا ۲٫۵؛ هرچه بیشتر، نقاط Canvas متراکم‌تر و بار GPU بیشتر."],
   ["Node Size","۴۰ تا ۱۱۰px؛ مقدار اختصاصی هر Node اگر ۰ باشد از Default استفاده می‌کند."],
   ["Hover Scale","۱ تا ۱٫۸ سراسری؛ Override هر Node تا ۱٫۸۵."],
   ["Radius","فاصله Node از مرکز کره؛ حدود ۰٫۷۵ تا ۱٫۹۵."],
   ["Ellipse","کشیدگی عمودی مسیر؛ ۱ دایره و مقدار کمتر Orbit تخت‌تر."],
   ["Angle","زاویه شروع بر حسب رادیان."],
   ["Speed","از ‎-0.001 تا +0.001؛ علامت جهت و قدرمطلق سرعت را مشخص می‌کند."],
   ["Card Width","۱۲۰ تا ۳۲۰px."],
   ["SVG","حداکثر ۵۰۰۰ کاراکتر؛ script/event/href و عناصر غیرمجاز حذف یا رد می‌شوند."],
   ["Tags","حداکثر ۸ Tag، هرکدام حداکثر ۳۰ کاراکتر."]
  ]
 },
 license:{
  title:"لایسنس",lead:"مجوز فروش آوان به Installation ID و Tenant ID مشخص وابسته است.",
  flow:["Installation ID","Tenant ID","دریافت License امضاشده","اعتبارسنجی Public Key","فعال‌سازی"],
  steps:[
   ["شناسه‌ها","Installation ID و Tenant ID را برای صادرکننده لایسنس ارسال کن."],
   ["کلید عمومی","فقط Public Key ناشر روی نصب قرار می‌گیرد؛ Private Key هرگز وارد آوان نمی‌شود."],
   ["توکن لایسنس","توکن امضاشده را بدون تغییر Paste و فعال کن."],
   ["ظرفیت","تاریخ، ماژول‌ها و تعداد کاربران در هر فعال‌سازی کنترل می‌شوند."]
  ],fields:[]
 }
};

function el(tag,cls,text){const n=document.createElement(tag);if(cls)n.className=cls;if(text!==undefined)n.textContent=text;return n}
function render(topic){
 const data=topics[topic]||topics.connections,root=$("help-root");root.replaceChildren();
 const hero=el("section","help-hero");hero.append(el("span","eyebrow","AVAN · GUIDE"),el("h1","",data.title),el("p","",data.lead));root.append(hero);
 const flow=el("section","help-card");flow.append(el("h2","","نقشه مسیر"));
 const rail=el("div","flow-rail");
 data.flow.forEach((step,i)=>{const box=el("div","flow-node");box.append(el("span","flow-index",String(i+1)),el("strong","",step));rail.append(box);if(i<data.flow.length-1)rail.append(el("span","flow-arrow","←"))});
 flow.append(rail);root.append(flow);
 const steps=el("section","help-card");steps.append(el("h2","","آموزش مرحله‌به‌مرحله"));
 const list=el("div","step-list");
 data.steps.forEach((item,i)=>{const row=el("article","step-card");row.append(el("span","step-number",String(i+1)),el("div","step-copy"));row.querySelector(".step-copy").append(el("h3","",item[0]),el("p","",item[1]));list.append(row)});
 steps.append(list);root.append(steps);
 if(data.fields?.length){
  const fields=el("section","help-card");fields.append(el("h2","","مقادیر و محل تهیه"));
  const table=el("div","field-grid");data.fields.forEach(([name,desc])=>{const row=el("div","field-row");row.append(el("code","",name),el("p","",desc));table.append(row)});fields.append(table);root.append(fields);
 }
 const safety=el("section","help-card safety");safety.append(el("h2","","قاعده امنیتی آوان"),el("p","","Secret، Password و Token پس از ذخیره دوباره به Browser برگردانده نمی‌شوند. برای «کپی تنظیمات»، Clone در Backend انجام می‌شود تا Secret افشا نشود."));root.append(safety);
 document.title="آوان | "+data.title;
}
document.addEventListener("DOMContentLoaded",()=>{
 $("close-help").addEventListener("click",()=>window.close());
 const topic=new URLSearchParams(location.search).get("topic")||"connections";
 render(topic);
});