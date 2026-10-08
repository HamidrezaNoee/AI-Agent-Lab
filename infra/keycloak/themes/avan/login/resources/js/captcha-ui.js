"use strict";
(function(){
 const encoder=new TextEncoder();
 let turnstilePromise=null;

 function setState(root,state,message){
  root.classList.remove("is-loading","is-checking","is-verified","is-expired","is-error");
  root.classList.add(state);
  const status=root.querySelector(".avan-captcha-status");
  if(status)status.textContent=message;
 }

 function hex(buffer){
  return [...new Uint8Array(buffer)].map(b=>b.toString(16).padStart(2,"0")).join("");
 }

 function ensureTurnstile(timeoutMs){
  if(window.turnstile)return Promise.resolve(window.turnstile);
  if(turnstilePromise)return turnstilePromise;
  turnstilePromise=new Promise((resolve,reject)=>{
   const callback="__avanKeycloakTurnstileReady";
   const timer=window.setTimeout(()=>{
    document.querySelector('script[data-avan-turnstile="1"]')?.remove();
    turnstilePromise=null;
    reject(new Error("cloudflare-timeout"));
   },Math.max(1200,timeoutMs||2500));
   window[callback]=()=>{
    window.clearTimeout(timer);
    try{delete window[callback]}catch(_err){}
    if(window.turnstile)resolve(window.turnstile);
    else{turnstilePromise=null;reject(new Error("cloudflare-unavailable"))}
   };
   document.querySelector('script[data-avan-turnstile="1"]')?.remove();
   const script=document.createElement("script");
   script.dataset.avanTurnstile="1";
   script.src="https://challenges.cloudflare.com/turnstile/v0/api.js?onload="+callback+"&render=explicit";
   script.async=true;script.defer=true;
   script.onerror=()=>{
    window.clearTimeout(timer);
    turnstilePromise=null;
    try{delete window[callback]}catch(_err){}
    reject(new Error("cloudflare-load-failed"));
   };
   document.head.appendChild(script);
  });
  return turnstilePromise;
 }

 async function solveLocal(root,setStateLocal){
  const algorithm=root.dataset.algorithm;
  const challenge=(root.dataset.challenge||"").toLowerCase();
  const salt=root.dataset.salt||"";
  const signature=root.dataset.signature||"";
  const max=Number(root.dataset.maxNumber||"0");
  if(algorithm!=="SHA-256"||!challenge||!salt||!signature||
     !Number.isInteger(max)||max<1000||max>250000||!window.crypto?.subtle){
   throw new Error("invalid-local-challenge");
  }
  let solution=null;
  const batchSize=64;
  for(let start=0;start<=max&&solution===null;start+=batchSize){
   const stop=Math.min(max,start+batchSize-1);
   const numbers=[];for(let n=start;n<=stop;n++)numbers.push(n);
   const hashes=await Promise.all(numbers.map(n=>
    crypto.subtle.digest("SHA-256",encoder.encode(salt+n))
   ));
   for(let i=0;i<hashes.length;i++){
    if(hex(hashes[i])===challenge){solution=numbers[i];break}
   }
   if(start===0||start%1024<batchSize){
    const percent=Math.min(99,Math.round((stop/max)*100));
    setStateLocal("is-checking","در حال بررسی محلی… "+percent+"٪");
   }
  }
  if(solution===null)throw new Error("challenge-not-solved");
  return btoa(JSON.stringify({
   algorithm,
   challenge:root.dataset.challenge,
   number:solution,
   salt,
   signature
  }));
 }

 function tryCloudflare(root,slot,badge,provider,setStateLocal){
  return new Promise(async(resolve,reject)=>{
   const sitekey=root.dataset.siteKey||"";
   if(!sitekey){reject(new Error("cloudflare-disabled"));return}
   const timeoutMs=Math.max(1200,Math.min(5000,Number(root.dataset.turnstileTimeout||"2500")));
   badge.textContent="CLOUDFLARE";
   provider.textContent="CLOUDFLARE TURNSTILE · PRIMARY";
   setStateLocal("is-checking","در حال بررسی با Cloudflare Turnstile…");

   let settled=false,widgetId=null;
   const timer=window.setTimeout(()=>fail(new Error("cloudflare-verification-timeout")),timeoutMs);
   function cleanup(){
    window.clearTimeout(timer);
    if(window.turnstile&&widgetId!==null){try{window.turnstile.remove(widgetId)}catch(_err){}}
   }
   function fail(err){
    if(settled)return;
    settled=true;cleanup();slot.replaceChildren();reject(err);
   }
   function success(token){
    if(settled)return;
    settled=true;window.clearTimeout(timer);resolve(token);
   }
   try{
    const turnstile=await ensureTurnstile(timeoutMs);
    if(settled)return;
    widgetId=turnstile.render(slot,{
     sitekey,
     action:root.dataset.action||"avan-login",
     theme:"dark",
     size:"flexible",
     appearance:"interaction-only",
     language:"fa",
     retry:"never",
     "refresh-expired":"never",
     callback:success,
     "expired-callback":()=>fail(new Error("cloudflare-expired")),
     "timeout-callback":()=>fail(new Error("cloudflare-timeout")),
     "error-callback":()=>fail(new Error("cloudflare-error"))
    });
   }catch(err){fail(err)}
  });
 }

 async function solve(root){
  if(root.dataset.rendered==="1")return;
  const panel=root.closest(".login-reveal-card");
  if(panel&&panel.classList.contains("is-collapsed"))return;
  root.dataset.rendered="1";

  const button=document.getElementById("kc-login");
  const field=document.getElementById("avan-antibot");
  const badge=root.querySelector(".avan-captcha-badge");
  const provider=root.querySelector(".captcha-provider");
  const slot=root.querySelector(".captcha-turnstile-slot");
  const expiresIn=Math.max(15,Number(root.dataset.expiresIn||"120"));
  if(!field||!badge||!provider||!slot){
   setState(root,"is-error","پیکربندی امنیتی کامل نیست");
   return;
  }
  if(button)button.disabled=true;

  try{
   const sitekey=root.dataset.siteKey||"";
   const forceLocal=root.dataset.forceLocal==="true";
   if(sitekey&&!forceLocal){
    try{
     const cfToken=await tryCloudflare(root,slot,badge,provider,
      (state,message)=>setState(root,state,message));
     field.value=JSON.stringify({provider:"cloudflare-turnstile",token:cfToken});
     if(button)button.disabled=false;
     badge.textContent="CLOUDFLARE";
     provider.textContent="CLOUDFLARE TURNSTILE · VERIFIED";
     setState(root,"is-verified","اتصال امن با Cloudflare تأیید شد");
     return;
    }catch(_err){
     slot.replaceChildren();
     badge.textContent="LOCAL";
     provider.textContent="ALTCHA · SELF-HOSTED FALLBACK";
     setState(root,"is-checking","Cloudflare در دسترس نبود؛ بررسی محلی فعال شد…");
    }
   }else{
    badge.textContent="LOCAL";
    provider.textContent="ALTCHA · SELF-HOSTED";
    setState(root,"is-checking",forceLocal?"Fallback محلی برای این تلاش فعال شد…":"Cloudflare تنظیم نشده؛ بررسی محلی فعال است…");
   }

   const localToken=await solveLocal(root,(state,message)=>setState(root,state,message));
   field.value=JSON.stringify({provider:"altcha-self-hosted",token:localToken});
   if(button)button.disabled=false;
   setState(root,"is-verified","اتصال امن با Anti-Bot داخلی تأیید شد");

   window.setTimeout(()=>{
    field.value="";
    if(button)button.disabled=true;
    setState(root,"is-expired","Challenge منقضی شد؛ برای بررسی تازه صفحه را نوسازی کنید");
   },Math.max(5000,(expiresIn-8)*1000));
  }catch(_err){
   field.value="";
   if(button)button.disabled=true;
   root.dataset.rendered="0";
   setState(root,"is-error","هیچ مسیر ضدرباتی در دسترس نیست");
  }
 }

 function renderAll(){
  document.querySelectorAll("[data-avan-captcha]").forEach(root=>void solve(root));
 }

 window.avanRenderCaptcha=renderAll;
 window.addEventListener("avan-login-expanded",renderAll);
 if(document.readyState==="loading")document.addEventListener("DOMContentLoaded",renderAll,{once:true});
 else renderAll();
})();