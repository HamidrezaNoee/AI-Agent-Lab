"use strict";
(function(){
 const root=document.querySelector("[data-otp-motion]");
 if(!root)return;
 const input=root.querySelector(".otp-motion-native");
 const form=input&&input.form;
 const cells=[...root.querySelectorAll(".otp-digit")];
 const status=root.querySelector(".otp-motion-status");
 if(!input||!form||cells.length!==6)return;
 const fa="۰۱۲۳۴۵۶۷۸۹",ar="٠١٢٣٤٥٦٧٨٩";
 const normalize=value=>String(value||"")
   .replace(/[۰-۹]/g,c=>String(fa.indexOf(c)))
   .replace(/[٠-٩]/g,c=>String(ar.indexOf(c)))
   .replace(/\D/g,"").slice(0,6);
 let locked=false,timer=null;
 function render(){
   const value=normalize(input.value);
   if(input.value!==value)input.value=value;
   cells.forEach((cell,index)=>{
     cell.textContent=value[index]||"";
     cell.classList.toggle("is-filled",index<value.length);
     cell.classList.toggle("is-next",index===value.length&&value.length<6);
   });
   root.classList.toggle("has-value",value.length>0);
 }
 function submitAfterMotion(){
   if(locked)return;
   const value=normalize(input.value);
   if(value.length!==6){
     root.classList.add("is-error");
     setTimeout(()=>root.classList.remove("is-error"),420);
     input.focus();return;
   }
   locked=true;input.value=value;input.readOnly=true;
   root.classList.add("is-complete");
   if(status)status.textContent="کد کامل شد؛ در حال تأیید.";
   const reduced=window.matchMedia&&window.matchMedia("(prefers-reduced-motion: reduce)").matches;
   clearTimeout(timer);
   timer=setTimeout(()=>{
     root.classList.add("is-verified");
     if(status)status.textContent="در حال بررسی کد.";
     HTMLFormElement.prototype.submit.call(form);
   },reduced?100:1240);
 }
 input.addEventListener("input",()=>{
   input.value=normalize(input.value);render();
   if(input.value.length===6&&!locked)setTimeout(submitAfterMotion,35);
 });
 input.addEventListener("paste",event=>{
   const value=normalize(event.clipboardData&&event.clipboardData.getData("text"));
   if(!value)return;
   event.preventDefault();input.value=value;render();
   input.dispatchEvent(new Event("input",{bubbles:true}));
 });
 root.addEventListener("click",()=>{if(!locked)input.focus()});
 form.addEventListener("submit",event=>{
   if(locked){event.preventDefault();return}
   if(normalize(input.value).length!==6)return;
   event.preventDefault();submitAfterMotion();
 });
 render();input.focus();
})();
