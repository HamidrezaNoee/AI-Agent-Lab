"use strict";
(function(){
 function init(){
  const panel=document.querySelector(".signin-panel.login-reveal-card");
  const toggle=document.querySelector("[data-login-reveal]");
  const form=document.getElementById("kc-form-login");
  if(!panel||!toggle||!form)return;
  let expanded=false;
  function setExpanded(open){
   expanded=!!open;
   panel.classList.toggle("is-collapsed",!expanded);
   panel.classList.toggle("is-expanded",expanded);
   toggle.setAttribute("aria-expanded",String(expanded));
   if(expanded){
    window.dispatchEvent(new CustomEvent("avan-login-expanded"));
    requestAnimationFrame(()=>document.getElementById("username")?.focus());
   }
  }
  toggle.addEventListener("click",()=>setExpanded(!expanded));
  document.addEventListener("pointerdown",event=>{
   if(expanded&&!panel.contains(event.target))setExpanded(false);
  },true);
  document.addEventListener("keydown",event=>{
   if(event.key==="Escape"&&expanded)setExpanded(false);
  });
  setExpanded(!!panel.querySelector(".signin-error"));
 }
 if(document.readyState==="loading")document.addEventListener("DOMContentLoaded",init,{once:true});
 else init();
})();