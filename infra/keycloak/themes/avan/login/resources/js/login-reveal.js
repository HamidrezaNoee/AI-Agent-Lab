"use strict";
(function(){
 function init(){
  const panel=document.querySelector(".signin-panel.login-reveal-card");
  const toggle=document.querySelector("[data-login-reveal]");
  const form=document.getElementById("kc-form-login");
  const username=document.getElementById("username");
  if(!panel||!toggle||!form)return;

  let expanded=false,pointerInside=false,collapseTimer=null;

  function setExpanded(open){
   expanded=!!open;
   panel.classList.toggle("is-collapsed",!expanded);
   panel.classList.toggle("is-expanded",expanded);
   toggle.setAttribute("aria-expanded",String(expanded));
   if(expanded)window.dispatchEvent(new CustomEvent("avan-login-expanded"));
  }

  function scheduleCollapse(){
   window.clearTimeout(collapseTimer);
   collapseTimer=window.setTimeout(()=>{
    if(!pointerInside)setExpanded(false);
   },90);
  }

  panel.addEventListener("pointerenter",event=>{
   if(event.pointerType==="mouse"||event.pointerType==="pen"){
    pointerInside=true;
    window.clearTimeout(collapseTimer);
    setExpanded(true);
   }
  });

  panel.addEventListener("pointerleave",event=>{
   if(event.pointerType==="mouse"||event.pointerType==="pen"){
    pointerInside=false;
    scheduleCollapse();
   }
  });

  panel.addEventListener("focusin",()=>{
   window.clearTimeout(collapseTimer);
   setExpanded(true);
  });

  panel.addEventListener("focusout",event=>{
   if(!panel.contains(event.relatedTarget)&&!pointerInside)scheduleCollapse();
  });

  // Touch/mobile fallback. Desktop users only need to hover.
  toggle.addEventListener("click",()=>{
   setExpanded(true);
   window.requestAnimationFrame(()=>username?.focus());
  });

  setExpanded(!!panel.querySelector(".signin-error"));
 }

 if(document.readyState==="loading")document.addEventListener("DOMContentLoaded",init,{once:true});
 else init();
})();