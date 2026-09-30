"use strict";
(function(){
 const SCRIPT_SRC=(document.currentScript&&document.currentScript.src)||"";
 const REDUCED=!!(window.matchMedia&&window.matchMedia("(prefers-reduced-motion: reduce)").matches);
 const caps=[
  {id:"docs",title:"Document Intelligence",summary:"تحلیل قرارداد، صورت‌جلسه، گزارش و فایل؛ استخراج اطلاعات و تبدیل محتوا به Context قابل استفاده برای Agent و جست‌وجوی سازمانی.",tags:["Documents","Extraction","RAG"],icon:"doc",radius:1.20,ellipse:.72,phase:3.50,speed:.00018},
  {id:"bi",title:"BI و تحلیل مدیریتی",summary:"اتصال گزارش‌های مدیریتی، KPIها و تحلیل روند به فضای کاری آوان؛ با امکان پرسش‌وپاسخ روی داده و یافتن گلوگاه‌ها.",tags:["Power BI","KPI","Root Cause"],icon:"chart",radius:1.38,ellipse:.66,phase:4.15,speed:-.00014},
  {id:"meetings",title:"جلسات و مصوبات",summary:"از برنامه‌ریزی و صورت‌جلسه تا اقدام، مسئول، موعد، درصد پیشرفت، ارزیابی و جلسه بعدی؛ متصل به AI Agent جلسات.",tags:["Minutes","Actions","Follow-up"],icon:"calendar",radius:1.13,ellipse:.78,phase:4.95,speed:.00020,accent:"orange"},
  {id:"bpms",title:"اتصالات BPMS",summary:"کاتالوگ یکپارچه اتصال ProcessMaker، Camunda، Appian، UiPath و سایر BPMSها با تست، ویرایش، OAuth و کنترل دسترسی.",tags:["ProcessMaker","BPMS","OAuth"],icon:"flow",radius:1.46,ellipse:.62,phase:5.62,speed:-.00013},
  {id:"agent",title:"Agentic Automation",summary:"Agentهای تخصصی برای تحلیل، تصمیم‌یار و اجرای کنترل‌شده کارها؛ هماهنگ با انسان، سیستم و Workflowهای سازمان.",tags:["Agents","Tools","Workflow"],icon:"spark",radius:1.18,ellipse:.75,phase:.10,speed:.00018},
  {id:"voice",title:"Voice AI",summary:"ورودی صوتی، تبدیل گفتار به متن، پاسخ صوتی، خلاصه‌سازی جلسه و ثبت سریع داده بدون نیاز به کار با فرم‌های طولانی.",tags:["STT","TTS","Assistant"],icon:"mic",radius:1.34,ellipse:.69,phase:.82,speed:-.00016},
  {id:"alerts",title:"هشدار و پایش",summary:"پایش تأخیرها، SLA، ریسک و اقدامات باز و ایجاد هشدار برای مدیر، مسئول و دبیر فرایند با قابلیت پیگیری.",tags:["SLA","Risk","Monitoring"],icon:"alert",radius:1.25,ellipse:.78,phase:1.62,speed:.00021,accent:"orange"},
  {id:"security",title:"هویت و امنیت",summary:"ورود سازمانی، MFA، مدیریت Tenant، نقش‌ها، Secret Management و Anti-Bot برای استفاده امن و تجاری آوان.",tags:["Keycloak","MFA","RBAC"],icon:"shield",radius:1.47,ellipse:.64,phase:2.45,speed:-.00015}
 ];
 const icons={
  doc:'<path d="M6 3h8l4 4v14H6z"/><path d="M14 3v5h5M9 12h6M9 16h6"/>',
  chart:'<path d="M4 19V10m5 9V5m5 14v-7m5 7V8"/><path d="M3 19h18"/>',
  calendar:'<rect x="3.5" y="5" width="17" height="15" rx="2"/><path d="M7 3v4m10-4v4M3.5 10h17"/><path d="M8 14h3m2 0h3m-8 3h8"/>',
  flow:'<circle cx="6" cy="6" r="2.4"/><circle cx="18" cy="6" r="2.4"/><circle cx="12" cy="18" r="2.4"/><path d="M8.1 7.3 10.7 15m5.2-7.7L13.3 15M8.4 6h7.2"/>',
  spark:'<path d="m12 2 1.8 5.2L19 9l-5.2 1.8L12 16l-1.8-5.2L5 9l5.2-1.8L12 2Z"/><path d="m19 15 .9 2.6 2.6.9-2.6.9L19 22l-.9-2.6-2.6-.9 2.6-.9L19 15Z"/>',
  mic:'<rect x="9" y="3" width="6" height="12" rx="3"/><path d="M5.5 11.5A6.5 6.5 0 0 0 18.5 11.5M12 18v3m-4 0h8"/>',
  alert:'<path d="M12 3 2.8 20h18.4L12 3Z"/><path d="M12 9v5M12 17.5v.5"/>',
  shield:'<path d="M12 3 19 6v5c0 4.5-2.5 7.7-7 10-4.5-2.3-7-5.5-7-10V6z"/><path d="m9.2 12 1.8 1.8 3.8-4"/>'
 };
 let root=null,globeWrap=null,globeImg=null,canvas=null,ctx=null,tooltip=null,nodes=[];
 let raf=0,last=0,selected=null,resizeObserver=null;

 function sceneDataUrl(name){
  if(!SCRIPT_SRC)return name;
  if(SCRIPT_SRC.includes("/admin/assets/"))return new URL("scene-data/"+name,SCRIPT_SRC).href;
  return new URL("../scene-data/"+name,SCRIPT_SRC).href;
 }
 async function loadChunks(prefix,count){
  const parts=await Promise.all(Array.from({length:count},async(_,i)=>{
   const response=await fetch(sceneDataUrl(prefix+"-"+i+".b64"),{credentials:"same-origin",cache:"force-cache"});
   if(!response.ok)throw new Error("scene asset "+prefix+"-"+i+" returned HTTP "+response.status);
   return (await response.text()).replace(/\s+/g,"");
  }));
  return parts.join("");
 }
 async function loadAssets(){
  try{
   const [background,globe]=await Promise.all([loadChunks("bg",5),loadChunks("globe",2)]);
   if(!root)return;
   document.documentElement.style.setProperty("--avan-live-login-bg",'url("data:image/webp;base64,'+background+'")');
   globeImg.src="data:image/webp;base64,"+globe;
   root.classList.add("is-ready");
  }catch(error){
   if(root)root.classList.add("asset-error");
   console.warn("AVAN_LOGIN_SCENE_ASSET_ERROR",error);
  }
 }
 function buildOrbitSvg(){
  const svg=document.createElementNS("http://www.w3.org/2000/svg","svg");
  svg.setAttribute("class","avan-globe-orbits");
  svg.setAttribute("viewBox","0 0 100 100");
  svg.setAttribute("preserveAspectRatio","none");
  svg.setAttribute("aria-hidden","true");
  const values=[
   ["o1","49","23","-14"],
   ["o2","45","28","47"],
   ["o3","43","37","86"]
  ];
  values.forEach(([cls,rx,ry,rot])=>{
   const e=document.createElementNS("http://www.w3.org/2000/svg","ellipse");
   e.setAttribute("class",cls);e.setAttribute("cx","50");e.setAttribute("cy","50");
   e.setAttribute("rx",rx);e.setAttribute("ry",ry);e.setAttribute("transform","rotate("+rot+" 50 50)");
   svg.append(e);
  });
  return svg;
 }
 function buildScene(){
  root=document.createElement("div");root.className="avan-live-scene";root.setAttribute("data-avan-live-scene","");
  root.setAttribute("aria-hidden","false");
  globeWrap=document.createElement("div");globeWrap.className="avan-globe-wrap";globeWrap.setAttribute("aria-hidden","true");
  const halo=document.createElement("div");halo.className="avan-globe-halo";
  globeImg=document.createElement("img");globeImg.className="avan-globe-image";globeImg.alt="";globeImg.decoding="async";
  canvas=document.createElement("canvas");canvas.className="avan-globe-canvas";canvas.setAttribute("aria-hidden","true");
  ctx=canvas.getContext("2d");
  globeWrap.append(halo,globeImg,canvas,buildOrbitSvg());
  const layer=document.createElement("div");layer.className="avan-orbit-layer";
  tooltip=document.createElement("aside");tooltip.className="avan-scene-tooltip";tooltip.setAttribute("role","status");tooltip.setAttribute("aria-live","polite");
  nodes=caps.map(cap=>{
   const button=document.createElement("button");button.type="button";
   button.className="avan-orbit-node"+(cap.accent==="orange"?" orange":"");
   button.setAttribute("aria-label",cap.title);
   button.innerHTML='<span class="avan-orbit-icon"><svg viewBox="0 0 24 24" aria-hidden="true">'+icons[cap.icon]+'</svg></span><span class="avan-orbit-label">'+cap.title+'</span>';
   const node={cap,el:button,angle:cap.phase,hovered:false,x:0,y:0};
   button.addEventListener("mouseenter",()=>{node.hovered=true;showTip(node)});
   button.addEventListener("mouseleave",()=>{node.hovered=false;if(selected!==node)hideTip()});
   button.addEventListener("focus",()=>{node.hovered=true;showTip(node)});
   button.addEventListener("blur",()=>{node.hovered=false;if(selected!==node)hideTip()});
   button.addEventListener("click",()=>{
    selected=selected===node?null:node;
    nodes.forEach(n=>n.el.classList.toggle("is-selected",selected===n));
    if(selected)showTip(node);else hideTip();
   });
   layer.append(button);return node;
  });
  root.append(globeWrap,layer,tooltip);
  document.body.prepend(root);
  resizeCanvas();last=performance.now();raf=requestAnimationFrame(loop);
  loadAssets();
  if(window.ResizeObserver){
   resizeObserver=new ResizeObserver(resizeCanvas);resizeObserver.observe(globeWrap);
  }
 }
 function geometry(){
  const r=globeWrap.getBoundingClientRect();
  return {cx:r.left+r.width/2,cy:r.top+r.height/2,rad:r.width*.40};
 }
 function showTip(node){
  if(!tooltip)return;
  tooltip.replaceChildren();
  const title=document.createElement("strong");title.textContent=node.cap.title;
  const body=document.createElement("p");body.textContent=node.cap.summary;
  const tags=document.createElement("div");tags.className="avan-scene-tags";
  node.cap.tags.forEach(value=>{const tag=document.createElement("span");tag.textContent=value;tags.append(tag)});
  tooltip.append(title,body,tags);tooltip.classList.add("is-visible");placeTip(node);
 }
 function hideTip(){if(tooltip)tooltip.classList.remove("is-visible")}
 function placeTip(node){
  if(!tooltip)return;
  const r=node.el.getBoundingClientRect(),width=Math.min(350,innerWidth-28),height=155;
  let left=r.right+14,top=r.top-28;
  if(left+width>innerWidth-14)left=r.left-width-14;
  left=Math.max(14,left);top=Math.max(14,Math.min(innerHeight-height-14,top));
  tooltip.style.width=width+"px";tooltip.style.left=left+"px";tooltip.style.top=top+"px";
 }
 function resizeCanvas(){
  if(!canvas||!globeWrap||!ctx)return;
  const r=globeWrap.getBoundingClientRect(),dpr=Math.min(devicePixelRatio||1,2);
  if(!r.width||!r.height)return;
  canvas.width=Math.max(1,Math.round(r.width*dpr));canvas.height=Math.max(1,Math.round(r.height*dpr));
  canvas.style.width=r.width+"px";canvas.style.height=r.height+"px";
  ctx.setTransform(dpr,0,0,dpr,0,0);
 }
 function drawGlobe(t){
  if(!ctx||!globeWrap||REDUCED)return;
  const r=globeWrap.getBoundingClientRect(),W=r.width,H=r.height;
  if(!W||!H)return;
  const cx=W/2,cy=H/2,R=W*.37,rot=t*.00020;
  ctx.clearRect(0,0,W,H);ctx.save();ctx.globalCompositeOperation="screen";
  for(let lat=-70;lat<=70;lat+=10){
   const la=lat*Math.PI/180,cl=Math.cos(la),sl=Math.sin(la);
   for(let lon=0;lon<360;lon+=12){
    const lo=lon*Math.PI/180+rot,x3=cl*Math.cos(lo),y3=sl,z3=cl*Math.sin(lo);
    if(z3<-.22)continue;
    const x=cx+x3*R,y=cy-y3*R*.98,alpha=.12+.52*((z3+1)/2);
    ctx.fillStyle="rgba(91,236,248,"+alpha+")";
    ctx.beginPath();ctx.arc(x,y,z3>.45?1.45:.85,0,Math.PI*2);ctx.fill();
   }
  }
  ctx.lineWidth=1.3;ctx.shadowBlur=12;ctx.shadowColor="#61edf7";
  for(let i=0;i<3;i++){
   ctx.strokeStyle=i===1?"rgba(255,117,88,.38)":"rgba(88,232,246,.38)";
   ctx.beginPath();ctx.ellipse(cx,cy,R*(1.03+i*.08),R*(.46+i*.07),rot*(i%2?-.55:.7)+i*.8,0,Math.PI*2);ctx.stroke();
  }
  for(let i=0;i<18;i++){
   const a=rot*2.4+i*.71,rr=R*(1.02+(i%5)*.075);
   ctx.fillStyle=i%4===0?"rgba(255,112,82,.72)":"rgba(86,235,248,.68)";
   ctx.beginPath();ctx.arc(cx+Math.cos(a)*rr,cy+Math.sin(a)*rr*.62,i%3?1.15:1.9,0,Math.PI*2);ctx.fill();
  }
  ctx.restore();
 }
 function loop(now){
  if(!root)return;
  const dt=Math.min(40,Math.max(0,now-last));last=now;
  const g=geometry();
  nodes.forEach(node=>{
   if(!REDUCED&&!node.hovered)node.angle+=dt*node.cap.speed;
   const rr=g.rad*node.cap.radius;
   node.x=g.cx+Math.cos(node.angle)*rr;
   node.y=g.cy+Math.sin(node.angle)*rr*node.cap.ellipse+(REDUCED?0:Math.sin(now*.0018+node.cap.radius*9)*3.5);
   const half=(node.el.offsetWidth||64)/2;
   node.el.style.transform="translate3d("+(node.x-half)+"px,"+(node.y-half)+"px,0)";
   if(selected===node)placeTip(node);
  });
  drawGlobe(now);raf=requestAnimationFrame(loop);
 }
 function interactive(target){
  return !!target.closest("input,textarea,select,button,a,label,.avan-captcha,.otp-motion");
 }
 function makeDraggable(card){
  if(card.dataset.avanDraggable==="1")return;
  card.dataset.avanDraggable="1";
  let active=false,pointerId=null,startX=0,startY=0,baseX=Number(card.dataset.dragX||0),baseY=Number(card.dataset.dragY||0);
  const move=event=>{
   if(!active||event.pointerId!==pointerId)return;
   const currentX=Number(card.dataset.dragX||0),currentY=Number(card.dataset.dragY||0);
   const rect=card.getBoundingClientRect(),baseLeft=rect.left-currentX,baseTop=rect.top-currentY,margin=12;
   let nextX=baseX+(event.clientX-startX),nextY=baseY+(event.clientY-startY);
   nextX=Math.min(innerWidth-margin-baseLeft-rect.width,Math.max(margin-baseLeft,nextX));
   nextY=Math.min(innerHeight-margin-baseTop-rect.height,Math.max(margin-baseTop,nextY));
   card.dataset.dragX=String(nextX);card.dataset.dragY=String(nextY);card.style.translate=nextX+"px "+nextY+"px";
  };
  const stop=event=>{
   if(!active||event.pointerId!==pointerId)return;
   active=false;card.dataset.dragging="0";card.classList.remove("is-login-dragging");
   baseX=Number(card.dataset.dragX||0);baseY=Number(card.dataset.dragY||0);
   try{card.releasePointerCapture(pointerId)}catch(_){}
   pointerId=null;
  };
  card.addEventListener("pointerdown",event=>{
   if(event.button!==0||innerWidth<820||interactive(event.target))return;
   active=true;pointerId=event.pointerId;startX=event.clientX;startY=event.clientY;
   baseX=Number(card.dataset.dragX||0);baseY=Number(card.dataset.dragY||0);
   card.dataset.dragging="1";card.classList.add("is-login-dragging");card.setPointerCapture(pointerId);event.preventDefault();
  });
  card.addEventListener("pointermove",move);card.addEventListener("pointerup",stop);card.addEventListener("pointercancel",stop);
  card.addEventListener("dblclick",event=>{
   if(interactive(event.target))return;
   card.dataset.dragX="0";card.dataset.dragY="0";card.style.translate="0px 0px";
  });
 }
 function parallax(event){
  if(!globeWrap||innerWidth<900||REDUCED)return;
  const dx=(event.clientX/innerWidth-.5)*7,dy=(event.clientY/innerHeight-.5)*5;
  globeWrap.style.translate=dx+"px "+dy+"px";
 }
 function teardown(){
  cancelAnimationFrame(raf);raf=0;
  if(resizeObserver){resizeObserver.disconnect();resizeObserver=null}
  if(root)root.remove();
  root=globeWrap=globeImg=canvas=ctx=tooltip=null;nodes=[];selected=null;
  document.body.classList.remove("avan-live-login-enabled");
  document.documentElement.style.removeProperty("--avan-live-login-bg");
 }
 function sync(){
  const card=document.querySelector(".login-reveal-card");
  if(card){
   document.body.classList.add("avan-live-login-enabled");
   if(!root)buildScene();
   makeDraggable(card);
  }else if(root)teardown();
 }
 window.addEventListener("resize",resizeCanvas,{passive:true});
 window.addEventListener("pointermove",parallax,{passive:true});
 if(document.readyState==="loading")document.addEventListener("DOMContentLoaded",sync,{once:true});else sync();
 new MutationObserver(sync).observe(document.documentElement,{subtree:true,childList:true});
})();