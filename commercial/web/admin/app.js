"use strict";
if(new URLSearchParams(window.location.search).get("embedded")==="1"){document.body.classList.add("admin-embedded");}
const state={csrf:null,user:null,settings:null,stage:"login",page:"connections",authMode:"bootstrap",orgSub:"company"};
const $=id=>document.getElementById(id);
function node(tag,cls,text){const n=document.createElement(tag);if(cls)n.className=cls;if(text!==undefined)n.textContent=String(text);return n}
function append(parent,...items){for(const item of items.flat())if(item!==null&&item!==undefined)parent.append(item);return parent}
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
 input.value=value||"";input.required=options.required!==false;input.autocomplete="off";
 if(options.placeholder)input.placeholder=options.placeholder;
 append(label,input);append(wrap,label);return wrap;
}
function selectField(title,name,items,value="",options={}){
 const wrap=node("div","form-field"),label=node("label","",title),select=node("select");
 select.name=name;select.required=options.required!==false;
 for(const item of items){
  const option=node("option","",item.label);option.value=item.value;
  if(item.value===value)option.selected=true;select.append(option);
 }
 select.disabled=!!options.disabled;append(label,select);append(wrap,label);return wrap;
}
function helpButton(topic,label="راهنمای این بخش"){
 const a=node("a","help-launch","💡 "+label);
 a.href="/admin/help/?topic="+encodeURIComponent(topic);
 a.target="_blank";a.rel="noopener noreferrer";
 a.setAttribute("aria-label","باز کردن راهنمای "+label+" در تب جدید");return a;
}
function helpTopicFor(page){
 if(page==="organization")return "organization-"+state.orgSub;
 return page;
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
  else if(!s.authenticated)showLogin();
  else if(!s.password_changed)showChangePassword();
  else if(!s.mfa_enrolled)showTotpEnroll();
  else if(!s.mfa_authenticated)showLogin();
  else if(state.authMode==="bootstrap"&&!document.body.classList.contains("admin-embedded")){
   window.location.replace("/");
  }
  else await showSettings();
 }catch(err){main().append(info(err.message||String(err),true))}
}
let _turnstilePromise=null;
function ensureTurnstile(timeoutMs=2500){
 if(window.turnstile)return Promise.resolve(window.turnstile);
 if(_turnstilePromise)return _turnstilePromise;
 _turnstilePromise=new Promise((resolve,reject)=>{
  const callback="__avanHybridTurnstileReady";
  const timer=setTimeout(()=>{
   document.querySelector('script[data-avan-turnstile="1"]')?.remove();
   _turnstilePromise=null;
   reject(Error("Cloudflare timeout"));
  },Math.max(1200,timeoutMs));
  window[callback]=()=>{
   clearTimeout(timer);
   try{delete window[callback]}catch{}
   if(window.turnstile)resolve(window.turnstile);
   else{_turnstilePromise=null;reject(Error("Cloudflare unavailable"))}
  };
  const existing=document.querySelector('script[data-avan-turnstile="1"]');
  if(existing)existing.remove();
  const script=document.createElement("script");
  script.dataset.avanTurnstile="1";
  script.src="https://challenges.cloudflare.com/turnstile/v0/api.js?onload="+callback+"&render=explicit";
  script.async=true;script.defer=true;
  script.onerror=()=>{
   clearTimeout(timer);_turnstilePromise=null;
   try{delete window[callback]}catch{}
   reject(Error("Cloudflare load failed"));
  };
  document.head.appendChild(script);
 });
 return _turnstilePromise;
}
async function solveLocalAntibot(config,onProgress){
 if(!window.crypto?.subtle)throw Error("مرورگر از اعتبارسنجی امن محلی پشتیبانی نمی‌کند.");
 if(config?.provider!=="altcha-self-hosted"||config.algorithm!=="SHA-256")
  throw Error("سرویس ضدربات داخلی پاسخ معتبر نداد.");
 const max=Number(config.maxNumber);
 if(!Number.isInteger(max)||max<1000||max>250000)throw Error("سطح سختی ضدربات معتبر نیست.");
 const encoder=new TextEncoder(),target=String(config.challenge).toLowerCase(),salt=String(config.salt);
 const batchSize=64;
 for(let start=0;start<=max;start+=batchSize){
  const stop=Math.min(max,start+batchSize-1);
  const numbers=[];for(let n=start;n<=stop;n++)numbers.push(n);
  const hashes=await Promise.all(numbers.map(n=>crypto.subtle.digest("SHA-256",encoder.encode(salt+n))));
  for(let i=0;i<hashes.length;i++){
   const hex=[...new Uint8Array(hashes[i])].map(b=>b.toString(16).padStart(2,"0")).join("");
   if(hex===target)return numbers[i];
  }
  if(typeof onProgress==="function"&&(start===0||start%1024<batchSize))
   onProgress(Math.min(99,Math.round((stop/max)*100)));
 }
 throw Error("اثبات امنیتی محلی حل نشد.");
}
function antibotPayload(config,number){
 return btoa(JSON.stringify({
  algorithm:config.algorithm,
  challenge:config.challenge,
  number,
  salt:config.salt,
  signature:config.signature
 }));
}
function antibotEnvelope(provider,value){
 return JSON.stringify({provider,token:value});
}
function buildCaptchaShell(host){
 host.className="avan-captcha is-loading";
 host.setAttribute("aria-label","اعتبارسنجی امنیتی");
 host.innerHTML=`<div class="avan-captcha-head">
  <div class="avan-captcha-visual" aria-hidden="true">
   <span class="captcha-scan-ring ring-a"></span><span class="captcha-scan-ring ring-b"></span>
   <span class="captcha-orbit-dot dot-a"></span><span class="captcha-orbit-dot dot-b"></span>
   <svg class="captcha-shield" viewBox="0 0 64 64" focusable="false">
    <defs><linearGradient id="captchaShieldGradient" x1="10" y1="8" x2="54" y2="57" gradientUnits="userSpaceOnUse"><stop stop-color="#65f6e8"/><stop offset=".52" stop-color="#23d9f1"/><stop offset="1" stop-color="#168cff"/></linearGradient></defs>
    <path class="shield-body" d="M32 5.5 52 13v15.2c0 13.2-7.8 23.8-20 30.3C19.8 52 12 41.4 12 28.2V13l20-7.5Z"></path>
    <path class="shield-scan" d="M20.3 31.8 28 39.5 44.8 22.7"></path>
   </svg>
  </div>
  <div class="avan-captcha-copy"><strong>بررسی امنیتی هوشمند</strong><span class="avan-captcha-status" aria-live="polite">در حال بررسی امنیتی…</span></div>
  <span class="avan-captcha-badge">HYBRID</span>
 </div>
 <div class="avan-captcha-progress" aria-hidden="true"><span></span></div>
 <div class="avan-captcha-challenge">
  <span class="captcha-provider">CLOUDFLARE → ALTCHA FALLBACK</span>
  <div class="captcha-turnstile-slot"></div>
 </div>`;
 return {
  slot:host.querySelector(".captcha-turnstile-slot"),
  provider:host.querySelector(".captcha-provider"),
  badge:host.querySelector(".avan-captcha-badge"),
  status:host.querySelector(".avan-captcha-status")
 };
}
function cloudflareAttempt(config,ui,setState){
 return new Promise(async(resolve,reject)=>{
  if(!config?.enabled||!config.site_key){reject(Error("Cloudflare disabled"));return}
  const timeoutMs=Math.max(1200,Math.min(5000,Number(config.timeout_ms)||2500));
  setState("is-checking","در حال بررسی امنیتی…");
  ui.badge.textContent="CLOUDFLARE";ui.provider.textContent="CLOUDFLARE TURNSTILE · PRIMARY";
  let settled=false,widgetId=null;
  const fail=err=>{
   if(settled)return;settled=true;clearTimeout(timer);
   if(window.turnstile&&widgetId!==null){try{window.turnstile.remove(widgetId)}catch{}}
   ui.slot.replaceChildren();reject(err instanceof Error?err:Error(String(err)));
  };
  const success=value=>{
   if(settled)return;settled=true;clearTimeout(timer);resolve(value);
  };
  const timer=setTimeout(()=>fail(Error("Cloudflare verification timeout")),timeoutMs);
  try{
   const turnstile=await ensureTurnstile(timeoutMs);
   if(settled)return;
   widgetId=turnstile.render(ui.slot,{
    sitekey:config.site_key,
    action:config.action,
    theme:config.theme||"dark",
    size:"flexible",
    appearance:"interaction-only",
    language:"fa",
    retry:"never",
    "refresh-expired":"never",
    callback:success,
    "expired-callback":()=>fail(Error("Cloudflare token expired")),
    "timeout-callback":()=>fail(Error("Cloudflare challenge timeout")),
    "error-callback":()=>fail(Error("Cloudflare verification failed"))
   });
  }catch(err){fail(err)}
 });
}
async function mountLoginCaptcha(host,submit,out){
 submit.disabled=true;
 const ui=buildCaptchaShell(host);
 let token="",currentProvider="",forceLocal=false,generation=0,expiryTimer=null;
 const setState=(name,message)=>{
  host.classList.remove("is-loading","is-checking","is-verified","is-expired","is-error");
  host.classList.add(name);
  ui.status.textContent=message;
 };
 const solveNew=async()=>{
  const current=++generation;token="";currentProvider="";submit.disabled=true;
  clearTimeout(expiryTimer);ui.slot.replaceChildren();
  setState("is-checking","در حال بررسی امنیتی…");
  const config=await api("captcha/config");
  if(config?.provider!=="hybrid")throw Error("پیکربندی Hybrid Anti-Bot معتبر نیست.");

  if(config.cloudflare?.enabled&&!forceLocal){
   try{
    const cfToken=await cloudflareAttempt(config.cloudflare,ui,setState);
    if(current!==generation)return;
    token=antibotEnvelope("cloudflare-turnstile",cfToken);currentProvider="cloudflare-turnstile";
    submit.disabled=false;ui.badge.textContent="CLOUDFLARE";
    ui.provider.textContent="CLOUDFLARE TURNSTILE · VERIFIED";
    setState("is-verified","اعتبارسنجی امنیتی انجام شد");
    return;
   }catch(_err){
    if(current!==generation)return;
    ui.slot.replaceChildren();ui.badge.textContent="LOCAL";
    ui.provider.textContent="ALTCHA · SELF-HOSTED FALLBACK";
    setState("is-checking","در حال تکمیل بررسی امنیتی…");
   }
  }else{
   ui.badge.textContent="LOCAL";ui.provider.textContent="ALTCHA · SELF-HOSTED";
   setState("is-checking",forceLocal?"در حال بررسی امنیتی…":"در حال بررسی امنیتی…");
  }

  if(!config.local)throw Error("Cloudflare و Anti-Bot داخلی هر دو در دسترس نیستند.");
  const number=await solveLocalAntibot(config.local,percent=>{
   if(current===generation)setState("is-checking",`در حال بررسی امنیتی… ${percent}٪`);
  });
  if(current!==generation)return;
  token=antibotEnvelope("altcha-self-hosted",antibotPayload(config.local,number));currentProvider="altcha-self-hosted";
  submit.disabled=false;
  setState("is-verified","اعتبارسنجی امنیتی انجام شد");
  const ttl=Math.max(15,Number(config.local.expiresIn)||120);
  expiryTimer=setTimeout(()=>{
   if(current!==generation)return;
   token="";submit.disabled=true;
   setState("is-expired","Challenge منقضی شد؛ بررسی تازه در حال اجراست…");
   solveNew().catch(err=>{
    setState("is-error","هیچ مسیر ضدرباتی در دسترس نیست");
    out.replaceChildren(info(err.message||"اعتبارسنجی ضدربات کامل نشد.",true));
   });
  },Math.max(5000,(ttl-8)*1000));
 };
 try{await solveNew()}catch(err){
  setState("is-error","هیچ مسیر ضدرباتی در دسترس نیست");
  throw err;
 }
 return {
  token:()=>token,
  reset:()=>{
   if(currentProvider==="cloudflare-turnstile")forceLocal=true;
   token="";currentProvider="";submit.disabled=true;
   solveNew().catch(err=>{
    setState("is-error","بررسی امنیتی کامل نشد");
    out.replaceChildren(info(err.message||"اعتبارسنجی ضدربات کامل نشد؛ دوباره تلاش کنید.",true));
   });
  }
 };
}
function loginCardDecor(){
 const d=node("div","login-card-decor");d.setAttribute("aria-hidden","true");
 d.innerHTML=`<svg viewBox="0 0 600 760" preserveAspectRatio="none" focusable="false">
  <defs>
   <linearGradient id="avanLoginStroke" x1="0" y1="0" x2="1" y2="1">
    <stop offset="0" stop-color="#79ecff"/><stop offset=".48" stop-color="#16d7f2"/><stop offset="1" stop-color="#0b8fff"/>
   </linearGradient>
   <radialGradient id="avanLoginGlow"><stop offset="0" stop-color="#35ecff" stop-opacity=".9"/><stop offset="1" stop-color="#35ecff" stop-opacity="0"/></radialGradient>
   <pattern id="avanLoginDots" width="18" height="18" patternUnits="userSpaceOnUse">
    <circle cx="2" cy="2" r="1.35" fill="#1fdcf4" opacity=".5"/>
   </pattern>
  </defs>
  <rect x="1.5" y="1.5" width="597" height="757" rx="34" fill="none" stroke="url(#avanLoginStroke)" stroke-width="2"/>
  <path d="M0 178C78 129 111 75 155 0" fill="none" stroke="#18cffa" stroke-width="1.25" opacity=".8"/>
  <path d="M600 546C537 592 522 691 425 760" fill="none" stroke="#18cffa" stroke-width="1.25" opacity=".8"/>
  <path d="M0 105C70 72 91 41 119 0" fill="none" stroke="#178fd8" stroke-width=".7" opacity=".65"/>
  <path d="M600 623C558 653 540 705 486 760" fill="none" stroke="#178fd8" stroke-width=".7" opacity=".65"/>
  <rect x="34" y="62" width="128" height="146" fill="url(#avanLoginDots)" opacity=".38"/>
  <rect x="444" y="568" width="118" height="118" fill="url(#avanLoginDots)" opacity=".3"/>
  <circle cx="301" cy="2" r="42" fill="url(#avanLoginGlow)" opacity=".42"/>
  <circle cx="598" cy="368" r="54" fill="url(#avanLoginGlow)" opacity=".22"/>
 </svg>`;
 return d;
}
function loginBrand(){
 const brand=node("div","login-brand"),mark=node("span","login-brand-mark"),copy=node("span","login-brand-copy");
 mark.setAttribute("aria-hidden","true");
 mark.innerHTML=`<svg viewBox="0 0 64 64" focusable="false"><defs><linearGradient id="avanMarkGradient" x1="8" y1="7" x2="55" y2="57" gradientUnits="userSpaceOnUse"><stop stop-color="#24f0e0"/><stop offset=".48" stop-color="#10cbe8"/><stop offset="1" stop-color="#1689ff"/></linearGradient></defs><path d="M30.9 7.7c1.7-3 6-3 7.7 0l18 31.2c1.8 3.1-.4 7-4 7H39.1L32 33.6l-7.1 12.3H11.4c-3.6 0-5.8-3.9-4-7l18-31.2c1.2-2 4.2-2 5.5 0Z" fill="url(#avanMarkGradient)"/><path d="M32 33.6 39.1 46H24.9L32 33.6Z" fill="#08263b"/></svg>`;
 append(copy,node("strong","","آوان"),node("small","","AI AGENT"));
 return append(brand,mark,copy);
}
function loginRevealButton(){
 const b=node("button","login-reveal-toggle");
 b.type="button";b.setAttribute("aria-expanded","false");
 b.innerHTML='<span>ورود</span><svg viewBox="0 0 24 24" aria-hidden="true"><path d="m7 9.5 5 5 5-5"></path></svg>';
 return b;
}
function showLogin(){
 const m=main(),p=panel("ورود به آوان","");
 p.classList.add("login","login-reveal-card","is-expanded","login-fixed-card");
 p.prepend(loginCardDecor(),loginBrand());
 const subtitle=node("p","login-reveal-subtitle","خوش آمدید؛ برای ادامه وارد حساب کاربری شوید.");
 const f=node("form","login-expand-body");
 const username=field("نام کاربری","username",""),password=field("رمز عبور","password","",{secret:true});
 append(f,username,password);
 const out=node("div"),captchaHost=node("div","turnstile-shell");
 const loginBtn=node("button","","ورود به آوان");loginBtn.type="submit";
 append(f,captchaHost,loginBtn,out);
 p.querySelector("h2")?.after(subtitle);
 append(p,f);append(m,p);

 let captcha=null,captchaReady=null;
 username.querySelector("input").autocomplete="username";
 password.querySelector("input").autocomplete="current-password";
 const ensureCaptchaMounted=()=>{
  if(!captchaReady)captchaReady=mountLoginCaptcha(captchaHost,loginBtn,out).then(x=>captcha=x).catch(err=>{
   showError(out,err);loginBtn.disabled=true;return null;
  });
  return captchaReady;
 };
 ensureCaptchaMounted();

 f.addEventListener("submit",async e=>{
  e.preventDefault();out.replaceChildren();
  try{
    captcha=await ensureCaptchaMounted();
    if(!captcha)throw Error("سرویس ضدربات آماده نیست.");
    const captchaToken=captcha.token()||"";
    if(!captchaToken)throw Error("ابتدا اعتبارسنجی ضدربات را کامل کنید.");
    p.dataset.submitting="1";busy(f,true);
    const result=await api("login",{username:formValue(f,"username"),
      password:f.elements.namedItem("password").value,captcha_token:captchaToken});
    if(result.mfa_required){showLoginOtp(result.challenge);return}
    state.csrf=result.csrf;window.location.assign("/")
  }catch(err){showError(out,err);captcha?.reset()}finally{
   delete p.dataset.submitting;busy(f,false);
   if(captcha&&!captcha.token())loginBtn.disabled=true;
  }
 });
}
function normalizeOtpDigits(value){
 const fa="۰۱۲۳۴۵۶۷۸۹",ar="٠١٢٣٤٥٦٧٨٩";
 return String(value||"").replace(/[۰-۹]/g,c=>String(fa.indexOf(c)))
   .replace(/[٠-٩]/g,c=>String(ar.indexOf(c))).replace(/\D/g,"").slice(0,6);
}
function createOtpMotionField(title,name,onComplete){
 const wrap=node("div","form-field otp-motion-field"),label=node("label","",title);
 const motion=node("div","otp-motion"),input=node("input","otp-motion-native");
 const stage=node("div","otp-stage"),ring=node("span","otp-orbit-ring");
 const digits=node("div","otp-digits"),verified=node("div","otp-verified");
 const status=node("span","otp-motion-status","");
 input.type="text";input.name=name;input.id="avan-"+name+"-motion";
 input.inputMode="numeric";input.pattern="[0-9]{6}";input.maxLength=6;
 input.autocomplete="one-time-code";input.required=true;
 label.htmlFor=input.id;motion.tabIndex=-1;
 stage.setAttribute("aria-hidden","true");status.setAttribute("aria-live","polite");
 for(let i=0;i<6;i++){const d=node("span","otp-digit","");d.style.setProperty("--i",String(i));append(digits,d)}
 verified.innerHTML='<svg viewBox="0 0 48 48" focusable="false"><circle cx="24" cy="24" r="20"></circle><path d="m15.5 24.5 5.5 5.5 12-13"></path></svg><span>تأیید شد</span>';
 append(stage,ring,digits,verified);append(motion,input,stage,status);append(wrap,label,motion);
 const cells=[...digits.children];
 let completion=null,errorTimer=null;
 function render(){
  const value=normalizeOtpDigits(input.value);if(input.value!==value)input.value=value;
  cells.forEach((cell,index)=>{
   cell.textContent=value[index]||"";
   cell.classList.toggle("is-filled",index<value.length);
   cell.classList.toggle("is-next",index===value.length&&value.length<6);
  });
  motion.classList.toggle("has-value",value.length>0);
 }
 function reset(error=false){
  completion=null;input.readOnly=false;input.value="";render();
  motion.classList.remove("is-complete","is-verified");
  if(error){motion.classList.add("is-error");clearTimeout(errorTimer);errorTimer=setTimeout(()=>motion.classList.remove("is-error"),520)}
  status.textContent=error?"کد تأیید نشد؛ دوباره وارد کنید.":"";
 }
 function complete(){
  if(completion)return completion;
  const value=normalizeOtpDigits(input.value);
  if(value.length!==6){motion.classList.add("is-error");setTimeout(()=>motion.classList.remove("is-error"),420);input.focus();return Promise.resolve(false)}
  input.value=value;input.readOnly=true;motion.classList.add("is-complete");
  status.textContent="کد کامل شد؛ در حال تأیید.";
  const reduced=window.matchMedia&&window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  completion=new Promise(resolve=>setTimeout(()=>{
   motion.classList.add("is-verified");status.textContent="کد آماده تأیید است.";resolve(true);
  },reduced?80:1180));
  return completion;
 }
 input.addEventListener("input",()=>{
  input.value=normalizeOtpDigits(input.value);render();
  if(input.value.length===6&&!motion.classList.contains("is-complete")&&typeof onComplete==="function")
   setTimeout(()=>onComplete(),35);
 });
 input.addEventListener("paste",event=>{
  const text=event.clipboardData?.getData("text")||"",value=normalizeOtpDigits(text);
  if(value){event.preventDefault();input.value=value;render();input.dispatchEvent(new Event("input",{bubbles:true}))}
 });
 motion.addEventListener("click",()=>{if(!input.readOnly)input.focus()});
 render();
 return {wrap,input,complete,reset};
}
function showLoginOtp(challenge){
 const m=main(),p=panel("تأیید دومرحله‌ای","");
 p.classList.add("login","login-otp");p.prepend(loginCardDecor(),loginBrand());
 const f=node("form"),out=node("div");
 let submitting=false;
 const code=createOtpMotionField("کد شش‌رقمی Authenticator","otp",()=>{if(!submitting)f.requestSubmit()});
 const submit=node("button","","تأیید و ورود");submit.type="submit";
 append(f,code.wrap,submit,out);append(p,f,btn("بازگشت به ورود",showLogin,"secondary"));append(m,p);
 code.input.focus();
 f.addEventListener("submit",async e=>{
  e.preventDefault();if(submitting)return;
  const otp=normalizeOtpDigits(code.input.value);
  if(otp.length!==6){await code.complete();return}
  submitting=true;busy(f,true);out.replaceChildren();
  try{
    const animated=await code.complete();if(!animated)return;
    const result=await api("login/otp",{challenge,otp});
    state.csrf=result.csrf;window.location.assign("/")
  }catch(err){
    code.reset(true);showError(out,err);code.input.focus()
  }finally{submitting=false;busy(f,false)}
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


async function renderUserBpmsBindings(m){
 const p=panel("اتصال کاربران به BPMS",
  "هر کاربر AVAN را به حساب متناظر همان شخص در هر BPMS متصل کنید. هویت AVAN مستقل می‌ماند و فقط نگاشت حساب BPMS ثبت می‌شود.");
 append(m,p);
 const feedback=node("div"),controls=node("div","grid"),editor=node("div"),summary=node("div","connection-list");
 append(p,feedback,controls,editor,node("h3","","اتصال‌های ثبت‌شده"),summary);

 const results=await Promise.allSettled([
  api("users/mapped"),
  api("user-bindings/sources"),
  api("user-bindings/list")
 ]);
 const value=i=>results[i].status==="fulfilled"?results[i].value:{};
 for(const result of results)if(result.status==="rejected")append(feedback,info(result.reason.message,true));

 const users=(value(0).users||[]).filter(x=>x.subject&&x.enabled!==false);
 const sources=(value(1).sources||[]).filter(x=>x.id&&x.enabled!==false);
 const bindings=value(2).bindings||[];

 if(!users.length){
  append(p,info("ابتدا حداقل یک کاربر فعال در AVAN ایجاد کنید.",true));
  return;
 }
 if(!sources.length){
  append(p,info("ابتدا حداقل یک اتصال فعال BPMS/ProcessMaker در بخش «اتصالات BPMS» ثبت کنید.",true));
  return;
 }

 const userLabel=node("label","","کاربر AVAN"),userSelect=node("select");
 userSelect.name="avan_subject";
 for(const user of users){
  const opt=node("option","",(user.name||user.username||user.subject)+" · "+(user.username||""));
  opt.value=user.subject;append(userSelect,opt);
 }
 append(userLabel,userSelect);

 const sourceLabel=node("label","","BPMS / ProcessMaker"),sourceSelect=node("select");
 sourceSelect.name="source_id";
 for(const source of sources){
  const engine=source.engine==="processmaker"?"ProcessMaker":(source.engine||"BPMS");
  const opt=node("option","",source.name+" · "+engine);
  opt.value=source.id;append(sourceSelect,opt);
 }
 append(sourceLabel,sourceSelect);
 append(controls,userLabel,sourceLabel);

 const selectedUser=()=>users.find(x=>x.subject===userSelect.value);
 const selectedSource=()=>sources.find(x=>x.id===sourceSelect.value);
 const currentBinding=()=>bindings.find(x=>x.avan_subject===userSelect.value&&x.source_id===sourceSelect.value&&x.status==="active");

 async function loadEditor(){
  const user=selectedUser(),source=selectedSource();
  if(!user||!source)return;
  editor.replaceChildren(info("در حال خواندن کاربران «"+source.name+"»…"));
  try{
   const data=await api("user-bindings/directory?subject="+encodeURIComponent(user.subject)+
                        "&source_id="+encodeURIComponent(source.id));
   const directory=(data.users||[]).filter(x=>x.active);
   const suggestions=data.suggestions||[];
   const current=currentBinding();
   editor.replaceChildren();

   const box=panel("اتصال "+(user.name||user.username)+" به "+source.name,
    "نام کاربری همان شخص در این BPMS را وارد کنید. آوان فقط در صورت وجود یک کاربر فعال با همین username اتصال را ثبت می‌کند.");
   const form=node("form","grid binding-editor");
   const usernameField=field("نام کاربری کاربر در "+source.name,"external_username",current?.external_username||"");
   const input=usernameField.querySelector("input");
   const listId="bpms-usernames-"+source.id+"-"+String(user.subject).replaceAll(/[^A-Za-z0-9]/g,"").slice(0,12);
   const datalist=node("datalist");datalist.id=listId;input.setAttribute("list",listId);
   input.autocomplete="off";input.placeholder="مثال: hamid.noee";
   for(const ext of directory){
    const opt=node("option");opt.value=ext.username||"";
    opt.label=[ext.display_name,ext.unit].filter(Boolean).join(" · ");
    append(datalist,opt);
   }
   append(form,usernameField,datalist);

   if(current){
    append(form,info("اتصال فعلی: "+current.external_username+
      (current.external_display_name?" · "+current.external_display_name:"")));
   }else{
    append(form,info("برای این کاربر و این BPMS هنوز اتصالی ثبت نشده است."));
   }

   if(suggestions.length){
    const suggestionBox=node("div","full");
    append(suggestionBox,node("strong","","پیشنهادهای احتمالی"));
    for(const candidate of suggestions.slice(0,3)){
     const row=node("div","binding-suggestion");
     append(row,
      node("span","",candidate.display_name+" · "+candidate.username),
      btn("استفاده از این username",()=>{input.value=candidate.username||""},"secondary"));
     append(suggestionBox,row);
    }
    append(form,suggestionBox);
   }

   const out=node("div","full"),actions=node("div","actions full");
   append(actions,
    btn(current?"به‌روزرسانی اتصال":"برقراری اتصال",async()=>{
     out.replaceChildren();
     const username=input.value.trim();
     if(!username){showError(out,Error("نام کاربری BPMS را وارد کنید."));return}
     busy(form,true);
     try{
      await api("user-bindings/bind-username",{
       subject:user.subject,source_id:source.id,external_username:username
      });
      append(out,info("اتصال کاربر به "+source.name+" با موفقیت ذخیره شد."));
      await showSettings("userbpms");
     }catch(err){showError(out,err)}finally{busy(form,false)}
    }),
    btn("خواندن مجدد کاربران BPMS",async()=>{
     out.replaceChildren();busy(form,true);
     try{
      await api("user-bindings/refresh",{source_id:source.id});
      append(out,info("فهرست کاربران و وضعیت اتصال‌ها از BPMS به‌روزرسانی شد."));
      await loadEditor();
     }catch(err){showError(out,err)}finally{busy(form,false)}
    },"secondary")
   );
   if(current)append(actions,btn("قطع اتصال",async()=>{
    if(!confirm("اتصال این کاربر به "+source.name+" قطع شود؟"))return;
    out.replaceChildren();busy(form,true);
    try{
     await api("user-bindings/unbind",{subject:user.subject,source_id:source.id});
     await showSettings("userbpms");
    }catch(err){showError(out,err)}finally{busy(form,false)}
   },"danger"));
   append(form,actions,out);append(box,form);append(editor,box);
  }catch(err){
   editor.replaceChildren();
   showError(editor,err);
  }
 }

 userSelect.addEventListener("change",loadEditor);
 sourceSelect.addEventListener("change",loadEditor);

 if(!bindings.length)append(summary,info("هنوز هیچ اتصال کاربر↔BPMS ثبت نشده است."));
 for(const binding of bindings){
  const user=users.find(x=>x.subject===binding.avan_subject);
  const source=sources.find(x=>x.id===binding.source_id);
  if(!user||!source)continue;
  const actions=node("div","connection-actions");
  append(actions,btn("مدیریت",()=>{
   userSelect.value=user.subject;sourceSelect.value=source.id;loadEditor();
  },"secondary"));
  append(summary,connectionItem(
   (user.name||user.username)+" ↔ "+source.name,
   "AVAN: "+(user.username||user.subject)+" · BPMS: "+(binding.external_username||"—"),
   {active:binding.status==="active",label:binding.status==="active"?"متصل":"نیازمند بررسی"},
   actions
  ));
 }
 await loadEditor();
}

const menu=[
 ["connections","وضعیت سامانه"],
 ["bpms","اتصالات BPMS"],
 ["userbpms","اتصال کاربران به BPMS"],
 ["agentdb","بانک Agent"],
 ["ai","هوش مصنوعی"],
 ["organization","سازمان و دسترسی"],
 ["appearance","تنظیمات ظاهری"],
 ["license","لایسنس"]
];

function settingsSubnav(items,active,onChange){
 const nav=node("nav","settings-subnav");
 nav.setAttribute("aria-label","زیرمجموعه تنظیمات");
 for(const [code,title] of items){
  const item=btn(title,()=>onChange(code),code===active?"active":"secondary");
  if(code===active)item.setAttribute("aria-current","page");
  append(nav,item);
 }
 return nav;
}

async function renderOrganizationHub(m){
 const items=[["company","سازمان‌ها"],["users","کاربران"]];
 if(state.orgSub==="identity")state.orgSub="users";
 append(m,settingsSubnav(items,state.orgSub,code=>{state.orgSub=code;showSettings("organization")}));
 if(state.orgSub==="company")await renderCompany(m);
 
 else await renderUsers(m);
}
async function showSettings(page=state.page){
 if(page==="mysql"||page==="processmaker")page="bpms";
 else if(page==="users"||page==="company"||page==="identity"){state.orgSub=page;page="organization"}

 const settings=await api("settings");state.settings=settings;state.page=page;
 const m=main();
 const hero=node("div","admin-hero"),heroTop=node("div","admin-hero-top");
 const heroText=node("div");
 append(heroText,node("span","eyebrow","AVAN · CONTROL CENTER"),
  node("h1","","مدیریت سامانه"),
  node("p","intro","هر تنظیم یک مالک دارد؛ راهنماها از فرم جدا شده‌اند و با آیکن لامپ در تب جدید باز می‌شوند."));
 append(heroTop,heroText,helpButton(helpTopicFor(page)));
 append(hero,heroTop);append(m,hero);

 const tabs=node("nav","tabs");tabs.setAttribute("aria-label","بخش‌های تنظیمات");
 for(const [code,title] of menu){
  const item=btn(title,()=>{state.bpmsEdit=null;showSettings(code)},state.page===code?"active":"");
  if(code===page)item.setAttribute("aria-current","page");append(tabs,item)
 }
 append(m,tabs);

 const contentHost=node("div","settings-page-content");
 contentHost.dataset.settingsPage=page;
 append(m,contentHost);
 try{
  if(page==="connections")await renderConnections(contentHost,settings);
  else if(page==="bpms")await renderBPMS(contentHost);
  else if(page==="userbpms")await renderUserBpmsBindings(contentHost);
  else if(page==="agentdb")await renderAgentDatabase(contentHost);
  else if(page==="ai")renderAI(contentHost,settings.ai||{});
  else if(page==="organization")await renderOrganizationHub(contentHost);
  else if(page==="appearance")await renderAppearance(contentHost);
  else if(page==="license")await renderLicense(contentHost,settings);
  else await renderConnections(contentHost,settings);
  if(!contentHost.children.length)throw Error("محتوای این بخش ساخته نشد.");
 }catch(err){
  contentHost.replaceChildren();
  const failure=panel("این بخش بارگذاری نشد",
    "فضای مدیریت سامانه فعال است، اما دریافت یا پردازش داده‌های این بخش ناموفق بود. صفحه سفید نمایش داده نمی‌شود.");
  failure.classList.add("settings-render-error");
  append(failure,info(err?.message||String(err)||"خطای نامشخص",true),
    btn("تلاش دوباره",()=>showSettings(page),"secondary"));
  append(contentHost,failure);
  console.error("AVAN_SETTINGS_RENDER_ERROR",page,err);
 }
}

function connectionItem(name,description,status,actions){
 const row=node("div","connection-card");
 const header=node("div","connection-card-head"),text=node("div","connection-info");
 append(text,node("strong","",name),node("p","hint",description));
 append(header,text,node("span","connection-pill "+(status.active?"is-active":"is-off"),status.label));
 append(row,header,actions);return row;
}
async function renderConnections(m,settings){
 const p=panel("وضعیت سامانه",
  "این صفحه فقط نمای سلامت و وضعیت پیکربندی است. هیچ اتصال یا Secret از اینجا ویرایش نمی‌شود؛ برای تغییر هر مورد وارد بخش مالک همان تنظیم شوید.");
 append(m,p);

 const [dbResult,bpmsResult,identityResult]=await Promise.allSettled([
  api("agent-db/connections"),api("bpms/catalog"),api("identity/status")
 ]);
 if(state.page!=="connections")return;

 const db=dbResult.status==="fulfilled"?dbResult.value:{active_id:null,connections:[]};
 const bpms=bpmsResult.status==="fulfilled"?bpmsResult.value:{connections:[]};
 const identity=identityResult.status==="fulfilled"?identityResult.value:null;
 const activeDb=db.connections.find(x=>x.id===db.active_id);
 const bpmsConnections=bpms.connections||[];
 const bpmsActive=bpmsConnections.filter(x=>x.connection_type==="processmaker"?x.active:x.enabled).length;

 const stats=node("div","connection-stats");
 const summary=[
  ["اتصالات BPMS",bpmsConnections.length?bpmsActive+" فعال از "+bpmsConnections.length:"ثبت‌نشده"],
  ["بانک Agent",activeDb?"فعال":"قطع"],
  ["هوش مصنوعی",settings.ai?.enabled?"فعال":"غیرفعال"],
  ["هویت",identity?.connected?"فعال":"نیازمند بررسی"]
 ];
 for(const [label,value] of summary){
  const card=node("div","connection-stat");append(card,node("small","",label),node("strong","",value));append(stats,card)
 }
 append(p,stats);

 if(dbResult.status==="rejected")append(p,info("وضعیت بانک Agent قابل دریافت نیست: "+dbResult.reason.message,true));
 if(bpmsResult.status==="rejected")append(p,info("وضعیت BPMSها قابل دریافت نیست: "+bpmsResult.reason.message,true));
 if(identityResult.status==="rejected")append(p,info("وضعیت هویت سازمانی قابل دریافت نیست.",true));

 const list=node("div","connection-list status-only-list");append(p,list);
 const statusRow=(title,description,active,label,target,onOpen)=>{
  const actions=node("div","connection-actions");
  const open=btn("مدیریت",onOpen||(()=>showSettings(target)),"secondary");
  append(actions,open);
  append(list,connectionItem(title,description,{active,label},actions));
 };

 const bpmsDescription=bpmsConnections.length
  ?bpmsConnections.map(x=>(x.engine==="processmaker"?"ProcessMaker":(x.engine||"BPMS"))+" · "+x.name).slice(0,4).join(" | ")
  :"هیچ اتصال BPMS ثبت نشده است.";
 statusRow("اتصالات BPMS",bpmsDescription,bpmsActive>0,
   bpmsConnections.length?(bpmsActive+" فعال"):"ثبت‌نشده","bpms",()=>showSettings("bpms"));

 statusRow("بانک اختصاصی Agent",
   activeDb?(activeDb.name+" · "+activeDb.server):(db.connections.length+" پروفایل ثبت‌شده · بدون اتصال فعال"),
   !!activeDb,activeDb?"فعال":"قطع","agentdb");

 statusRow("هوش مصنوعی",
   settings.ai?.model?settings.ai.model+" · "+(settings.ai.enabled?"فعال":"غیرفعال"):"کلید و مدل هنوز تنظیم نشده‌اند.",
   !!settings.ai?.enabled,settings.ai?.enabled?"فعال":(settings.ai?.api_key?"غیرفعال":"ثبت‌نشده"),"ai");

 statusRow("هویت و دسترسی سازمانی",
   identity?.connected?("Keycloak · Realm "+identity.realm):"هویت سازمانی هنوز آماده یا قابل بررسی نیست.",
   !!identity?.connected,identity?.connected?"فعال":"نیازمند بررسی","organization",
   ()=>{state.orgSub="users";showSettings("organization")});

 const noteBox=node("div","settings-clean-note");
 append(noteBox,node("strong","","قاعده مدیریت تنظیمات"),
  node("p","hint","هر Secret و اتصال فقط در یک صفحه ویرایش می‌شود. این Dashboard فقط وضعیت را نشان می‌دهد تا تنظیم تکراری یا متناقض ایجاد نشود."));
 append(p,noteBox);
}

function appearanceImageData(file){
 return new Promise((resolve,reject)=>{
  if(!file||!/^image\/(png|jpeg|webp)$/.test(file.type)){reject(Error("فقط PNG، JPG یا WebP مجاز است."));return}
  if(file.size>10*1024*1024){reject(Error("فایل اولیه باید کمتر از ۱۰ مگابایت باشد."));return}
  const url=URL.createObjectURL(file),img=new Image();
  img.onload=()=>{
   try{
    const maxW=1920,maxH=1080,scale=Math.min(1,maxW/img.naturalWidth,maxH/img.naturalHeight);
    const canvas=document.createElement("canvas");canvas.width=Math.max(1,Math.round(img.naturalWidth*scale));canvas.height=Math.max(1,Math.round(img.naturalHeight*scale));
    const ctx=canvas.getContext("2d");ctx.drawImage(img,0,0,canvas.width,canvas.height);
    canvas.toBlob(blob=>{
     URL.revokeObjectURL(url);
     if(!blob){reject(Error("تبدیل تصویر انجام نشد."));return}
     if(blob.size>5*1024*1024){reject(Error("تصویر پس از بهینه‌سازی هنوز بیش از ۵ مگابایت است."));return}
     const reader=new FileReader();reader.onload=()=>resolve(String(reader.result));reader.onerror=()=>reject(Error("خواندن تصویر انجام نشد."));reader.readAsDataURL(blob);
    },"image/webp",.88);
   }catch(err){URL.revokeObjectURL(url);reject(err)}
  };
  img.onerror=()=>{URL.revokeObjectURL(url);reject(Error("تصویر قابل خواندن نیست."))};img.src=url;
 });
}
function appearanceRange(title,value,min,max,step,suffix=""){
 const row=node("div","appearance-slider"),label=node("label","",title),input=node("input"),out=node("output");
 input.type="range";input.min=String(min);input.max=String(max);input.step=String(step);input.value=String(value);
 out.textContent=String(value)+suffix;input.addEventListener("input",()=>out.textContent=input.value+suffix);
 append(label,input);append(row,label,out);return {row,input,out};
}
async function renderAppearance(m){
 const p=panel("ویرایشگر کامل ظاهر صفحه ورود",
  "پس‌زمینه، کره، مدارها، Hover و تک‌تک Nodeها مستقل و قابل تنظیم‌اند. کارت اصلی Login و منطق امنیتی ورود از این Editor جدا نگه داشته شده‌اند.");
 append(m,p);
 const out=node("div"),config=await api("appearance");
 let background=config.background_image||"",globeImage=config.globe_image||"";
 const elements=(config.elements||[]).map(x=>({...x,tags:[...(x.tags||[])]}));
 const grid=node("div","appearance-grid");

 const range=(title,key,value,min,max,step,suffix="")=>{
  const r=appearanceRange(title,value,min,max,step,suffix);r.input.dataset.appearanceGlobal=key;return r;
 };
 const select=(title,key,items,value)=>{
  const s=selectField(title,key,items,value);s.querySelector("select").dataset.appearanceGlobal=key;return s;
 };
 const color=(title,key,value)=>{
  const w=field(title,key,value,{type:"color"});w.querySelector("input").dataset.appearanceGlobal=key;return w;
 };
 const check=(labelText,key,value)=>{
  const label=node("label"),input=node("input");input.type="checkbox";input.checked=!!value;input.dataset.appearanceGlobal=key;
  append(label,input,node("span","",labelText));return {label,input};
 };
 const imagePicker=(title,current,setter,preview,clearLabel)=>{
  const box=node("div","appearance-upload"),label=node("label","form-field"),caption=node("span","",title),input=node("input");
  input.type="file";input.accept="image/png,image/jpeg,image/webp";append(label,caption,input);append(box,label);
  input.addEventListener("change",async()=>{
   const file=input.files?.[0];if(!file)return;
   try{
    const data=await appearanceImageData(file);setter(data);preview.style.backgroundImage='url("'+data+'")';
    out.replaceChildren(info("تصویر آماده ذخیره است."));
   }catch(err){input.value="";showError(out,err)}
  });
  append(box,btn(clearLabel,()=>{setter("");preview.style.backgroundImage="";input.value=""},"secondary"));
  return box;
 };

 const intro=node("div","appearance-editor-summary");
 append(intro,
  node("strong","","Scene Editor V4"),
  node("span","","تمام مقادیر زیر در Store پایدار ذخیره و با Login سازمانی Keycloak همگام می‌شوند."),
  node("span","","حداکثر ۱۲ Node · SVG امن · تصاویر Raster تا ۵MB بعد از بهینه‌سازی"));
 append(p,intro);

 // Background
 const bg=node("section","appearance-card full");
 append(bg,node("h3","","۱. پس‌زمینه صفحه Login"),
  node("p","hint","تصویر، محل Crop، Fit، نور، رنگ، Blur، Overlay و Parallax جداگانه کنترل می‌شوند."));
 const bgPreview=node("div","appearance-preview appearance-preview-wide");
 if(background)bgPreview.style.backgroundImage='url("'+background.replaceAll('"','%22')+'")';
 append(bg,bgPreview,imagePicker("انتخاب تصویر پس‌زمینه",background,v=>background=v,bgPreview,"حذف تصویر و استفاده از پیش‌فرض"));
 const bgControls=node("div","appearance-control-grid");
 const bgFit=select("نوع نمایش تصویر","background_fit",[
  {value:"cover",label:"Cover · پر کردن صفحه"},{value:"contain",label:"Contain · نمایش کامل"},
  {value:"stretch",label:"Stretch · کشیده تا کل صفحه"},{value:"auto",label:"Auto · اندازه طبیعی"}
 ],config.background_fit||"cover");
 const bgX=range("موقعیت افقی تصویر","background_position_x",config.background_position_x??50,0,100,1,"%");
 const bgY=range("موقعیت عمودی تصویر","background_position_y",config.background_position_y??50,0,100,1,"%");
 const bgBright=range("روشنایی پس‌زمینه","background_brightness",config.background_brightness??1.12,.45,1.7,.05,"×");
 const bgContrast=range("Contrast پس‌زمینه","background_contrast",config.background_contrast??1.08,.5,1.8,.05,"×");
 const bgSat=range("Saturation پس‌زمینه","background_saturation",config.background_saturation??1.08,0,2,.05,"×");
 const bgBlur=range("Blur پس‌زمینه","background_blur",config.background_blur??0,0,20,.5,"px");
 const bgDim=range("Dark layer","background_dim",config.background_dim??.03,0,.8,.02);
 const overlayColor=color("رنگ Overlay","overlay_color",config.overlay_color||"#031522");
 const overlayOpacity=range("شدت Overlay رنگی","overlay_opacity",config.overlay_opacity??.05,0,.8,.02);
 const bgParallax=range("مقدار Parallax با حرکت Mouse","background_parallax",config.background_parallax??6,0,30,1,"px");
 append(bgControls,bgFit,bgX.row,bgY.row,bgBright.row,bgContrast.row,bgSat.row,bgBlur.row,bgDim.row,overlayColor,overlayOpacity.row,bgParallax.row);
 append(bg,bgControls);

 // Globe
 const globe=node("section","appearance-card full");
 append(globe,node("h3","","۲. کره و شبکه هوشمند"),
  node("p","hint","کره دیگر بخشی از عکس Background نیست؛ موقعیت، تصویر، نور، چرخش و نقاط شبکه مستقل‌اند."));
 const globePreview=node("div","appearance-globe-preview");
 if(globeImage)globePreview.style.backgroundImage='url("'+globeImage.replaceAll('"','%22')+'")';
 const globeVisible=check("نمایش کره", "globe_visible", config.globe_visible!==false);
 append(globe,globePreview,globeVisible.label,imagePicker("تصویر سفارشی کره؛ در صورت خالی بودن Sprite آوان استفاده می‌شود",globeImage,v=>globeImage=v,globePreview,"بازگشت به کره پیش‌فرض"));
 const globeControls=node("div","appearance-control-grid");
 const globeX=range("موقعیت افقی مرکز کره","globe_x",config.globe_x??29,8,60,.5,"%");
 const globeY=range("موقعیت عمودی مرکز کره","globe_y",config.globe_y??44,18,82,.5,"%");
 const globeScale=range("اندازه کره","globe_scale",config.globe_scale??1.22,.55,1.85,.05,"×");
 const globeOpacity=range("Opacity کره","globe_opacity",config.globe_opacity??1,0,1,.05);
 const globeBright=range("روشنایی کره","globe_brightness",config.globe_brightness??1.32,.5,2,.05,"×");
 const globeContrast=range("Contrast کره","globe_contrast",config.globe_contrast??1.1,.5,1.8,.05,"×");
 const globeSat=range("Saturation کره","globe_saturation",config.globe_saturation??1.22,0,2,.05,"×");
 const globeHue=range("Hue Rotate کره","globe_hue",config.globe_hue??0,-180,180,5,"°");
 const globeGlow=range("Glow کره","globe_glow",config.globe_glow??1.3,0,2.5,.05,"×");
 const globeWobble=range("شدت حرکت آرام کره","globe_wobble",config.globe_wobble??1,0,2,.05,"×");
 const globeRotation=range("سرعت چرخش شبکه کره","globe_rotation_speed",config.globe_rotation_speed??1,0,3,.1,"×");
 const pointDensity=range("تراکم نقاط شبکه","globe_point_density",config.globe_point_density??1,.5,2.5,.1,"×");
 const pointSize=range("اندازه نقاط شبکه","globe_point_size",config.globe_point_size??1,.5,2.5,.1,"×");
 const pointOpacity=range("Opacity نقاط شبکه","globe_point_opacity",config.globe_point_opacity??1,.1,1,.05);
 append(globeControls,globeX.row,globeY.row,globeScale.row,globeOpacity.row,globeBright.row,globeContrast.row,globeSat.row,globeHue.row,
  globeGlow.row,globeWobble.row,globeRotation.row,pointDensity.row,pointSize.row,pointOpacity.row);
 append(globe,globeControls);

 // Global node/orbit/hover
 const behavior=node("section","appearance-card full");
 append(behavior,node("h3","","۳. مدارها، Nodeها و رفتار Hover"),
  node("p","hint","این مقادیر Default کل Scene هستند؛ هر Node پایین‌تر می‌تواند اندازه، Hover و مسیر خودش را Override کند."));
 const behaviorControls=node("div","appearance-control-grid");
 const nodeSize=range("اندازه پیش‌فرض Node","node_size",config.node_size??70,40,110,1,"px");
 const nodeOpacity=range("Opacity همه Nodeها","node_opacity",config.node_opacity??1,.25,1,.05);
 const nodeBorder=range("ضخامت Border Node","node_border_width",config.node_border_width??1,0,4,.1,"px");
 const nodeGlow=range("Glow عمومی Node","node_glow",config.node_glow??1,0,2.5,.05,"×");
 const hoverScale=range("بزرگ‌شدن پیش‌فرض Hover","hover_scale",config.hover_scale??1.24,1,1.8,.05,"×");
 const hoverDuration=range("مدت Animation Hover","hover_duration",config.hover_duration??180,0,1200,20,"ms");
 const hover=select("رفتار Hover","hover_mode",[
  {value:"card",label:"Card · عنوان + توضیح + Tag"},
  {value:"tooltip",label:"Tooltip کامل و شناور"},
  {value:"label",label:"فقط عنوان"},
  {value:"glow",label:"فقط Glow و بزرگ‌شدن"},
  {value:"none",label:"بدون واکنش Hover"}
 ],config.hover_mode||"card");
 const orbitMode=select("نحوه حرکت عناصر","orbit_mode",[{value:"drift",label:"شناوری آرام در جایگاه‌ها"},{value:"orbit",label:"گردش کامل دور کره"},{value:"static",label:"ثابت"}],config.orbit_mode||"orbit");
 const orbitSpeed=range("سرعت کلی حرکت Nodeها","orbit_speed",config.orbit_speed??.22,0,3,.1,"×");
 const orbitWidth=range("ضخامت خطوط مدار","orbit_line_width",config.orbit_line_width??1.15,.2,4,.1,"px");
 const orbitOpacity=range("Opacity خطوط مدار","orbit_opacity",config.orbit_opacity??.78,0,1,.05);
 const orbitGlow=range("Glow خطوط مدار","orbit_glow",config.orbit_glow??1,0,2.5,.05,"×");
 const orbitPrimary=color("رنگ اصلی مدار","orbit_primary",config.orbit_primary||"#50EAF7");
 const orbitSecondary=color("رنگ دوم مدار","orbit_secondary",config.orbit_secondary||"#FF7053");
 const cardWidth=range("عرض کارت توضیح","card_width",config.card_width??176,120,320,5,"px");
 const cardOpacity=range("Opacity کارت توضیح","card_opacity",config.card_opacity??.94,.35,1,.05);
 append(behaviorControls,nodeSize.row,nodeOpacity.row,nodeBorder.row,nodeGlow.row,hoverScale.row,hoverDuration.row,hover,
  orbitMode,orbitSpeed.row,orbitWidth.row,orbitOpacity.row,orbitGlow.row,orbitPrimary,orbitSecondary,cardWidth.row,cardOpacity.row);
 const behaviorChecks=node("div","appearance-checks");
 const pause=check("توقف همان Node هنگام Hover","pause_on_hover",config.pause_on_hover!==false);
 const orbits=check("نمایش خطوط مدار","show_orbits",config.show_orbits!==false);
 const idleCards=check("نمایش کم‌رنگ Card حتی بدون Hover","show_idle_cards",!!config.show_idle_cards);
 append(behaviorChecks,pause.label,orbits.label,idleCards.label);append(behavior,behaviorControls,behaviorChecks);

 // Elements
 const elementSection=node("section","appearance-card full");
 const head=node("div","section-head"),headText=node("div");
 append(headText,node("h3","","۴. تنظیم مستقل هر المان چرخان"),
  node("p","hint","ترتیب، SVG، متن، Tag، اندازه، Hover، Glow، Opacity، شعاع/کشیدگی/زاویه/سرعت مدار و محل Card برای هر Node مستقل است."));
 const addBtn=btn("＋ افزودن Node",()=>{
  if(elements.length>=12){out.replaceChildren(info("حداکثر ۱۲ Node قابل تعریف است.",true));return}
  captureElements();
  elements.push({id:"custom_"+Date.now(),enabled:true,title:"قابلیت جدید",subtitle:"توضیح کوتاه",description:"توضیح کامل قابلیت",tags:["AVAN"],accent:"#63ECFF",
    radius:1.25,ellipse:.7,angle:Math.random()*6.2,speed:.00015,size:0,hover_scale:0,glow:1,opacity:1,card_side:"auto",label_mode:"inherit",
    svg:'<svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="7"/><path d="M12 8v8M8 12h8"/></svg>'});
  drawElements();
 },"secondary");
 append(head,headText,addBtn);append(elementSection,head);
 const elementsHost=node("div","appearance-elements");append(elementSection,elementsHost);

 const mkInput=(labelText,value,fieldName,opts={})=>{
  const wrap=node("label","form-field"),label=node("span","",labelText),input=node(opts.multiline?"textarea":"input");
  input.dataset.appearanceField=fieldName;if(!opts.multiline)input.type=opts.type||"text";input.value=value??"";
  if(opts.min!==undefined)input.min=String(opts.min);if(opts.max!==undefined)input.max=String(opts.max);if(opts.step!==undefined)input.step=String(opts.step);
  if(opts.placeholder)input.placeholder=opts.placeholder;append(wrap,label,input);return {wrap,input};
 };
 const mkSelect=(labelText,value,fieldName,items)=>{
  const wrap=node("label","form-field"),label=node("span","",labelText),sel=node("select");sel.dataset.appearanceField=fieldName;
  items.forEach(([v,t])=>{const o=node("option","",t);o.value=v;if(v===value)o.selected=true;sel.append(o)});append(wrap,label,sel);return {wrap,input:sel};
 };
 function captureElements(){
  for(const card of elementsHost.querySelectorAll(".appearance-element")){
   const item=elements[Number(card.dataset.index)];if(!item)continue;
   for(const input of card.querySelectorAll("[data-appearance-field]")){
    const key=input.dataset.appearanceField;
    item[key]=input.type==="checkbox"?input.checked:input.type==="number"?Number(input.value):key==="tags"?input.value.split(",").map(x=>x.trim()).filter(Boolean):input.value;
   }
  }
 }
 function drawElements(){
  elementsHost.replaceChildren();
  elements.forEach((item,index)=>{
   const card=node("article","appearance-element");card.dataset.index=String(index);
   const h=node("div","appearance-element-head"),identity=node("div","appearance-element-identity"),sample=node("span","appearance-svg-sample");
   const svgPreview=node("img");svgPreview.alt="";svgPreview.src="data:image/svg+xml,"+encodeURIComponent(item.svg||"");sample.append(svgPreview);
   const enabled=node("input");enabled.type="checkbox";enabled.checked=item.enabled!==false;enabled.dataset.appearanceField="enabled";
   const enabledLabel=node("label");append(enabledLabel,enabled,node("strong","",item.title||("Node "+(index+1))));
   append(identity,node("span","appearance-order",String(index+1)),enabledLabel);
   const actions=node("div","actions");
   append(actions,
    btn("↑",()=>{if(index>0){captureElements();[elements[index-1],elements[index]]=[elements[index],elements[index-1]];drawElements()}},"secondary"),
    btn("↓",()=>{if(index<elements.length-1){captureElements();[elements[index+1],elements[index]]=[elements[index],elements[index+1]];drawElements()}},"secondary"),
    btn("کپی",()=>{if(elements.length<12){captureElements();const copy=structuredClone(elements[index]);copy.id="copy_"+Date.now();copy.title+=" · کپی";elements.splice(index+1,0,copy);drawElements()}},"secondary"),
    btn("حذف",()=>{captureElements();elements.splice(index,1);drawElements()},"secondary"));
   append(h,identity,sample,actions);append(card,h);
   const controls=node("div","appearance-element-controls");
   const title=mkInput("عنوان",item.title,"title"),subtitle=mkInput("متن کوتاه",item.subtitle,"subtitle"),
    tags=mkInput("Tagها؛ با کاما جدا کن",(item.tags||[]).join(", "), "tags"),
    accent=mkInput("رنگ اختصاصی",item.accent||"#63ECFF","accent",{type:"color"}),
    size=mkInput("اندازه Node؛ ۰ یعنی Default",item.size??0,"size",{type:"number",min:0,max:110,step:1}),
    hscale=mkInput("Hover Scale؛ ۰ یعنی Default",item.hover_scale??0,"hover_scale",{type:"number",min:0,max:1.85,step:.05}),
    glow=mkInput("Glow اختصاصی",item.glow??1,"glow",{type:"number",min:0,max:2.5,step:.05}),
    opacity=mkInput("Opacity Node",item.opacity??1,"opacity",{type:"number",min:.25,max:1,step:.05}),
    radius=mkInput("شعاع مدار",item.radius??1.25,"radius",{type:"number",min:.75,max:1.95,step:.01}),
    ellipse=mkInput("کشیدگی عمودی مدار",item.ellipse??.7,"ellipse",{type:"number",min:.35,max:1,step:.01}),
    angle=mkInput("زاویه شروع؛ رادیان",item.angle??0,"angle",{type:"number",min:-20,max:20,step:.01}),
    speed=mkInput("سرعت/جهت؛ منفی = برعکس",item.speed??.00015,"speed",{type:"number",min:-.001,max:.001,step:.00001}),
    cardSide=mkSelect("محل Card",item.card_side||"auto","card_side",[["auto","خودکار"],["left","چپ"],["right","راست"],["top","بالا"],["bottom","پایین"]]),
    labelMode=mkSelect("نمایش Label",item.label_mode||"inherit","label_mode",[["inherit","طبق تنظیم Hover"],["always","همیشه"],["hover","فقط Hover"],["hidden","مخفی"]]),
    desc=mkInput("توضیح کامل Tooltip",item.description,"description",{multiline:true}),
    svg=mkInput("کد SVG آیکن",item.svg,"svg",{multiline:true});
   desc.wrap.classList.add("full");svg.wrap.classList.add("full");
   const svgFileWrap=node("label","form-field full"),svgFileTitle=node("span","","یا فایل SVG انتخاب کن"),svgFile=node("input");
   svgFile.type="file";svgFile.accept=".svg,image/svg+xml";
   svgFile.addEventListener("change",async()=>{
    const file=svgFile.files?.[0];if(!file)return;
    if(file.size>30*1024){svgFile.value="";out.replaceChildren(info("فایل SVG باید کمتر از ۳۰KB باشد.",true));return}
    try{const raw=await file.text();if(!/<svg(?:\s|>)/i.test(raw))throw Error("فایل SVG معتبر نیست.");svg.input.value=raw;svg.input.dispatchEvent(new Event("input",{bubbles:true}));out.replaceChildren(info("SVG وارد شد. پیش‌نمایش آیکن بعد از ذخیره و Sanitise شدن توسط Backend به‌روز می‌شود."))}
    catch(err){svgFile.value="";showError(out,err)}
   });
   append(svgFileWrap,svgFileTitle,svgFile);
   append(controls,title.wrap,subtitle.wrap,tags.wrap,accent.wrap,size.wrap,hscale.wrap,glow.wrap,opacity.wrap,radius.wrap,ellipse.wrap,angle.wrap,speed.wrap,
    cardSide.wrap,labelMode.wrap,desc.wrap,svg.wrap,svgFileWrap);append(card,controls);elementsHost.append(card);
  });
 }
 drawElements();

 append(grid,bg,globe,behavior,elementSection);append(p,grid);

 const getGlobal=key=>p.querySelector('[data-appearance-global="'+key+'"]');
 const n=key=>Number(getGlobal(key)?.value);
 const b=key=>!!getGlobal(key)?.checked;
 const v=key=>getGlobal(key)?.value||"";
 const actions=node("div","appearance-actions");
 append(actions,
  btn("ذخیره همه تنظیمات ظاهری",async()=>{
   const savedElements=[...elementsHost.querySelectorAll(".appearance-element")].map((card,index)=>{
    const val=name=>card.querySelector('[data-appearance-field="'+name+'"]'),original=elements[index]||{};
    return {id:original.id||("custom_"+index),enabled:!!val("enabled")?.checked,title:val("title")?.value.trim()||"قابلیت",
     subtitle:val("subtitle")?.value.trim()||"",description:val("description")?.value.trim()||"",
     tags:(val("tags")?.value||"").split(",").map(x=>x.trim()).filter(Boolean).slice(0,8),
     svg:val("svg")?.value.trim()||original.svg,accent:val("accent")?.value||"#63ECFF",
     size:Number(val("size")?.value||0),hover_scale:Number(val("hover_scale")?.value||0),glow:Number(val("glow")?.value||1),opacity:Number(val("opacity")?.value||1),
     radius:Number(val("radius")?.value||1.25),ellipse:Number(val("ellipse")?.value||.7),angle:Number(val("angle")?.value||0),speed:Number(val("speed")?.value||.00015),
     card_side:val("card_side")?.value||"auto",label_mode:val("label_mode")?.value||"inherit"};
   });
   const payload={version:5,background_image:background,background_fit:v("background_fit"),background_position_x:n("background_position_x"),background_position_y:n("background_position_y"),
    background_brightness:n("background_brightness"),background_contrast:n("background_contrast"),background_saturation:n("background_saturation"),background_blur:n("background_blur"),
    background_dim:n("background_dim"),overlay_color:v("overlay_color"),overlay_opacity:n("overlay_opacity"),background_parallax:n("background_parallax"),
    globe_image:globeImage,globe_visible:b("globe_visible"),globe_x:n("globe_x"),globe_y:n("globe_y"),globe_scale:n("globe_scale"),globe_opacity:n("globe_opacity"),
    globe_brightness:n("globe_brightness"),globe_contrast:n("globe_contrast"),globe_saturation:n("globe_saturation"),globe_hue:n("globe_hue"),globe_glow:n("globe_glow"),
    globe_wobble:n("globe_wobble"),globe_rotation_speed:n("globe_rotation_speed"),globe_point_density:n("globe_point_density"),globe_point_size:n("globe_point_size"),globe_point_opacity:n("globe_point_opacity"),
    node_size:n("node_size"),node_opacity:n("node_opacity"),node_border_width:n("node_border_width"),node_glow:n("node_glow"),hover_scale:n("hover_scale"),hover_duration:n("hover_duration"),
    hover_mode:v("hover_mode"),pause_on_hover:b("pause_on_hover"),login_auto_collapse:false,show_orbits:b("show_orbits"),show_idle_cards:b("show_idle_cards"),orbit_speed:n("orbit_speed"),orbit_mode:v("orbit_mode"),
    orbit_line_width:n("orbit_line_width"),orbit_opacity:n("orbit_opacity"),orbit_glow:n("orbit_glow"),orbit_primary:v("orbit_primary"),orbit_secondary:v("orbit_secondary"),
    card_width:n("card_width"),card_opacity:n("card_opacity"),elements:savedElements};
   out.replaceChildren();
   try{
    const result=await api("appearance/save",payload);
    out.replaceChildren(info(result.identity_theme_synced?"ظاهر V4 ذخیره شد و Keycloak نیز همگام شد. برای دیدن نتیجه Login را با Ctrl+F5 باز کن.":"ظاهر V4 ذخیره شد؛ همگام‌سازی فایل عمومی Keycloak در این اجرا انجام نشد."));
   }catch(err){showError(out,err)}
  }),
  btn("بازگردانی کامل ظاهر پیشنهادی آوان",async()=>{
   if(!confirm("تمام تنظیمات Scene، Background، Globe و Nodeها به پیش‌فرض V4 برگردد؟"))return;
   try{await api("appearance/reset",{});await showSettings("appearance")}catch(err){showError(out,err)}
  },"secondary"),out);
 append(p,actions);
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
 const p=panel("کاربران","");append(m,p);
 const toolbar=node("div","actions"),feedback=node("div"),createHost=node("div");
 append(toolbar,btn("افزودن کاربر",()=>openCreate()),btn("به‌روزرسانی",()=>showSettings("users"),"secondary"));
 append(p,toolbar,feedback,createHost);
 const search=node("input");search.type="search";search.placeholder="جست‌وجوی نام یا نام کاربری";search.setAttribute("aria-label","جست‌وجوی کاربران");append(p,search);
 const results=await Promise.allSettled([api("users/mapped"),api("user-bindings/sources"),api("license/status"),api("identity/status"),api("users/identities"),api("users/pending"),api("company")]);
 const value=i=>results[i].status==="fulfilled"?results[i].value:{};
 const mapped=value(0).users||[],sources=value(1).sources||[],licensedModules=value(2).valid?(value(2).modules||[]):[],status=value(3),pending=value(5).pending||[],company=value(6);
 for(const i of [0,1,2,3,4,5,6])if(results[i].status==="rejected")append(feedback,info(results[i].reason.message,true));
 if(value(4).truncated)append(feedback,info("فهرست کاربران بیش از حد مجاز است؛ همه نتایج نمایش داده نشده‌اند.",true));
 const accounts=node("div","connection-list");append(p,accounts);
 let activeEditor=null;
 function open(host,render){if(activeEditor)activeEditor.replaceChildren();activeEditor=host;host.replaceChildren();render()}
 function close(host){host.replaceChildren();if(activeEditor===host)activeEditor=null}
 function saveForm(host,fields,submit){
  const form=node("form","grid"),out=node("div","full");append(form,fields);
  const save=node("button","","ذخیره");save.type="submit";append(form,save,btn("انصراف",()=>close(host),"secondary"),out);append(host,form);
  form.addEventListener("submit",async e=>{e.preventDefault();busy(form,true);try{const result=await submit(form);close(host);if(result!==false)await showSettings("users")}catch(err){showError(out,err)}finally{busy(form,false)}});return form;
 }
 const raw=(form,name)=>form.elements.namedItem(name).value;
 function openCreate(){open(createHost,()=>saveForm(createHost,[
  field("نام کاربری","username"),
  field("نام و نام خانوادگی","name"),
  field("ایمیل","email","",{type:"email"}),
  field("رمز ورود؛ حداقل ۱۶ نویسه","password","",{secret:true}),
  field("تکرار رمز ورود","repeat","",{secret:true}),
  selectField("نقش","role",[{value:"Expert",label:"کارشناس"},{value:"Manager",label:"مدیر"},{value:"SysAdmin",label:"مدیر سیستم"}],"Expert")
 ],async f=>{
  const password=raw(f,"password");
  if(password!==raw(f,"repeat"))throw Error("تکرار رمز ورود یکسان نیست.");
  await api("users/create-identity",{
   username:formValue(f,"username"),
   name:formValue(f,"name"),
   email:formValue(f,"email"),
   role:formValue(f,"role"),
   temporary_password:password
  });
 }))}

 function edit(user,host,passwordOnly){open(host,()=>{
  const local=user.local,fields=[];
  if(!passwordOnly){fields.push(field("نام کاربری","username",user.username));if(!local)fields.push(field("نام و نام خانوادگی","name",user.name),field("ایمیل","email",user.email,{type:"email"}))}
  if(local)fields.push(field("رمز فعلی","current","",{secret:true}),field("کد Authenticator","otp"));
  if(passwordOnly)fields.push(field("رمز جدید؛ حداقل ۱۶ نویسه","password","",{secret:true}),field("تکرار رمز جدید","repeat","",{secret:true}));
  saveForm(host,fields,async f=>{
   const password=passwordOnly?raw(f,"password"):"";
   if(passwordOnly&&password!==raw(f,"repeat"))throw Error("تکرار رمز یکسان نیست.");
   if(local){await api("identity/godadmin-credentials",{username:passwordOnly?user.username:formValue(f,"username"),current:raw(f,"current"),updated:password,otp:formValue(f,"otp")});window.location.assign("/admin/");return false}
   if(passwordOnly)await api("users/password",{subject:user.subject,password});
   else await api("users/profile",{subject:user.subject,username:formValue(f,"username"),name:formValue(f,"name"),email:formValue(f,"email")});
  });
 })}
 const moduleLabels={
  1:"جلسات و دستیار",
  2:"دبیر هوشمند",
  3:"BI و گزارش",
  4:"هشدار و پیگیری"
 };
 const moduleSelector=(selected,namePrefix="module")=>{
  const wrap=node("div","module-permission-grid");
  const chosen=new Set(selected||[]);
  for(const id of licensedModules){
   const label=node("label","module-permission-option");
   const input=node("input");input.type="checkbox";input.value=String(id);
   input.dataset.moduleId=String(id);input.name=namePrefix+"_"+id;input.checked=chosen.has(id);
   append(label,input,node("span","",moduleLabels[id]||("ماژول "+id)));append(wrap,label);
  }
  if(!licensedModules.length)append(wrap,node("span","hint","هیچ ماژول فعالی در لایسنس سازمان وجود ندارد."));
  return wrap;
 };
 const selectedModules=host=>[...host.querySelectorAll("input[data-module-id]:checked")]
   .map(x=>Number(x.dataset.moduleId)).filter(x=>Number.isInteger(x));

 const reasonLabel=reason=>({
  username_exact:"نام کاربری یکسان",
  email_exact:"ایمیل تأییدشده یکسان",
  display_name_similar:"نام مشابه"
 }[reason]||"پیشنهاد سیستم");

 async function renderBindingEditor(host,user,source,current){
  host.replaceChildren(info("در حال خواندن فهرست کاربران «"+source.name+"»…"));
  try{
   const data=await api("user-bindings/directory?subject="+encodeURIComponent(user.subject)+
                        "&source_id="+encodeURIComponent(source.id));
   host.replaceChildren();
   const suggestions=data.suggestions||[],users=(data.users||[]).filter(x=>x.active);
   if(suggestions.length){
    const suggestion=panel("پیشنهاد آوان",
      "این پیشنهاد فقط برای کمک به مدیر است و به‌صورت خودکار Binding ایجاد نمی‌کند.");
    for(const candidate of suggestions.slice(0,3)){
     const row=node("div","binding-suggestion");
     append(row,
      node("strong","",candidate.display_name+" · "+candidate.username),
      node("span","hint",reasonLabel(candidate.reason)+" · امتیاز "+candidate.score),
      btn("انتخاب این کاربر",()=>{
       const select=host.querySelector("select[name=external_user_id]");
       if(select){select.value=candidate.external_user_id;select.dataset.suggestedReason=candidate.reason}
      },"secondary"));
     append(suggestion,row);
    }
    append(host,suggestion);
   }
   const form=node("form","grid binding-editor");
   const label=node("label","full","کاربر متناظر در "+source.name);
   const select=node("select");select.name="external_user_id";
   const empty=node("option","",users.length?"انتخاب کاربر BPMS":"کاربر فعال در این BPMS یافت نشد");
   empty.value="";append(select,empty);
   for(const ext of users){
    const suffix=[ext.email,ext.unit].filter(Boolean).join(" · ");
    const opt=node("option","",ext.display_name+" · "+ext.username+(suffix?" · "+suffix:""));
    opt.value=ext.external_user_id;append(select,opt);
   }
   if(current&&users.some(x=>x.external_user_id===current.external_user_id)){
    select.value=current.external_user_id;
   }else if(suggestions[0]){
    select.value=suggestions[0].external_user_id;
    select.dataset.suggestedReason=suggestions[0].reason;
   }
   append(label,select);append(form,label);
   const out=node("div","full");
   append(form,
    btn(current?"ذخیره تغییر اتصال":"اتصال کاربر",async()=>{
     out.replaceChildren();
     const external=select.value;if(!external){showError(out,Error("یک کاربر BPMS انتخاب کنید."));return}
     const suggested=suggestions.find(x=>x.external_user_id===external);
     const method=suggested?
       (suggested.reason==="username_exact"?"username_suggestion":
        suggested.reason==="email_exact"?"email_suggestion":
        "display_name_suggestion"):"manual";
     try{
      await api("user-bindings/bind",{
       subject:user.subject,source_id:source.id,
       external_user_id:external,match_method:method
      });
      append(out,info("اتصال ذخیره شد."));
      await showSettings("users");
     }catch(err){showError(out,err)}
    }),
    btn("انصراف",()=>host.replaceChildren(),"secondary"),out);
   append(host,form);
  }catch(err){host.replaceChildren();showError(host,err)}
 }


 async function buildAccess(card,user){
  append(card,btn("بستن",()=>close(card),"secondary"));
  const permissionBox=node("div","avan-module-permissions");
  append(permissionBox,node("h3","","مجوزهای ماژول AVAN"),
   node("p","hint","این مجوزها مستقل از BPMS هستند و فقط می‌توانند زیرمجموعه ماژول‌های فعال لایسنس سازمان باشند."));
  const initialModules=user.module_permissions==null?licensedModules:user.module_permissions;
  const permissionOptions=moduleSelector(initialModules,"user_module");
  const permissionOut=node("div");
  append(permissionBox,permissionOptions,
   btn("ذخیره مجوزهای AVAN",async()=>{
    permissionOut.replaceChildren();
    try{
     await api("users/modules",{subject:user.subject,modules:selectedModules(permissionOptions)});
     append(permissionOut,info("مجوزهای AVAN ذخیره شد."));
     await showSettings("users");
    }catch(err){showError(permissionOut,err)}
   },"secondary"),permissionOut);
  append(card,permissionBox);

  const bindingTitle=node("div","section-head"),bindingHost=node("div","bpms-binding-list");
  append(bindingTitle,node("h3","","اتصال به BPMSها"),
   node("span","hint","هر BPMS یک Binding مستقل دارد."));
  append(card,bindingTitle,bindingHost);
  let existing=[];
  try{existing=(await api("user-bindings/list?subject="+encodeURIComponent(user.subject))).bindings||[]}
  catch(err){append(bindingHost,info(err.message,true));return}

  for(const source of sources){
   const current=existing.find(x=>x.source_id===source.id);
   const row=node("div","bpms-binding-card"),head=node("div","connection-card-head");
   const text=node("div","connection-info");
   append(text,node("strong","",source.name),
    node("p","hint",(source.engine||source.connection_type)+" · "+
      (current
       ?("متصل به "+(current.external_display_name||current.external_username||current.external_user_id)+
         " · "+(current.status==="active"?"فعال":"نیازمند بازبینی"))
       :"بدون اتصال")));
   const badge=node("span","connection-pill"+(current?.status==="active"?" is-active":""),
    current?(current.status==="active"?"متصل":"نیازمند بررسی"):"بدون اتصال");
   append(head,text,badge);append(row,head);
   const actions=node("div","connection-actions"),editor=node("div","binding-inline-editor");
   append(actions,
    btn(current?"تغییر کاربر BPMS":"انتخاب کاربر BPMS",
      ()=>renderBindingEditor(editor,user,source,current),"secondary"),
    btn("همگام‌سازی",async()=>{
     editor.replaceChildren();
     try{
      const r=await api("user-bindings/refresh",{source_id:source.id});
      append(editor,info("دایرکتوری "+r.directory_users+" کاربر · Binding فعال "+r.active_bindings+
       " · نیازمند بررسی "+r.stale_bindings));
     }catch(err){showError(editor,err)}
    },"secondary"));
   if(current)append(actions,btn("قطع اتصال",async()=>{
    if(!confirm("اتصال این کاربر AVAN به «"+source.name+"» قطع شود؟"))return;
    try{await api("user-bindings/unbind",{subject:user.subject,source_id:source.id});await showSettings("users")}
    catch(err){showError(editor,err)}
   },"secondary danger"));
   append(row,actions,editor);append(bindingHost,row);
  }
  if(!sources.length)append(bindingHost,info("هنوز BPMS ثبت نشده است. ابتدا از تب «اتصالات BPMS» یک اتصال ایجاد کنید."));

 }
 const all=new Map();
 for(const u of pending)all.set(u.subject,{...u,pending:true});
 for(const u of mapped)all.set(u.subject,{...(all.get(u.subject)||{}),...u,approved:true});
 for(const u of value(4).users||[])all.set(u.subject,{...(all.get(u.subject)||{}),...u});
 if(status.godadmin_local)all.set("local-godadmin",{subject:"local-godadmin",username:status.godadmin_username||"godadmin",name:"GodAdmin",enabled:true,local:true});
 const rows=[...all.values()].sort((a,b)=>Number(!!b.local)-Number(!!a.local));
 for(const user of rows){
  const card=panel(user.name||user.username,user.username||""),actions=node("div","actions"),host=node("div","editor-slot");
  card.classList.add("avan-user-card");
  card.dataset.search=[user.username,user.name,user.email].filter(Boolean).join(" ").toLowerCase();
  append(card,node("span","connection-pill",user.local?"مدیر سامانه":user.approved?(user.enabled?"فعال":"غیرفعال"):user.pending?"در انتظار تأیید":"ورود اولیه انجام نشده"));
  append(actions,btn("ویرایش",()=>edit(user,host,false),"secondary"),btn("تغییر رمز",()=>edit(user,host,true),"secondary"));
  if(user.approved&&!user.local){
   append(actions,btn("دسترسی‌ها",()=>open(host,()=>buildAccess(host,user)),"secondary"),btn(user.enabled?"غیرفعال‌کردن":"فعال‌کردن",async()=>{try{await api("users/enabled",{subject:user.subject,enabled:!user.enabled});await showSettings("users")}catch(err){showError(feedback,err)}},"secondary"));
  }else if(user.pending&&!user.local){
   append(actions,btn("فعال‌سازی",()=>open(host,()=>{
    const options=moduleSelector(licensedModules,"approval_module");
    saveForm(host,[selectField("نقش","role",[{value:"Expert",label:"کارشناس"},{value:"Manager",label:"مدیر"},...((user.roles||[]).includes("SysAdmin")?[{value:"SysAdmin",label:"مدیر سیستم"}]:[])],"Expert"),field("واحد","department_name","",{required:false}),options],f=>api("users/approve",{tenant_id:user.tenant_id,subject:user.subject,company_name:company.company_name,role:formValue(f,"role"),department_name:formValue(f,"department_name")||null,manager_subject:null,modules:selectedModules(options)}));
   }),"secondary"));
  }
  if(!user.local&&user.subject!==status.godadmin_subject)append(actions,btn("حذف کاربر",()=>open(host,()=>{
   const form=node("form","grid"),out=node("div","full"),remove=node("button","danger","حذف قطعی کاربر");remove.type="submit";
   append(form,info("حساب «"+(user.username||user.name)+"» و دسترسی‌های AVAN و اتصال‌های BPMS آن حذف می‌شوند. سوابق فرایندها باقی می‌مانند."),remove,btn("انصراف",()=>close(host),"secondary"),out);append(host,form);
   form.addEventListener("submit",async e=>{e.preventDefault();busy(form,true);try{await api("users/delete",{subject:user.subject});close(host);await showSettings("users")}catch(err){showError(out,err)}finally{busy(form,false)}});
  }),"secondary danger"));
  append(card,actions,host);append(accounts,card);
 }
 if(!rows.length)append(accounts,info("کاربری ثبت نشده است."));
 search.addEventListener("input",()=>{const q=search.value.trim().toLowerCase();for(const row of accounts.children)row.hidden=!!q&&!String(row.dataset.search||"").includes(q)});
}
async function renderBPMS(m){
 const section=panel("اتصالات BPMS",
  "ProcessMaker و سایر موتورهای BPMS از همین فهرست مدیریت می‌شوند. نوع اتصال را انتخاب کنید؛ فرم بر اساس موتور انتخاب‌شده تغییر می‌کند.");
 append(m,section);
 const loading=info("در حال دریافت فهرست اتصالات BPMS…");
 append(section,loading);
 let data;
 try{
  data=await api("bpms/catalog");
  loading.remove();
 }catch(err){
  loading.remove();
  append(section,info("فهرست اتصالات BPMS قابل دریافت نیست: "+(err?.message||String(err)),true),
    btn("تلاش دوباره",()=>showSettings("bpms"),"secondary"));
  return;
 }
 const head=node("div","section-head"),headActions=node("div","actions"),headText=node("div");
 append(headText,node("h3","","اتصال‌های ثبت‌شده"),
   node("span","connection-count",(data.connections||[]).length+" اتصال"));
 append(head,headText);
 const editor=node("div","editor-slot");
 const help=helpButton("bpms","راهنمای اتصال BPMS");
 const add=btn("+ اتصال جدید",()=>openEditor(null));
 append(headActions,help,add);append(head,headActions);append(section,head);

 const list=node("div","connection-list bpms-unified-list");append(section,list);
 const typeLabel=id=>(data.types||[]).find(x=>x.id===id)?.label||id;

 async function reload(){await showSettings("bpms")}

 function connectionRow(c){
  const actions=node("div","connection-actions"),out=node("div","full connection-feedback");
  const isPm=c.connection_type==="processmaker";
  const detail=isPm
   ?[
      "ProcessMaker",
      c.mysql?.host?(c.mysql.host+":"+(c.mysql.port||3306)+" / "+(c.mysql.database||"")):"MySQL ناقص",
      c.oauth?.workspace?("Workspace "+c.oauth.workspace):"OAuth ناقص",
      c.oauth?.token_managed?"OAuth خودکار":"OAuth نیازمند بررسی"
    ].join(" · ")
   :[typeLabel(c.engine||"other"),c.base_url||"",c.has_token?"توکن ثبت‌شده":"بدون توکن"].filter(Boolean).join(" · ");

  const test=btn("تست",async()=>{
    test.disabled=true;out.replaceChildren();
    try{
      await api("bpms/catalog/test",{connection_type:c.connection_type,id:c.id});
      out.replaceChildren(info("اتصال «"+c.name+"» با موفقیت تست شد."));
    }catch(err){showError(out,err)}finally{test.disabled=false}
  },"secondary");
  const edit=btn("ویرایش",()=>openEditor(c),"secondary");
  const copy=btn("کپی تنظیمات",async()=>{
    const proposed=(c.name||"اتصال")+" - کپی";
    const name=window.prompt("نام اتصال کپی‌شده:",proposed);
    if(name===null)return;
    copy.disabled=true;out.replaceChildren();
    try{
      await api("bpms/catalog/copy",{connection_type:c.connection_type,id:c.id,name:name.trim()||proposed});
      await reload();
    }catch(err){showError(out,err)}finally{copy.disabled=false}
  },"secondary");
  const remove=btn("حذف",async()=>{
    if(!confirm("اتصال «"+c.name+"» حذف شود؟ این عمل تنظیمات ذخیره‌شده همین اتصال را پاک می‌کند."))return;
    remove.disabled=true;out.replaceChildren();
    try{await api("bpms/catalog/delete",{connection_type:c.connection_type,id:c.id});await reload()}
    catch(err){showError(out,err)}finally{remove.disabled=false}
  },"secondary danger");
  append(actions,test,edit,copy);
  if(isPm)append(actions,btn("فرایندها و کارتابل‌ها",()=>secretaryProcessSettings(c,out),"secondary"));

  if(isPm&&!c.active){
    append(actions,btn("فعال‌سازی",async()=>{
      try{await api("bpms/processmaker/activate",{connection_type:"processmaker",id:c.id});await reload()}
      catch(err){showError(out,err)}
    }));
  }
  if(!isPm){
    append(actions,btn(c.enabled?"غیرفعال‌سازی":"فعال‌سازی",async()=>{
      try{await api("bpms/connections/enabled",{source_id:c.id,enabled:!c.enabled});await reload()}
      catch(err){showError(out,err)}
    },c.enabled?"secondary":""));
  }
  append(actions,remove);
  const active=isPm?!!c.active:!!c.enabled;
  const label=isPm?(c.active?"فعال":"ذخیره‌شده"):(c.enabled?"فعال":"غیرفعال");
  const row=connectionItem(c.name,detail,{active,label},actions);append(row,out);return row;
 }

 for(const c of data.connections||[])append(list,connectionRow(c));
 if(!(data.connections||[]).length)append(list,info("هنوز اتصال BPMS ثبت نشده است. روی «اتصال جدید» بزنید."));

 function openEditor(connection){
  editor.replaceChildren();state.bpmsEdit=connection?.id||"new";
  const isEdit=!!connection;
  const initialType=connection?(connection.connection_type==="processmaker"?"processmaker":(connection.engine||"other")):"processmaker";
  const box=panel(isEdit?"ویرایش اتصال «"+connection.name+"»":"اتصال BPMS جدید",
    "نوع BPMS را انتخاب کنید. اطلاعات لازم بر اساس موتور انتخاب‌شده نمایش داده می‌شود و ذخیره فقط پس از تست موفق انجام می‌شود.");
  box.classList.add("connection-editor","bpms-wizard");
  const toolbar=node("div","wizard-toolbar");
  append(toolbar,helpButton("bpms","راهنمای این اتصال"));
  append(box,toolbar);

  const base=node("form","grid"),dynamic=node("div","wizard-dynamic full"),out=node("div","full");
  const typeItems=(data.types||[]).map(x=>({value:x.id,label:x.label}));
  const nameField=field("نام دلخواه اتصال","name",connection?.name||"");
  const typeField=selectField("نوع BPMS","bpms_type",typeItems,initialType,{disabled:isEdit});
  append(base,nameField,typeField,dynamic,out);append(box,base);append(editor,box);

  const typeSelect=typeField.querySelector("select");

  function renderDynamic(){
    dynamic.replaceChildren();out.replaceChildren();
    const selected=isEdit?initialType:typeSelect.value;
    const localHelp=dynamic.querySelector?.(".help-launch");
    if(selected==="processmaker"){
      const mysql=connection?.connection_type==="processmaker"?(connection.mysql||{}):{};
      const oauth=connection?.connection_type==="processmaker"?(connection.oauth||{}):{};
      const f=node("div","grid wizard-fields");
      append(f,
       node("h3","full wizard-section-title","۱. اتصال داده ProcessMaker / MySQL"),
       field("Host MySQL","mysql_host",mysql.host||"host.docker.internal"),
       field("Port MySQL","mysql_port",String(mysql.port||3306),{type:"number"}),
       field("Database","mysql_database",mysql.database||"bitnami_pm"),
       field("Read-only Username","mysql_username",mysql.username||"avan_reader"),
       field(isEdit?"رمز MySQL؛ برای حفظ قبلی خالی بگذارید":"رمز MySQL","mysql_password","",{secret:true,required:!isEdit}),
       field("Timezone","mysql_timezone",mysql.timezone||"Asia/Tehran"),
       field("CA PEM؛ در صورت TLS","mysql_ca_pem","",{multiline:true,required:false}),
       node("h3","full wizard-section-title","۲. OAuth / API ProcessMaker"),
       field("Base URL API","oauth_base_url",oauth.base_url||"http://host.docker.internal:84"),
       field("Workspace","oauth_workspace",oauth.workspace||"workflow"),
       field("Client ID","oauth_client_id",oauth.client_id||""),
       field(isEdit?"Client Secret؛ برای حفظ قبلی خالی بگذارید":"Client Secret","oauth_client_secret","",{secret:true,required:!isEdit}),
       field(isEdit?"Username؛ فقط برای ساخت Token جدید":"Username ProcessMaker","oauth_username","",{required:!isEdit}),
       field(isEdit?"Password؛ فقط برای ساخت Token جدید و ذخیره نمی‌شود":"Password ProcessMaker؛ ذخیره نمی‌شود","oauth_password","",{secret:true,required:!isEdit})
      );
      const tls=node("input");tls.type="checkbox";tls.name="mysql_tls";tls.checked=!!mysql.tls;
      const tlsLabel=node("label","checkbox-line full");append(tlsLabel,tls,node("span",""," استفاده از TLS برای MySQL"));append(f,tlsLabel);
      const activate=node("input");activate.type="checkbox";activate.name="activate";activate.checked=isEdit?!!connection.active:true;
      const activateLabel=node("label","checkbox-line full");append(activateLabel,activate,node("span",""," پس از ذخیره، اتصال فعال ProcessMaker باشد"));append(f,activateLabel);

      const payload=()=>({
       id:isEdit?connection.id:null,name:formValue(base,"name"),
       mysql_host:formValue(base,"mysql_host"),mysql_port:Number(formValue(base,"mysql_port")||3306),
       mysql_database:formValue(base,"mysql_database"),mysql_username:formValue(base,"mysql_username"),
       mysql_password:formValue(base,"mysql_password"),mysql_tls:tls.checked,
       mysql_ca_pem:formValue(base,"mysql_ca_pem"),mysql_timezone:formValue(base,"mysql_timezone"),
       oauth_base_url:formValue(base,"oauth_base_url"),oauth_workspace:formValue(base,"oauth_workspace"),
       oauth_client_id:formValue(base,"oauth_client_id"),oauth_client_secret:formValue(base,"oauth_client_secret"),
       oauth_username:formValue(base,"oauth_username"),oauth_password:formValue(base,"oauth_password"),
       activate:activate.checked
      });
      const actions=node("div","actions full");
      const save=btn(isEdit?"تست و ذخیره تغییرات":"تست و افزودن",async()=>{
       busy(base,true);out.replaceChildren();
       try{
        const body=payload();
        await api("bpms/processmaker/save",body);
        const pw=base.elements.namedItem("oauth_password");if(pw)pw.value="";
        const mpw=base.elements.namedItem("mysql_password");if(mpw)mpw.value="";
        await reload();
       }catch(err){
        const pw=base.elements.namedItem("oauth_password");if(pw)pw.value="";
        showError(out,err)
       }finally{busy(base,false)}
      });
      append(actions,save,btn("انصراف",()=>{state.bpmsEdit=null;editor.replaceChildren()},"secondary"));
      append(f,actions);append(dynamic,f);
    }else{
      const source=connection?.connection_type==="adapter"?connection:null;
      const f=node("div","grid wizard-fields");
      append(f,
       node("h3","full wizard-section-title","اتصال از طریق AVAN REST v1"),
       field("Base URL آداپتر HTTPS","base_url",source?.base_url||"",{placeholder:"https://bpms.example.com"}),
       field(isEdit?"Bearer Token؛ برای حفظ قبلی خالی بگذارید":"Bearer Token فقط‌خواندنی","bearer_token","",{secret:true,required:!isEdit})
      );
      const enabled=node("input");enabled.type="checkbox";enabled.name="enabled";enabled.checked=source?!!source.enabled:true;
      const enabledLabel=node("label","checkbox-line full");append(enabledLabel,enabled,node("span",""," پس از ذخیره فعال باشد"));append(f,enabledLabel);
      const payload=()=>({id:source?.id||null,name:formValue(base,"name"),kind:"avan-rest-v1",
        engine:selected,base_url:formValue(base,"base_url"),bearer_token:formValue(base,"bearer_token"),
        enabled:enabled.checked});
      const actions=node("div","actions full");
      const save=btn(isEdit?"تست و ذخیره تغییرات":"تست و افزودن",async()=>{
       busy(base,true);out.replaceChildren();
       try{
        const body=payload();await api("bpms/connections/check",body);
        await api("bpms/connections/save",body);
        const token=base.elements.namedItem("bearer_token");if(token)token.value="";
        await reload();
       }catch(err){showError(out,err)}finally{busy(base,false)}
      });
      append(actions,save,btn("انصراف",()=>{state.bpmsEdit=null;editor.replaceChildren()},"secondary"));
      append(f,actions);append(dynamic,f);
    }
  }
  typeSelect.addEventListener("change",renderDynamic);renderDynamic();
  box.scrollIntoView({behavior:"smooth",block:"nearest"});
 }

 append(section,editor);
 if(state.bpmsEdit){
   const existing=(data.connections||[]).find(x=>x.id===state.bpmsEdit);
   if(existing)openEditor(existing);
   else if(state.bpmsEdit==="new")openEditor(null);
   else state.bpmsEdit=null;
 }
}

async function renderCompany(m){
 const p=panel("مدیریت سازمان‌ها",
  "هر سازمان Tenant ID ثابت خودش را دارد. می‌توانید چند سازمان تعریف کنید، وضعیت هرکدام را ببینید، نام را ویرایش و سازمان را فعال یا غیرفعال کنید.");
 append(m,p);

 const toolbar=node("div","section-head"),title=node("div");
 append(title,node("h3","","سازمان‌های ثبت‌شده"),
  node("span","hint","Tenant ID بعد از ایجاد هرگز تغییر نمی‌کند."));
 const actions=node("div","actions"),editor=node("div","organization-editor-slot");
 append(actions,btn("+ افزودن سازمان",()=>openOrganizationEditor(null)));
 append(toolbar,title,actions);append(p,toolbar,editor);

 const list=node("div","organization-list");append(p,list);
 let state;
 try{state=await api("organizations")}
 catch(err){append(list,info("فهرست سازمان‌ها قابل دریافت نیست: "+(err?.message||String(err)),true));return}

 const rows=state.organizations||[];
 if(!rows.length)append(list,info("هنوز سازمانی ثبت نشده است. روی «افزودن سازمان» بزنید."));

 function openOrganizationEditor(current){
  editor.replaceChildren();
  const box=panel(current?"ویرایش سازمان":"افزودن سازمان جدید",
   current
    ?"Tenant ID ثابت می‌ماند؛ فقط نام رسمی و وضعیت سازمان قابل تغییر است."
    :"برای سازمان جدید AVAN یک Tenant ID یکتا و دائمی تولید می‌کند.");
  box.classList.add("organization-editor");
  const form=node("form","grid"),out=node("div","full");
  append(form,field("نام رسمی سازمان","company_name",current?.company_name||""));
  const enabledLabel=node("label","organization-enabled-option");
  const enabled=node("input");enabled.type="checkbox";enabled.checked=current?!!current.enabled:true;
  append(enabledLabel,enabled,node("span","", "سازمان فعال باشد"));
  append(form,enabledLabel);
  if(current)append(form,node("div","full organization-tenant-readonly",
    "Tenant ID: "+current.tenant_id));
  const save=node("button","",current?"ذخیره تغییرات":"ایجاد سازمان");save.type="submit";
  append(form,save,btn("انصراف",()=>editor.replaceChildren(),"secondary"),out);
  form.addEventListener("submit",async e=>{
   e.preventDefault();busy(form,true);out.replaceChildren();
   try{
    const result=await api("organizations/save",{
     tenant_id:current?.tenant_id||null,
     company_name:formValue(form,"company_name"),
     enabled:enabled.checked
    });
    append(out,info((result.created?"سازمان ایجاد شد":"تغییرات ذخیره شد")+" · Tenant ID: "+result.tenant_id));
    await showSettings("company");
   }catch(err){showError(out,err)}finally{busy(form,false)}
  });
  append(box,form);append(editor,box);
 }

 for(const org of rows){
  const card=node("div","organization-card");
  const head=node("div","organization-card-head"),meta=node("div","organization-card-meta");
  append(meta,node("strong","",org.company_name||"سازمان بدون نام"),
   node("span","organization-tenant",org.tenant_id));
  const badges=node("div","organization-badges");
  append(badges,node("span","connection-pill "+(org.enabled?"is-active":"is-off"),
    org.enabled?"فعال":"غیرفعال"));
  if(org.is_primary)append(badges,node("span","organization-primary-badge","سازمان سازگار فعلی"));
  append(head,meta,badges);append(card,head);

  const details=node("div","organization-details");
  append(details,
   node("span","hint","ایجاد: "+(org.created_utc?new Date(org.created_utc).toLocaleString("fa-IR"):"—")),
   node("span","hint","آخرین تغییر: "+(org.updated_utc?new Date(org.updated_utc).toLocaleString("fa-IR"):"—")));
  append(card,details);

  const cardActions=node("div","actions");
  append(cardActions,
   btn("ویرایش",()=>openOrganizationEditor(org),"secondary"),
   btn(org.enabled?"غیرفعال‌سازی":"فعال‌سازی",async()=>{
    if(org.enabled&&!confirm("سازمان «"+org.company_name+"» غیرفعال شود؟"))return;
    try{
     await api("organizations/enabled",{tenant_id:org.tenant_id,enabled:!org.enabled});
     await showSettings("company");
    }catch(err){
     editor.replaceChildren();showError(editor,err)
    }
   },org.enabled?"secondary danger":""));
  append(card,cardActions);append(list,card);
 }

 const noteBox=node("div","settings-clean-note");
 append(noteBox,node("strong","","قاعده چندسازمانی AVAN"),
  node("p","hint","نام و وضعیت سازمان قابل تغییر است اما Tenant ID ثابت می‌ماند. اتصال کاربران، BPMSها، لایسنس و داده‌های Agent در مراحل بعدی با همین Tenant ID به سازمان مربوط Scope می‌شوند."));
 append(p,noteBox);
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



async function secretaryProcessSettings(connection,target){
 target.replaceChildren(info("در حال دریافت فرایندهای اتصال..."));
 try{
  const data=await api("secretary/processes/"+encodeURIComponent(connection.id));target.replaceChildren();
  const box=panel("فرایندها و کارتابل‌ها · "+connection.name,"بسته اختصاصی جلسه و اقدامات را به فرایندهای نصب‌شده همین اتصال متصل کنید.");
  const listing=node("details");append(listing,node("summary","","فرایندهای این BPMS ("+data.processes.length+")"));
  for(const p of data.processes)append(listing,node("p","",p.title+" · "+p.process_uid));append(box,listing);
  for(const pack of data.packs){const entry=node("div");append(entry,info((pack.meeting?.title||pack.process?.title||pack.id)+" · "+(pack.enabled?"فعال":"غیرفعال")+" · نسخه "+pack.revision),btn(pack.enabled?"غیرفعال‌سازی فرایند":"فعال‌سازی فرایند",async()=>{try{await api("process-workspace/enabled",{source_id:connection.id,pack_id:pack.id,revision:pack.revision,enabled:!pack.enabled});await secretaryProcessSettings(connection,target)}catch(e){showError(entry,e)}},"secondary"));append(box,entry)}
  const native=node("form"),nativeSelect=node("select");nativeSelect.setAttribute("aria-label","فرایند برای کارتابل بومی");for(const p of data.processes){const o=node("option","",p.title);o.value=p.process_uid;append(nativeSelect,o)}
  const nativeOut=node("div");append(native,nativeSelect,btn("اتصال کارتابل بومی این فرایند",async()=>{try{await api("process-workspace/connect",{source_id:connection.id,process_uid:nativeSelect.value});await secretaryProcessSettings(connection,target)}catch(e){showError(nativeOut,e)}}),info("کارتابل بومی برای هر فرایند، خواندنی است. عملیات اختصاصی با آداپتور همان فرایند فعال می‌شود."),nativeOut);append(box,native);
  const f=node("form"),select=node("select");select.name="pack";append(select,node("option","","بسته جدید"));for(const p of data.packs.filter(p=>p.adapter==="meeting_v2")){const o=node("option","",p.meeting.title);o.value=p.id;append(select,o)}
  append(f,node("label","","بسته قابل تنظیم"),select);
  const meeting=field("PMX مدیریت جلسات","meeting","",{type:"file"}),action=field("PMX اجرای اقدامات","action","",{type:"file"});for(const w of [meeting,action]){w.querySelector("input").accept=".pmx";append(f,w)}
  append(f,field("یادآوری پایش چند دقیقه قبل از پایان؟ (۱۴۴۰ = یک روز)","monitor",1440,{type:"number"}),field("یادآوری اقدام چند دقیقه قبل از مهلت؟","lead",60,{type:"number"}));
  const enabled=selectField("وضعیت دبیر این فرایند","enabled",[{value:"true",label:"فعال"},{value:"false",label:"غیرفعال"}],"true");append(f,enabled);
  select.addEventListener("change",()=>{const p=data.packs.find(x=>x.id===select.value);if(p){f.elements.monitor.value=p.monitor_lead_minutes;f.elements.lead.value=p.action_lead_minutes;f.elements.enabled.value=String(p.enabled)}});
  append(f,info("ابزارها: استخراج و پرسش تکمیلی، دعوت‌نامه، تأیید رئیس، صورتجلسه، گزارش و بررسی اقدام، پایش و پیشنهاد جلسه پیگیری. PMX نامرتبط نیازمند آداپتور اختصاصی است."));
  const out=node("div");append(f,btn("بررسی PMX و ذخیره تنظیم فرایند",async()=>{
   busy(f,true);try{
    const files=[f.elements.meeting.files[0],f.elements.action.files[0]];if(files.some(x=>!x||x.size>2500000))throw Error("هر دو فایل PMX لازم است؛ حداکثر هر فایل ۲٫۵ مگابایت.");
    const [meeting_pmx,action_pmx]=await Promise.all(files.map(x=>x.text()));const old=data.packs.find(x=>x.id===select.value);
    await api("secretary/packs/save",{source_id:connection.id,meeting_pmx,action_pmx,id:old?.id||null,revision:old?.revision||null,enabled:f.elements.enabled.value==="true",monitor_lead_minutes:Number(f.elements.monitor.value),action_lead_minutes:Number(f.elements.lead.value)});
    await secretaryProcessSettings(connection,target);
   }catch(e){showError(out,e)}finally{busy(f,false)}
  }),out);append(box,f);append(target,box);
 }catch(e){showError(target,e)}
}
