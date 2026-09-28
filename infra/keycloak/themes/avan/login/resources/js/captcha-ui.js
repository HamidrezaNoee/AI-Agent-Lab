"use strict";
(function(){
 function setState(root,state,message){
  root.classList.remove("is-loading","is-checking","is-verified","is-expired","is-error");
  root.classList.add(state);
  const status=root.querySelector(".avan-captcha-status");
  if(status)status.textContent=message;
 }
 function render(root){
  if(root.dataset.rendered==="1"||!window.turnstile)return;
  root.dataset.rendered="1";
  const slot=root.querySelector(".avan-captcha-challenge");
  const button=document.getElementById("kc-login");
  if(!slot)return;
  if(button)button.disabled=true;
  setState(root,"is-checking","در حال بررسی مرورگر و اتصال امن…");
  window.turnstile.render(slot,{
   sitekey:root.dataset.sitekey,
   action:root.dataset.action||"avan-login",
   theme:"dark",
   size:"flexible",
   appearance:"interaction-only",
   language:"fa",
   retry:"auto",
   "refresh-expired":"auto",
   callback:function(){
    if(button)button.disabled=false;
    setState(root,"is-verified","اتصال امن تأیید شد");
   },
   "expired-callback":function(){
    if(button)button.disabled=true;
    setState(root,"is-expired","تأیید امنیتی منقضی شد؛ در حال تازه‌سازی…");
   },
   "timeout-callback":function(){
    if(button)button.disabled=true;
    setState(root,"is-expired","زمان بررسی پایان یافت؛ دوباره تلاش کنید");
   },
   "error-callback":function(){
    if(button)button.disabled=true;
    setState(root,"is-error","بررسی امنیتی کامل نشد؛ دوباره تلاش کنید");
   }
  });
 }
 function renderAll(){
  document.querySelectorAll("[data-avan-captcha]").forEach(render);
 }
 window.avanTurnstileReady=function(){
  if(document.readyState==="loading")document.addEventListener("DOMContentLoaded",renderAll,{once:true});
  else renderAll();
 };
})();