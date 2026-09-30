"use strict";
(function(){
 const IMAGE={w:1672,h:941,gx:370,gy:350,gr:214};
 const caps=[
  {id:"meetings",title:"جلسات و مصوبات",summary:"دبیر هوشمند، صورت‌جلسه، اقدامات، تأیید و پیگیری تا بسته‌شدن.",tags:["Minutes","Actions","Follow-up"],icon:"calendar",orbit:.15,speed:.00023,phase:.2},
  {id:"bi",title:"BI و تحلیل مدیریتی",summary:"گزارش زنده فرایندها، KPIها، روندها و پرسش مدیریتی روی داده عملیاتی.",tags:["KPI","BI","Trends"],icon:"chart",orbit:.38,speed:-.00018,phase:1.25},
  {id:"bpms",title:"اتصالات BPMS",summary:"ProcessMaker و سایر موتورهای BPMS در یک کاتالوگ با تست، ویرایش و مدیریت اتصال.",tags:["ProcessMaker","BPMS","OAuth"],icon:"flow",orbit:.58,speed:.00016,phase:2.1},
  {id:"agent",title:"Agentic Automation",summary:"Agentهای تخصصی برای تحلیل، تصمیم‌یار و اجرای کنترل‌شده گردش‌کارهای سازمان.",tags:["Agents","Tools","Workflow"],icon:"spark",orbit:.25,speed:-.00021,phase:3.0},
  {id:"voice",title:"Voice AI",summary:"ورودی و پاسخ صوتی برای دستیار مدیریتی، جلسات و ثبت سریع اطلاعات.",tags:["Speech","TTS","Assistant"],icon:"mic",orbit:.48,speed:.00019,phase:4.0},
  {id:"docs",title:"Document Intelligence",summary:"درک سند، استخراج داده و اتصال محتوای اسناد به Agent و فرایندهای سازمان.",tags:["Docs","Extract","Context"],icon:"doc",orbit:.7,speed:-.00014,phase:5.05},
  {id:"alerts",title:"هشدار و پیگیری",summary:"پایش SLA، تأخیر، ریسک و اقدامات باز با هشدارهای قابل پیگیری.",tags:["SLA","Risk","Monitor"],icon:"alert",orbit:.33,speed:.00024,phase:5.7},
  {id:"security",title:"هویت و امنیت",summary:"ورود یکپارچه، MFA، کنترل دسترسی و Anti-Bot هیبرید برای محیط سازمانی.",tags:["MFA","OIDC","Anti-Bot"],icon:"shield",orbit:.62,speed:-.00017,phase:.85}
 ];
 const icons={
  calendar:'<path d="M7 3v3M17 3v3M4 8h16M5 5h14a1 1 0 0 1 1 1v13H4V6a1 1 0 0 1 1-1Z"/><path d="M8 12h3v3H8zM13 12h3v3h-3z"/>',
  chart:'<path d="M4 20V9M10 20V4M16 20v-7M22 20H2"/><path d="m4 8 6-4 6 7 5-4"/>',
  flow:'<circle cx="5" cy="6" r="2.5"/><circle cx="19" cy="6" r="2.5"/><circle cx="12" cy="18" r="2.5"/><path d="M7.5 6h9M6.5 8l4 7M17.5 8l-4 7"/>',
  spark:'<path d="m12 2 1.8 5.2L19 9l-5.2 1.8L12 16l-1.8-5.2L5 9l5.2-1.8L12 2Z"/><path d="m19 15 .9 2.6 2.6.9-2.6.9L19 22l-.9-2.6-2.6-.9 2.6-.9L19 15Z"/>',
  mic:'<rect x="8" y="3" width="8" height="12" rx="4"/><path d="M5 11a7 7 0 0 0 14 0M12 18v3M8 21h8"/>',
  doc:'<path d="M6 2h8l4 4v16H6z"/><path d="M14 2v5h5M9 12h6M9 16h6"/>',
  alert:'<path d="M12 3 2.8 20h18.4L12 3Z"/><path d="M12 9v5M12 17.5v.5"/>',
  shield:'<path d="M12 2 20 5v6c0 5.2-3.1 8.6-8 11-4.9-2.4-8-5.8-8-11V5l8-3Z"/><path d="m8.5 12 2.3 2.3 4.8-5"/>'
 };
 let root,canvas,ctx,nodes=[],tooltip,selected=null,raf=0,last=0,globe={x:0,y:0,r:0};
 function bg(){document.documentElement.style.setProperty("--avan-live-login-bg",'url("data:image/webp;base64,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")')}
 function calc(){
  const w=innerWidth,h=innerHeight,s=Math.max(w/IMAGE.w,h/IMAGE.h),rw=IMAGE.w*s,rh=IMAGE.h*s;
  const ox=(w-rw)/2,oy=(h-rh)/2;
  globe={x:ox+IMAGE.gx*s,y:oy+IMAGE.gy*s,r:IMAGE.gr*s};
  if(canvas){const dpr=Math.min(devicePixelRatio||1,2);canvas.width=Math.round(w*dpr);canvas.height=Math.round(h*dpr);canvas.style.width=w+"px";canvas.style.height=h+"px";ctx=canvas.getContext("2d");ctx.setTransform(dpr,0,0,dpr,0,0)}
 }
 function draw(t){
  if(!ctx)return;
  ctx.clearRect(0,0,innerWidth,innerHeight);
  const {x,y,r}=globe,phase=t*.00008;
  ctx.save();ctx.globalCompositeOperation="screen";
  for(let k=0;k<4;k++){
   ctx.beginPath();ctx.strokeStyle=k%2?"rgba(48,225,238,.19)":"rgba(255,102,78,.11)";
   ctx.lineWidth=k===0?1.2:.75;
   ctx.ellipse(x,y,r*(1.08+k*.14),r*(.52+k*.08),phase*(k%2?1:-1)+k*.72,0,Math.PI*2);
   ctx.stroke();
  }
  for(let i=0;i<18;i++){
   const a=phase*4+i*.71,rr=r*(1.05+(i%5)*.09),ex=x+Math.cos(a)*rr,ey=y+Math.sin(a)*rr*.58;
   ctx.fillStyle=i%4?"rgba(101,239,250,.62)":"rgba(255,108,80,.72)";
   ctx.shadowBlur=10;ctx.shadowColor=ctx.fillStyle;ctx.beginPath();ctx.arc(ex,ey,i%3?1.6:2.4,0,Math.PI*2);ctx.fill();
  }
  const sweep=(t*.00035)%(Math.PI*2);
  ctx.strokeStyle="rgba(95,244,255,.42)";ctx.lineWidth=2.2;ctx.shadowBlur=14;ctx.shadowColor="#4ee7ff";
  ctx.beginPath();ctx.arc(x,y,r*1.03,sweep,sweep+1.05);ctx.stroke();
  ctx.restore();
 }
 function posNode(n,t){
  if(n.hovered||n.dragHold)return;
  n.angle+=(t-last)*n.cap.speed;
  const r=globe.r*(1.22+n.cap.orbit*.5),rx=r,ry=globe.r*(.68+n.cap.orbit*.22);
  n.x=globe.x+Math.cos(n.angle)*rx;n.y=globe.y+Math.sin(n.angle)*ry;
  n.el.style.transform='translate3d('+(n.x-27)+'px,'+(n.y-27)+'px,0)';
  if(selected===n)placeTip(n);
 }
 function placeTip(n){
  if(!tooltip||!n)return;
  const maxW=Math.min(330,innerWidth-30),left=Math.max(15,Math.min(innerWidth-maxW-15,n.x+34)),top=Math.max(15,Math.min(innerHeight-170,n.y-64));
  tooltip.style.width=maxW+"px";tooltip.style.left=left+"px";tooltip.style.top=top+"px";
 }
 function showTip(n,pinned=false){
  selected=pinned?n:selected;
  tooltip.replaceChildren();
  const h=document.createElement("strong");h.textContent=n.cap.title;
  const p=document.createElement("p");p.textContent=n.cap.summary;
  const tags=document.createElement("div");tags.className="avan-scene-tags";
  n.cap.tags.forEach(x=>{const s=document.createElement("span");s.textContent=x;tags.append(s)});
  tooltip.append(h,p,tags);tooltip.classList.add("is-visible");placeTip(n);
 }
 function hideTip(n){if(selected)return;if(n&&!n.hovered)tooltip.classList.remove("is-visible")}
 function loop(t){
  if(!last)last=t;draw(t);nodes.forEach(n=>posNode(n,t));last=t;raf=requestAnimationFrame(loop)
 }
 function nodeEl(cap,index){
  const b=document.createElement("button");b.type="button";b.className="avan-orbit-node";b.setAttribute("aria-label",cap.title);
  b.innerHTML='<span class="avan-orbit-icon"><svg viewBox="0 0 24 24" aria-hidden="true">'+icons[cap.icon]+'</svg></span><span class="avan-orbit-label">'+cap.title+'</span>';
  const n={cap,el:b,angle:cap.phase,x:0,y:0,hovered:false};
  b.addEventListener("mouseenter",()=>{n.hovered=true;showTip(n,false)});
  b.addEventListener("mouseleave",()=>{n.hovered=false;if(selected!==n)hideTip(n)});
  b.addEventListener("focus",()=>{n.hovered=true;showTip(n,false)});
  b.addEventListener("blur",()=>{n.hovered=false;if(selected!==n)hideTip(n)});
  b.addEventListener("click",()=>{selected=selected===n?null:n;nodes.forEach(x=>x.el.classList.toggle("is-selected",selected===x));if(selected)showTip(n,true);else tooltip.classList.remove("is-visible")});
  return n;
 }
 function scene(){
  if(root)return;
  root=document.createElement("div");root.className="avan-live-scene";root.setAttribute("data-avan-live-scene","");
  canvas=document.createElement("canvas");canvas.className="avan-globe-fx";canvas.setAttribute("aria-hidden","true");
  const layer=document.createElement("div");layer.className="avan-orbit-layer";
  tooltip=document.createElement("aside");tooltip.className="avan-scene-tooltip";tooltip.setAttribute("role","status");tooltip.setAttribute("aria-live","polite");
  nodes=caps.map(nodeEl);nodes.forEach(n=>layer.append(n.el));root.append(canvas,layer,tooltip);document.body.prepend(root);calc();last=0;cancelAnimationFrame(raf);raf=requestAnimationFrame(loop)
 }
 function interactive(el){return !!el.closest('input,textarea,select,button,a,label,form,.avan-captcha,.otp-motion')}
 function draggable(card){
  if(card.dataset.avanDraggable==="1")return;card.dataset.avanDraggable="1";
  let active=false,pid=null,sx=0,sy=0,bx=Number(card.dataset.dragX||0),by=Number(card.dataset.dragY||0);
  const move=e=>{
   if(!active||e.pointerId!==pid)return;
   const rect=card.getBoundingClientRect(),margin=12;
   let nx=bx+(e.clientX-sx),ny=by+(e.clientY-sy);
   const baseLeft=rect.left-(Number(card.dataset.dragX||0)),baseTop=rect.top-(Number(card.dataset.dragY||0));
   nx=Math.min(innerWidth-margin-baseLeft-rect.width,Math.max(margin-baseLeft,nx));
   ny=Math.min(innerHeight-margin-baseTop-rect.height,Math.max(margin-baseTop,ny));
   card.dataset.dragX=String(nx);card.dataset.dragY=String(ny);card.style.translate=nx+"px "+ny+"px";
  };
  const end=e=>{
   if(!active||e.pointerId!==pid)return;active=false;card.dataset.dragging="0";card.classList.remove("is-login-dragging");
   bx=Number(card.dataset.dragX||0);by=Number(card.dataset.dragY||0);try{card.releasePointerCapture(pid)}catch{}pid=null;
  };
  card.addEventListener("pointerdown",e=>{
   if(e.button!==0||interactive(e.target)||innerWidth<820)return;
   active=true;pid=e.pointerId;sx=e.clientX;sy=e.clientY;bx=Number(card.dataset.dragX||0);by=Number(card.dataset.dragY||0);
   card.dataset.dragging="1";card.classList.add("is-login-dragging");card.setPointerCapture(pid);e.preventDefault();
  });
  card.addEventListener("pointermove",move);card.addEventListener("pointerup",end);card.addEventListener("pointercancel",end);
  card.addEventListener("dblclick",e=>{if(interactive(e.target))return;card.dataset.dragX="0";card.dataset.dragY="0";card.style.translate="0px 0px"});
 }
 function sync(){
  const card=document.querySelector(".login-reveal-card,.panel.login");
  if(card){document.body.classList.add("avan-live-login-enabled");scene();draggable(card)}
  else if(root){root.remove();root=null;nodes=[];tooltip=null;cancelAnimationFrame(raf);document.body.classList.remove("avan-live-login-enabled")}
 }
 bg();window.addEventListener("resize",calc,{passive:true});
 if(document.readyState==="loading")document.addEventListener("DOMContentLoaded",sync,{once:true});else sync();
 new MutationObserver(sync).observe(document.documentElement,{subtree:true,childList:true});
})();