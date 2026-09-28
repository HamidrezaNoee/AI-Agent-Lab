"use strict";
(function(){
 const encoder=new TextEncoder();

 function setState(root,state,message){
  root.classList.remove("is-loading","is-checking","is-verified","is-expired","is-error");
  root.classList.add(state);
  const status=root.querySelector(".avan-captcha-status");
  if(status)status.textContent=message;
 }

 function hex(buffer){
  return [...new Uint8Array(buffer)].map(b=>b.toString(16).padStart(2,"0")).join("");
 }

 async function solve(root){
  if(root.dataset.rendered==="1")return;
  const panel=root.closest(".login-reveal-card");
  if(panel&&panel.classList.contains("is-collapsed"))return;
  root.dataset.rendered="1";

  const button=document.getElementById("kc-login");
  const field=document.getElementById("avan-antibot");
  const algorithm=root.dataset.algorithm;
  const challenge=(root.dataset.challenge||"").toLowerCase();
  const salt=root.dataset.salt||"";
  const signature=root.dataset.signature||"";
  const max=Number(root.dataset.maxNumber||"0");
  const expiresIn=Math.max(15,Number(root.dataset.expiresIn||"120"));

  if(button)button.disabled=true;
  if(!field||algorithm!=="SHA-256"||!challenge||!salt||!signature||
     !Number.isInteger(max)||max<1000||max>250000||!window.crypto?.subtle){
   setState(root,"is-error","سرویس ضدربات داخلی پاسخ معتبر نداد");
   return;
  }

  try{
   setState(root,"is-checking","در حال انجام Proof-of-Work محلی…");
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
      setState(root,"is-checking","در حال بررسی امنیتی… "+percent+"٪");
    }
   }
   if(solution===null)throw new Error("challenge-not-solved");

   field.value=btoa(JSON.stringify({
    algorithm,
    challenge:root.dataset.challenge,
    number:solution,
    salt,
    signature
   }));
   if(button)button.disabled=false;
   setState(root,"is-verified","اتصال امن تأیید شد · بدون سرویس خارجی");

   window.setTimeout(()=>{
    field.value="";
    if(button)button.disabled=true;
    setState(root,"is-expired","Challenge منقضی شد؛ برای دریافت بررسی تازه صفحه را نوسازی کنید");
   },Math.max(5000,(expiresIn-8)*1000));
  }catch(_err){
   field.value="";
   if(button)button.disabled=true;
   root.dataset.rendered="0";
   setState(root,"is-error","بررسی امنیتی کامل نشد؛ دوباره وارد کارت شوید");
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