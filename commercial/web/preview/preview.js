"use strict";
/* Visual-only, loopback, synthetic dataset preview. No API tokens or DB credentials.
   ALL text from dataset is inserted using textContent, never untrusted innerHTML.
   The simulated module toggles DO NOT issue/revoke a commercial license.
*/
const state = {
  cases: [], tab: "overview", selectedId: 910002, query: "", domain: "all",
  status: "all", modules: {1:true, 2:true, 3:false, 4:true}
};
const labels = {
  overview: "نمای کلی", meetings: "جلسات و مصوبات", assistant: "دستیار مدیریتی",
  secretary: "دبیر هوشمند", analytics: "تحلیل و گزارش", monitoring: "هشدار و پیگیری",
  modules: "مدیریت ماژول‌ها", sysadmin: "نمونه SysAdmin",
  godadmin: "نمونه GodAdmin"
};
const names = {2:"دبیر هوشمند جلسه",3:"تحلیل و گزارش مدیریتی",4:"هشدار و پیگیری اقدامات"};
const descriptions = {
  2:"آماده‌سازی دستور جلسه، مطالعه سوابق و نمایش اقدامات برای بازبینی دبیر.",
  3:"نمایش شاخص‌ها، تحلیل وضعیت جلسات و آمار اقدامات باز و تأخیردار.",
  4:"شناسایی اقدامات با موعد گذشته و نمایش موارد نیازمند پیگیری."
};
const statuses = {
  Closed:["مختومه","good"],InProgress:["در حال اجرا","purple"],
  Delayed:["دارای تأخیر","bad"],Planned:["برنامه‌ریزی‌شده","warn"]
};
const $ = id => document.getElementById(id);
function node(tag, cls="", content) {
  const e = document.createElement(tag);
  if (cls) e.className = cls;
  if (content !== undefined && content !== null) e.textContent = String(content);
  return e;
}
function add(parent,...children) {children.flat(Infinity).filter(x=>x!==null&&x!==undefined).forEach(c=>parent.append(c));return parent;}
function action(label,fn,cls="button") {const b=node("button",cls,label);b.type="button";b.addEventListener("click",fn);return b;}
function section(label,value) {const a=node("div","detail-group");add(a,node("h3","",label),node("p","",value));return a;}
function status(code) {
  const pair=statuses[code]||[code,""];return node("span","badge "+pair[1],pair[0]);
}
function fmtDate(value) {
  if(!value)return "—";
  const d=new Date(value);return Number.isNaN(d.getTime())?"—":
    new Intl.DateTimeFormat("fa-IR",{dateStyle:"medium",timeZone:"UTC"}).format(d);
}
function sumActions(cases) {return cases.flatMap(c=>c.actions.map(a=>({...a,meeting:c})))}
function isLate(a) {return !a.is_closed&&a.progress_percent<100&&new Date(a.due_at_utc).getTime()<Date.now()}
function numeric(value){return new Intl.NumberFormat("fa-IR").format(value)}
function toast(text) {const t=$("toast");t.textContent=text;t.hidden=false;clearTimeout(toast.timer);toast.timer=setTimeout(()=>t.hidden=true,3500)}
function showTab(tab) {
  if(!Object.hasOwn(labels,tab))return;
  state.tab=tab;
  $("breadcrumb").textContent=labels[tab];
  document.querySelectorAll(".nav-item").forEach(b=>{
    const active=b.dataset.tab===tab;b.classList.toggle("active",active);
    if(active)b.setAttribute("aria-current","page");else b.removeAttribute("aria-current");
  });
  document.querySelector(".sidebar").classList.remove("open");
  $("menu-toggle").setAttribute("aria-expanded","false");
  render();window.scrollTo({top:0,behavior:"instant"});
}
function heading(parent,kicker,title,description,buttons=[]) {
  const wrapper=node("div","page-heading");
  const head=node("div");
  add(head,node("span","eyebrow",kicker),node("h1","",title),node("p","",description));
  add(wrapper,head);
  if(buttons.length)add(wrapper,add(node("div","flex"),...buttons));add(parent,wrapper);
}
function notice(parent,txt="این اطلاعات فقط برای نمایش ظاهر و جریان محصول هستند؛ هیچ داده واقعی، خرید، ورود یا تغییر در ProcessMaker انجام نمی‌شود.") {
  add(parent,node("div","status-banner",txt));
}
function stat(label,value,foot,icon,variant="") {
  const card=node("div","stat "+variant);
  const top=node("div","stat-top");add(top,node("span","stat-label",label),node("span","stat-icon",icon));
  add(card,top,node("strong","number",numeric(value)),node("small","",foot));return card;
}
function box(title,sub) {
  const c=node("section","panel");const h=node("div","panel-header");add(h,node("h2","",title),node("small","",sub||""));add(c,h);return c;
}
function allStats(){
  const a=sumActions(state.cases);return {
    meetings:state.cases.length,actions:a.length,
    open:a.filter(x=>!x.is_closed&&x.progress_percent<100).length,
    overdue:a.filter(isLate).length
  };
}
function hero(parent){
  const e=node("div","hero");
  add(e,node("span","eyebrow","AVAN · INTELLIGENT MEETINGS"),
    node("h1","","از صورت‌جلسه تا تصمیم، در یک نمای مدیریتی"),
    node("p","","جلسات، مصوبات، اقدامات و پیگیری‌ها را در یک فضای واحد ببینید. این نسخه، پیش‌نمایش مستقل با ۱۰۰ سناریوی کاملاً ساختگی صنعت خودرو است."));
  add(e,action("مشاهده جلسات",()=>showTab("meetings"),"button"),node("span","chip","◌ نسخه نمایشی · بدون اتصال عملیاتی"));
  add(parent,e);
}
function miniMeetings(parent,amount=5){
  const p=box("جلسات اخیر در نمونه","برای دیدن جزئیات روی هر جلسه بزنید");
  state.cases.slice().reverse().slice(0,amount).forEach(c=>{
    const row=node("div","list-row clickable"),label=node("div");
    add(label,node("strong","",c.title),node("small","",c.meeting_no+" · "+c.domain));
    add(row,label,status(c.meeting_status));
    row.tabIndex=0;row.setAttribute("role","button");
    row.addEventListener("click",()=>{state.selectedId=c.meeting_id;showTab("meetings")});
    row.addEventListener("keydown",e=>{if(e.key==="Enter"||e.key===" "){e.preventDefault();row.click()}});
    add(p,row);
  });add(parent,p);
}
function bars(parent,title,counts,max=8) {
  const p=box(title,"۱۰ حوزه فعالیت ساختگی");
  const entries=Object.entries(counts).sort((a,b)=>b[1]-a[1]).slice(0,max);
  const cap=Math.max(1,...entries.map(e=>e[1]));
  const wrap=node("div","bars");
  entries.forEach(([name,n])=>{
    const line=node("div","bar-row"),head=node("div","bar-head");
    add(head,node("span","",name),node("strong","",numeric(n)));
    const bg=node("div","bar-bg"),fill=node("span","bar-fill");
    fill.style.width=(n/cap*100).toFixed(0)+"%";
    add(bg,fill);add(line,head,bg);add(wrap,line);
  });add(p,wrap);add(parent,p);
}
function countBy(cases,key){const result={};cases.forEach(c=>{const k=c[key];result[k]=(result[k]||0)+1});return result}
function overview(main) {
  heading(main,"داشبورد مدیریتی","سلام، به آوان خوش آمدید","نمای یکپارچه جلسات و اقدامات در مجموعه ساختگی خودروآزما.",[
    action("گزارش اقدامات",()=>showTab("monitoring"),"button secondary"),
    action("پرسش از دستیار",()=>showTab("assistant"))
  ]);
  notice(main);hero(main);
  const s=allStats(),stats=node("div","stats");
  add(stats,stat("کل جلسات نمونه",s.meetings,"در ۱۰ حوزه خودرویی","▤"),
    stat("اقدامات تعریف‌شده",s.actions,"۳ اقدام در هر جلسه","✓","purple"),
    stat("اقدامات باز",s.open,"بر اساس داده ساختگی","◷","teal"),
    stat("اقدامات با موعد گذشته",s.overdue,"تا تاریخ سیستم شما","!","amber"));
  add(main,stats);
  const grid=node("div","grid-2"),left=node("div"),right=node("div");
  miniMeetings(left);bars(right,"توزیع جلسات بر اساس حوزه",countBy(state.cases,"domain"),6);
  add(grid,left,right);add(main,grid);
}
function filtered(){
  const term=state.query.trim().toLocaleLowerCase("fa");
  return state.cases.filter(c=>
    (state.domain==="all"||c.domain===state.domain)&&
    (state.status==="all"||c.meeting_status===state.status)&&
    (!term||[c.title,c.meeting_no,c.domain,c.resolution].join(" ").toLocaleLowerCase("fa").includes(term))
  );
}
function selectBox(choices,value,onchange,placeholder){
  const s=node("select","select");s.setAttribute("aria-label",placeholder);
  choices.forEach(([key,label])=>{const option=node("option","",label);option.value=key;option.selected=key===value;add(s,option)});
  s.addEventListener("change",()=>onchange(s.value));return s;
}
function meetingTable(parent,cases){
  const panel=box("فهرست جلسات",numeric(cases.length)+" مورد از داده ساختگی");
  const wrap=node("div","table-wrap"),table=node("table","table");
  const thead=node("thead"),tr=node("tr");
  ["شماره جلسه","موضوع","حوزه","زمان","وضعیت","جزئیات"].forEach(x=>add(tr,node("th","",x)));
  add(thead,tr);add(table,thead);
  const body=node("tbody");cases.forEach(c=>{
    const row=node("tr");add(row,node("td","number",c.meeting_no));
    const title=node("td");add(title,node("strong","",c.title),node("small","",c.scenario_id));add(row,title);
    add(row,node("td","",c.domain),node("td","",fmtDate(c.meeting_date_utc)),add(node("td"),status(c.meeting_status)));
    const cell=node("td");add(cell,action("مشاهده",()=>{state.selectedId=c.meeting_id;render()},"text-link"));add(row,cell);
    add(body,row);
  });add(table,body);add(wrap,table);
  if(!cases.length)add(panel,node("div","empty","جلسه‌ای با فیلترهای انتخاب‌شده پیدا نشد."));
  else add(panel,wrap);add(parent,panel);
}
function detail(main,c){
  if(!c)return;
  const panel=box("پرونده جلسه · "+c.meeting_no,"نمای کامل سناریوی کاملاً ساختگی");
  const header=node("div","flex");
  add(header,node("strong","content-title",c.title),status(c.meeting_status),
    action("آماده‌سازی توسط دبیر",()=>showTab("secretary"),"button secondary"));
  add(panel,header);
  const meta=node("div","pill-list");[c.domain,fmtDate(c.meeting_date_utc),"رئیس: "+c.chair].forEach(x=>add(meta,node("span","",x)));add(panel,meta);
  add(panel,section("درخواست اولیه",c.initial_request),
    section("خلاصه مباحث",c.discussion),
    section("مصوبه",c.resolution),
    section("ریسک ثبت‌شده در سناریو",c.risk));
  const sec=node("div","detail-group");add(sec,node("h3","","اقدامات این جلسه"));
  c.actions.forEach(a=>add(sec,actionItem(a)));add(panel,sec);
  add(panel,section("نظر دبیر",c.secretary_followup),
    section("پیشنهاد جلسه بعد",c.next_meeting_topic));add(main,panel);
}
function actionItem(a){
  const d=node("div","action-item");
  add(d,node("strong","",a.action_no+" — "+a.description),
    node("small","",a.owner_unit+" · مهلت: "+fmtDate(a.due_at_utc)));
  const foot=node("div","flex");
  add(foot,node("span","badge "+(a.is_closed?"good":isLate(a)?"bad":"warn"),
       a.is_closed?"تکمیل‌شده":isLate(a)?"گذشته از موعد":"در جریان"),
    node("small","",numeric(a.progress_percent)+"٪ پیشرفت"));
  add(d,foot);const p=node("div","progress"),fill=node("span");fill.style.width=a.progress_percent+"%";
  add(p,fill);add(d,p);return d;
}
function meetings(main){
  heading(main,"WORKSPACE / MEETINGS","جلسات و مصوبات","جست‌وجو، فیلتر و بررسی ۱۰۰ سناریوی آزمایشی صنعت خودرو.");
  notice(main);
  const toolbar=node("div","toolbar"),search=node("input","search");
  search.type="search";search.placeholder="عنوان، مصوبه یا شماره جلسه...";search.value=state.query;
  search.setAttribute("aria-label","جست‌وجوی جلسات");
  // Keep input focus while filtering: update only the results and detail.
  let timer=null;search.addEventListener("input",()=>{state.query=search.value;clearTimeout(timer);timer=setTimeout(updateMeetingResults,120)});
  const domains=[["all","تمام حوزه‌ها"],...new Set(state.cases.map(c=>c.domain))].map(x=>Array.isArray(x)?x:[x,x]);
  add(toolbar,search,selectBox(domains,state.domain,v=>{state.domain=v;updateMeetingResults()},"فیلتر حوزه"),
    selectBox([["all","تمام وضعیت‌ها"],...Object.entries(statuses).map(([k,v])=>[k,v[0]])],
              state.status,v=>{state.status=v;updateMeetingResults()},"فیلتر وضعیت"));
  add(main,toolbar);
  add(main,node("div","",undefined));const results=node("div");results.id="meeting-results";add(main,results);
  updateMeetingResults();
}
function updateMeetingResults(){
  const target=$("meeting-results");if(!target)return;
  target.replaceChildren();meetingTable(target,filtered());
  detail(target,state.cases.find(c=>c.meeting_id===state.selectedId));
}
function locked(main,code){
  const c=node("div","locked");add(c,node("span","locked-icon","◈"),
    node("h2","",names[code]+" غیرفعال است"),
    node("p","","در این پیش‌نمایش، ماژول "+numeric(code)+" به‌صورت موقت خاموش شده است. در محصول واقعی فقط مدیر سازمانِ دارای مجوز معتبر می‌تواند آن را فعال کند."),
    action("رفتن به مدیریت ماژول‌ها",()=>showTab("modules")));add(main,c);
}
function secretary(main){
  heading(main,"MODULE 02 / SECRETARY","دبیر هوشمند جلسه","پیش‌نویس دستور جلسه، اقدامات و پیگیری‌ها؛ بدون ثبت یا تغییر در ProcessMaker.");
  notice(main);if(!state.modules[2])return locked(main,2);
  const toolbar=node("div","toolbar");
  const c=state.cases.find(c=>c.meeting_id===state.selectedId)||state.cases[0];
  const picker=selectBox(state.cases.map(x=>[String(x.meeting_id),x.meeting_no+" · "+x.title]),
      String(c.meeting_id),v=>{state.selectedId=Number(v);render()},"جلسه مورد بررسی");
  picker.classList.add("search");add(toolbar,picker);add(main,toolbar);
  const grid=node("div","grid-2"),left=box("پیش‌نویس دستور جلسه",c.meeting_no),right=box("سوابق و اطلاعات همراه",c.domain);
  c.preparation.agenda.forEach((a,i)=>add(left,section("موضوع "+numeric(i+1),a)));
  add(left,section("پیشنهاد جلسه بعد",c.next_meeting_topic),
    node("p","note","این موارد از سناریوی ساختگی خوانده شده‌اند؛ استخراج خودکار صوت و ثبت در ProcessMaker انجام نمی‌شود."));
  add(right,section("درخواست اولیه",c.initial_request),
    section("مرور پیشینه",c.preparation.prior_meeting_review),
    section("مصوبه ثبت‌شده",c.resolution),section("پیگیری دبیر",c.secretary_followup));
  add(grid,left,right);add(main,grid);
  const actions=box("اقدامات جهت پیگیری","بر مبنای پرونده سناریوی نمونه");
  c.actions.forEach(a=>add(actions,actionItem(a)));add(main,actions);
}
function analytics(main){
  heading(main,"MODULE 03 / ANALYTICS","گزارش و تحلیل مدیریتی","وضعیت جلسات و اقدامات بر اساس ۱۰۰ پرونده ساختگی.");
  notice(main);if(!state.modules[3])return locked(main,3);
  const s=allStats(),cards=node("div","stats");
  add(cards,stat("جلسات",s.meetings,"مجموع داده‌های ساختگی","▤"),
    stat("اقدامات",s.actions,"سه مورد به‌ازای هر جلسه","✓","purple"),
    stat("باز",s.open,"پیشرفت کمتر از ۱۰۰٪ و بسته‌نشده","◷","teal"),
    stat("تأخیردار",s.overdue,"تا تاریخ جاری دستگاه","!","amber"));
  add(main,cards);
  const grid=node("div","grid-2"),left=node("div"),right=node("div");
  const counts=countBy(state.cases,"meeting_status"),translated={};
  Object.entries(counts).forEach(([key,count])=>translated[statuses[key]?.[0]||key]=count);
  bars(left,"ترکیب وضعیت جلسات",translated,4);bars(right,"تعداد جلسات به تفکیک حوزه",countBy(state.cases,"domain"),10);
  add(grid,left,right);add(main,grid);
  const p=box("قابل استناد در این پیش‌نمایش","فقط داده نمونه");
  add(p,node("p","content-text","تمام ارقام از ۱۰۰ سناریوی ساختگی بارگذاری‌شده محاسبه شده‌اند؛ این پنل به دیتابیس واقعی سازمان یا گزارش مالی متصل نیست."));add(main,p);
}
function monitoring(main){
  heading(main,"MODULE 04 / MONITORING","هشدار و پیگیری اقدامات","فهرست اقدامات باز با موعد گذشته بر اساس ساعت دستگاه.");
  notice(main);if(!state.modules[4])return locked(main,4);
  const late=sumActions(state.cases).filter(isLate)
    .sort((a,b)=>new Date(a.due_at_utc)-new Date(b.due_at_utc));
  const bar=node("div","stats");add(bar,
    stat("اقدامات تأخیردار",late.length,"فقط داده‌های ساختگی","!","amber"),
    stat("جلسات دارای تأخیر",new Set(late.map(x=>x.meeting.meeting_id)).size,"در نمونه موجود","▤"),
    stat("اقدامات باز",allStats().open,"از ۳۰۰ اقدام","◷","purple"),
    stat("اعلان ارسالی",0,"ارسال پیامک/ایمیل پیاده‌سازی نشده","✉","teal"));
  add(main,bar);
  const p=box("موارد دارای موعد گذشته",numeric(late.length)+" اقدام نمونه");
  late.slice(0,50).forEach(a=>{
    const row=node("div","list-row"),d=node("div");
    add(d,node("strong","",a.action_no+" · "+a.description),
      node("small","",a.meeting.meeting_no+" · "+a.owner_unit+" · موعد "+fmtDate(a.due_at_utc)));
    const side=node("div","flex");add(side,node("span","badge bad",numeric(a.progress_percent)+"٪"),
      action("پرونده جلسه",()=>{state.selectedId=a.meeting.meeting_id;showTab("meetings")},"text-link"));
    add(row,d,side);add(p,row);
  });
  if(!late.length)add(p,node("div","empty","در سناریوهای نمونه اقدامی با موعد گذشته پیدا نشد."));
  if(late.length>50)add(p,node("p","note","برای خوانایی فقط ۵۰ ردیف نخست نمایش داده شده است."));
  add(main,p);
}
function modules(main){
  heading(main,"PRODUCT / MODULES","مدیریت ماژول‌ها","سوییچ‌ها در این صفحه فقط وضعیت نمایشی را تغییر می‌دهند؛ هیچ خرید یا تغییر SQL انجام نمی‌شود.");
  notice(main,"شبیه‌سازی مدیریت ماژول‌ها: وضعیت انتخابی فقط در همین صفحه و تا زمان بارگذاری مجدد حفظ می‌شود. در سامانه واقعی، فعال‌سازی صرفاً پس از خرید معتبر و تأیید مدیر سازمان از طریق API و SQL انجام می‌شود.");
  const grid=node("div","module-grid");
  const core=node("section","module-card");add(core,node("div","num","۱"),node("h2","","دستیار مدیریتی جلسات"),
    node("p","","هسته پایه: پرسش‌وپاسخ مبتنی بر جست‌وجوی صریح در سناریوهای ساختگی."),
    node("div","mod-foot",undefined));
  const foot=core.lastElementChild;add(foot,node("span","badge good","پایه · فعال"),
    action("مشاهده",()=>showTab("assistant"),"button secondary"));add(grid,core);
  for(const code of [2,3,4]){
    const c=node("section","module-card");
    add(c,node("div","num",String(code)),node("h2","",names[code]),node("p","",descriptions[code]));
    const foot=node("div","mod-foot");
    const badge=node("span","badge "+(state.modules[code]?"good":"warn"),
      state.modules[code]?"روشن · آزمایشی":"خاموش · آزمایشی");
    const toggle=action("",()=>{state.modules[code]=!state.modules[code];toast("وضعیت نمایشی تغییر کرد؛ مجوز یا داده واقعی تغییری نکرد.");render()},
      "toggle "+(state.modules[code]?"on":""));
    toggle.setAttribute("role","switch");toggle.setAttribute("aria-label",names[code]);
    toggle.setAttribute("aria-checked",String(state.modules[code]));
    add(foot,badge,toggle);add(c,foot);add(grid,c);
  }
  add(main,grid);
  const n=box("سازوکار واقعی فروش ماژول‌ها","کد API و SQL از این پیش‌نمایش مجزا است");
  add(n,node("p","content-text","در مسیر واقعی هر درخواست، توکن امضاشده، عضویت کاربر و وضعیت اشتراک بررسی می‌شود. ماژول‌های ۲، ۳ و ۴ فقط در صورت داشتن مجوز معتبر و روشن‌بودن در دیتابیس قابل استفاده هستند. خرید بانکی و صدور مجوز واقعی هنوز پیاده‌سازی نشده است."));
  add(main,n);
}
const managementQuestions = [
  "کدام اقدامات مصوب جلسات عقب‌افتاده‌اند؟",
  "مهم‌ترین موضوعات حل‌نشده این ماه چیست؟",
  "عملکرد واحدها در اجرای مصوبات چگونه بوده است؟",
  "کدام مدیر یا واحد بیشترین اقدامات باز را دارد؟",
  "اقدامات جلسه شماره LAB-910002 در چه وضعیتی هستند؟",
  "مهم‌ترین ریسک‌های قابل مشاهده در جلسات اخیر چیست؟",
  "چه موضوعاتی در جلسات مختلف به‌صورت مکرر مطرح شده‌اند؟",
  "برای جلسه آینده چه مواردی باید در دستور جلسه قرار گیرد؟"
];
function assistant(main){
  heading(main,"MODULE 01 / MANAGEMENT ASSISTANT","گزارش‌گیری هوشمند جلسات",
    "هشت پرسش تخصصی قابل اجرا روی ۱۰۰ جلسه و ۳۰۰ اقدام ساختگی، همراه با منبع هر نتیجه.");
  notice(main,"این نسخه جواب محاسبه‌شده از داده‌های نمونه را نشان می‌دهد؛ مدل زبانی، دیتابیس واقعی، چارت مجوزهای واقعی، صدا و اطلاعات عملیاتی در این پیش‌نمایش متصل نیستند.");
  const panel=box("پرسش مدیریتی","پاسخ قابل بررسی · همراه با شماره جلسه/اقدام");
  const input=node("textarea","textarea");
  input.placeholder="مثلاً: کدام اقدامات مصوب جلسات عقب‌افتاده‌اند؟";
  input.setAttribute("aria-label","متن پرسش تخصصی");input.maxLength=350;
  const result=node("div");result.id="assistant-result";
  const send=action("دریافت پاسخ مستند",()=>answerManagementQuestion(input.value),"button teal");
  add(panel,input,node("p","note",
    "در پاسخ، بازه زمانی، تعداد داده‌های بررسی‌شده و محدودیت منابع مشخص است. از این نسخه برای تصمیم عملیاتی استفاده نکنید."),
    send,result);add(main,panel);
  const suggestions=box("پرسش‌های تخصصی آماده","برای اجرای گزارش، یکی از سؤال‌ها را انتخاب کنید");
  const list=node("div","bars");
  managementQuestions.forEach((q,i)=>{
    const button=action(numeric(i+1)+". "+q,()=>{
      input.value=q;answerManagementQuestion(q);
    },"button secondary");
    button.style.textAlign="right";button.style.width="100%";
    add(list,button);
  });
  add(suggestions,list);add(main,suggestions);
}
async function answerManagementQuestion(question){
  const target=$("assistant-result");if(!target)return;
  target.replaceChildren();
  if(!question||question.trim().length<3){
    add(target,node("p","note","لطفاً یک پرسش حداقل سه‌حرفی وارد کنید."));return;
  }
  add(target,node("p","note","در حال محاسبه گزارش و بررسی منابع ساختگی..."));
  try{
    const response=await fetch("/demo-ask",{
      method:"POST",cache:"no-store",credentials:"omit",
      headers:{"Content-Type":"application/json"},
      body:JSON.stringify({question:question.trim()})
    });
    if(!response.ok)throw Error("کد خطا: "+response.status);
    const data=await response.json();
    if(data.synthetic!==true||data.model_used!==false||
       !Array.isArray(data.items)||!Array.isArray(data.sources))
      throw Error("پاسخ نمونه معتبر نیست.");
    if(!$("assistant-result")||$("assistant-result")!==target)return;
    target.replaceChildren();
    const out=node("div","result");
    add(out,node("h2","","پاسخ بر اساس داده‌های ساختگی"),
      node("p","content-text",data.answer),
      node("p","note","زمان محاسبه (UTC): "+data.as_of_utc+
        " · جلسات قابل مشاهده در نمونه: "+numeric(data.meetings_considered)+
        " · اقدامات: "+numeric(data.actions_considered)));
    const details=node("div","detail-group");
    add(details,node("h3","","جلسات و مصوبات مرتبط"));
    for(const item of data.items){
      const row=node("div","list-row"),info=node("div");
      const source=item.source||{},name=source.meeting_no||"شماره نامشخص";
      add(info,node("strong","content-title",item.text),
        node("small","",name+(source.action_no?" · "+source.action_no:"")+
          (item.owner_unit?" · "+item.owner_unit:"")+
          (item.progress_percent!==undefined?" · پیشرفت "+numeric(item.progress_percent)+"٪":"")));
      const show=action("مشاهده پرونده",()=>{
        const meeting=state.cases.find(c=>c.meeting_id===source.meeting_id);
        if(!meeting){toast("جلسه در این مجموعه نمونه پیدا نشد.");return}
        state.selectedId=meeting.meeting_id;showTab("meetings");
      },"text-link");
      add(row,info,show);add(details,row);
    }
    if(!data.items.length)add(details,node("p","note",
      "برای این پرسش منبعی با شرایط تعیین‌شده در سناریوهای موجود پیدا نشد."));
    add(out,details);
    for(const note of data.notes||[])add(out,node("p","note","• "+note));
    add(out,node("p","note",
      "منابع این پاسخ فقط ۱۰۰ سناریوی کاملاً ساختگی هستند. «بدون نتیجه» به معنی نبود مسئله در جلسات واقعی شرکت نیست."));
    add(target,out);
  }catch(error){
    if(target.isConnected){
      target.replaceChildren();
      add(target,node("p","note","امکان محاسبه پاسخ وجود ندارد: "+error.message));
    }
  }
}
/* Explicitly FICTIONAL screens: demonstrate product navigation and interaction
   without a real IdP, SQL writer, ProcessMaker, signed license, or account. */
const demoStaff = [
  {uid:"DEMO-001",name:"کارشناس نمونه یک",unit:"بازرگانی",manager:"مدیر نمونه واحد",role:"Expert"},
  {uid:"DEMO-002",name:"کارشناس نمونه دو",unit:"مجوزات",manager:"مدیر نمونه واحد",role:"Expert"},
  {uid:"DEMO-003",name:"مدیر نمونه واحد",unit:"بازرگانی",manager:"رئیس نمونه هیئت‌مدیره",role:"Manager"},
  {uid:"DEMO-004",name:"رئیس نمونه هیئت‌مدیره",unit:"هیئت‌مدیره",manager:"—",role:"Manager"},
  {uid:"DEMO-005",name:"مدیر سیستم نمونه",unit:"فناوری اطلاعات",manager:"—",role:"SysAdmin"}
];
function sysadmin(main){
  heading(main,"FICTIONAL UI / SYSADMIN","مدیریت سازمان · نمونه ظاهری",
    "پیش‌نمایش چارت، هویت بصری، کاربران و وضعیت اتصال‌ها؛ این صفحه حساب یا مجوز واقعی ندارد.");
  notice(main,"این صفحه فقط نمونه طراحی برای تأیید رابط کاربری است. انتخاب نقش، تغییر نام، همگام‌سازی و بازنشانی رمز در این صفحه هیچ عملیات سروری انجام نمی‌دهند.");
  const settings=box("تنظیمات شرکت","تنظیم نمایشی نام و رنگ · فقط داخل همین مرورگر");
  const name=node("input","search");name.maxLength=120;name.value="شرکت خودرویی کاملاً ساختگی";
  name.setAttribute("aria-label","نام شرکت نمایشی");
  const color=node("input","search");color.type="color";color.value="#0a917e";
  add(settings,node("p","note","نام شرکت"),name,node("p","note","رنگ سازمان"),color,
    action("نمایش تنظیمات پیشنهادی",()=>{
      document.querySelector(".workspace strong").textContent=name.value.trim()||"شرکت نمونه";
      document.documentElement.style.setProperty("--teal",color.value);
      toast("نام و رنگ فقط در مرورگر این پیش‌نمایش تغییر کردند؛ SQL یا برندینگ واقعی تغییری نکرد.");
    },"button teal"));
  add(main,settings);
  const connect=box("اتصال‌های سازمان","اطلاعات ورود و نشانی واقعی هرگز در پیش‌نمایش دریافت نمی‌شود");
  const points=[
    ["ProcessMaker 3.3.6","در این صفحه متصل نیست · نیازمند OAuth فقط‌خواندنی و Workspace تأییدشده"],
    ["SQL Server","در این صفحه متصل نیست · نیازمند Reader و Admin مجزا، RLS و بانک آزمایشی"],
    ["Keycloak / هویت سازمانی","در این صفحه متصل نیست · نیازمند issuer معتبر، MFA و شناسه sub تأییدشده"]
  ];
  points.forEach(([k,v])=>add(connect,section(k,v)));
  add(connect,action("پیش‌نمایش عملیات Sync",()=>toast(
    "این دکمه فقط نمایشی است. همگام‌سازی واقعی از پنل متصل و با احراز هویت SysAdmin انجام می‌شود."
  ),"button secondary"));
  add(main,connect);
  const users=box("کاربران و چارت سازمانی نمونه","۵ هویت ساختگی · شناسه ProcessMaker واقعی نیست");
  const table=node("table","table"),head=node("thead"),tr=node("tr");
  ["شناسه نمونه","نام","واحد","مدیر مستقیم","نقش نمونه"].forEach(x=>add(tr,node("th","",x)));
  add(head,tr);add(table,head);
  const body=node("tbody");
  demoStaff.forEach(person=>{
    const row=node("tr");
    [person.uid,person.name,person.unit,person.manager].forEach(x=>add(row,node("td","",x)));
    const cell=node("td");
    if(person.role==="SysAdmin")add(cell,node("span","badge purple","SysAdmin · نمونه"));
    else add(cell,selectBox([["Expert","کارشناس"],["Manager","مدیر"]],person.role,v=>{
      person.role=v;toast("نقش این شخص ساختگی فقط در رابط نمایشی تغییر کرد.");
    },"نقش ساختگی "+person.name));
    add(row,cell);add(body,row);
  });
  add(table,body);add(users,add(node("div","table-wrap"),table));
  add(users,node("p","note",
    "قاعده محصول واقعی: کارشناس جلسات خود/زیرچارت، مدیر همه جلسات سازمان، SysAdmin مدیریت تنظیمات و کاربران. این جدول برای نشان‌دادن طراحی است نه صدور مجوز واقعی."));
  add(main,users);
  const identity=box("مدیریت حساب","بدون ارسال ایمیل، تغییر رمز یا ساخت کاربر");
  add(identity,node("p","content-text",
    "برای ایجاد حساب و اتصال شناسه کاربر ProcessMaker، هویت باید ابتدا نزد Keycloak تأیید شود. درخواست ایمیل تغییر رمز فقط از پنل واقعیِ دارای توکن و با سرویس مدیریتی فعال ارسال خواهد شد."),
    action("نمایش شرط فعال‌شدن مدیریت کاربران",()=>toast(
      "نیازمند Keycloak واقعی، حساب SysAdmin تأییدشده و API متصل در /portal/ است؛ عملیات واقعی اینجا غیرفعال است."
    ),"button secondary"));
  add(main,identity);
}
function godadmin(main){
  heading(main,"FICTIONAL UI / GODADMIN","کنترل پنل لیماک · نمونه ظاهری",
    "مرور نمای مدیریت مشتریان، ماژول‌ها، ظرفیت کاربر و لایسنس قبل از اتصال به سامانه تجاری.");
  notice(main,"GodAdmin واقعی فقط پس از احراز هویت معتبر و ثبت مستقل PlatformOperator فعال می‌شود؛ نقش سازنده به‌تنهایی دسترسی به محتوای محرمانه مشتری ندارد. این صفحه صرفاً نمایش طراحی است.");
  const stats=node("div","stats");
  add(stats,stat("مشتری ساختگی",2,"بدون ثبت مشتری در SQL","♙"),
    stat("ماژول قابل‌فروش",3,"شماره‌های ۲، ۳ و ۴","⬡","teal"),
    stat("لایسنس واقعی صادرشده",0,"بدون کلید خصوصی صادرکننده","◆","purple"),
    stat("حساب واقعی ساخته‌شده",0,"بدون Keycloak و پرداخت","✓","amber"));
  add(main,stats);
  const catalog=box("فهرست مشتریان نمونه","داده نمایشی؛ مجوز و پرداخت واقعی ندارد");
  [
    ["شرکت خودرویی ساختگی الف","۳۵ کاربر · دبیر روشن، تحلیل خاموش، پایش روشن"],
    ["شرکت خودرویی ساختگی ب","۱۲ کاربر · فقط هسته پایه"]
  ].forEach(([name,detail])=>add(catalog,section(name,detail)));
  add(main,catalog);
  const studio=box("مشخصات درخواست لایسنس","پیش‌نمایش فرم · هیچ کلید یا امضایی تولید نمی‌شود");
  const customer=node("input","search");customer.placeholder="نام مشتری کاملاً ساختگی";
  customer.maxLength=120;customer.setAttribute("aria-label","نام مشتری نمونه");
  const seats=node("input","search");seats.type="number";seats.min="1";
  seats.max="100000";seats.value="100";seats.setAttribute("aria-label","حداکثر تعداد کاربران نمونه");
  const selection=node("div","flex"),chosen=[];
  for(const [id,titleText] of [[2,"دبیر"],[3,"تحلیل"],[4,"پایش"]]){
    const label=node("label","chip"),input=node("input");input.type="checkbox";input.value=String(id);
    if(id===2)input.checked=true;
    add(label,input,node("span","",titleText));add(selection,label);chosen.push(input);
  }
  const output=node("div");
  add(studio,node("p","note","نام سازمان"),customer,node("p","note","ظرفیت کاربر"),
    seats,node("p","note","ماژول‌های اختیاری"),selection,
    action("نمایش درخواست نمونه",()=>{
      output.replaceChildren();
      if(!customer.value.trim()||!Number.isInteger(Number(seats.value))||
         Number(seats.value)<1||Number(seats.value)>100000){
        add(output,node("p","note","نام شرکت و ظرفیت معتبر نمونه وارد کنید."));return;
      }
      const codes=[1,...chosen.filter(x=>x.checked).map(x=>Number(x.value))];
      add(output,node("p","content-text","درخواست نمایشی برای "+customer.value.trim()+
        " · ظرفیت "+numeric(Number(seats.value))+" کاربر · ماژول‌های "+codes.join("، ")),
        node("p","note","این درخواست به سرور ارسال نشده و لایسنس ایجاد نشده است. صدور معتبر فقط با LIMAK License Studio و کلید خصوصی آفلاین انجام می‌شود."));
    },"button teal"),output);
  add(main,studio);
}

function render(){
  const main=$("main");main.replaceChildren();
  switch(state.tab){
    case "meetings": meetings(main);break;
    case "assistant": assistant(main);break;
    case "secretary": secretary(main);break;
    case "analytics": analytics(main);break;
    case "monitoring": monitoring(main);break;
    case "modules": modules(main);break;
    case "sysadmin": sysadmin(main);break;
    case "godadmin": godadmin(main);break;
    default: overview(main);
  }
}
async function initialize(){
  document.querySelectorAll(".nav-item").forEach(b=>b.addEventListener("click",()=>showTab(b.dataset.tab)));
  $("menu-toggle").addEventListener("click",()=>{
    const sidebar=document.querySelector(".sidebar");
    const opened=sidebar.classList.toggle("open");
    $("menu-toggle").setAttribute("aria-expanded",String(opened));
  });
  try{
    const res=await fetch("/demo-data",{cache:"no-store",credentials:"omit"});
    if(!res.ok)throw Error("HTTP "+res.status);
    const data=await res.json();
    if(data.synthetic!==true||data.count!==100||!Array.isArray(data.scenarios)
       ||data.scenarios.length!==100)throw Error("invalid fictional dataset");
    state.cases=data.scenarios;
    render();
  }catch(err){
    const main=$("main");main.replaceChildren();
    const e=node("div","locked");
    add(e,node("h2","","امکان بارگذاری داده نمونه وجود ندارد"),
      node("p","",String(err.message)),node("p","note","برنامه پیش‌نمایش را از طریق پورت 8090 و فقط روی localhost اجرا کنید."));
    add(main,e);
  }
}
document.addEventListener("DOMContentLoaded",initialize);
