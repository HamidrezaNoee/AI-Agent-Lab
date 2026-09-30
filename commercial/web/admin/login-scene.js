"use strict";
(function(){
 const source=document.currentScript||document.querySelector('script[src*="login-scene.js"]');
 const appearanceUrl=source?.dataset.appearanceUrl||"/admin/api/appearance/public";
 const sceneRoot=source?.dataset.sceneRoot||"/admin/assets/scene-data/";
 const fallback={
  background_image:"",background_position:"center",background_brightness:1.10,background_dim:.05,
  globe_scale:1.18,globe_brightness:1.24,globe_saturation:1.18,globe_glow:1.15,
  node_size:68,hover_scale:1.22,hover_mode:"card",pause_on_hover:true,show_orbits:true,
  show_idle_cards:true,orbit_speed:1,
  elements:[
   {id:"docs",enabled:true,title:"مدیریت اسناد",subtitle:"استخراج، طبقه‌بندی و جستجوی هوشمند",description:"تحلیل قرارداد، صورت‌جلسه، گزارش و فایل و تبدیل محتوا به Context قابل استفاده برای Agent.",tags:["Documents","Extraction","RAG"],accent:"#63ECFF",r:1.22,e:.70,a:4.35,s:-.00014,svg:'<svg viewBox="0 0 24 24"><path d="M6 3h8l4 4v14H6z"/><path d="M14 3v5h5M9 12h6m-6 4h6"/></svg>'},
   {id:"bi",enabled:true,title:"تحلیل و گزارشات",subtitle:"داشبوردها و هوش تجاری",description:"KPI، تحلیل روند، گزارش مدیریتی و یافتن گلوگاه‌ها روی داده واقعی سازمان.",tags:["Power BI","KPI","Root Cause"],accent:"#65EEF2",r:1.40,e:.64,a:3.35,s:.00013,svg:'<svg viewBox="0 0 24 24"><path d="M4 19V10m5 9V5m5 14v-7m5 7V8"/><path d="M3 19h18"/></svg>'},
   {id:"meetings",enabled:true,title:"جلسات و مصوبات",subtitle:"مدیریت جلسات، مصوبات و پیگیری",description:"چرخه جلسه، اقدام، مسئول، موعد، پیشرفت و ارزیابی نتیجه.",tags:["Minutes","Actions","Follow-up"],accent:"#FF7358",r:1.25,e:.76,a:2.85,s:-.00016,svg:'<svg viewBox="0 0 24 24"><circle cx="8" cy="9" r="3"/><circle cx="16" cy="9" r="3"/><path d="M3.5 19c.8-3.2 2.8-5 5.5-5s4.7 1.8 5.5 5M12.5 15c.8-.7 1.8-1 2.9-1 2.6 0 4.5 1.7 5.1 5"/></svg>'},
   {id:"bpms",enabled:true,title:"اتصالات BPMS",subtitle:"ProcessMaker، Camunda و سایر موتورها",description:"کاتالوگ اتصال موتورهای فرایندی با تست، OAuth و کنترل دسترسی.",tags:["ProcessMaker","BPMS","OAuth"],accent:"#61EAF7",r:1.42,e:.62,a:5.55,s:-.00012,svg:'<svg viewBox="0 0 24 24"><circle cx="6" cy="6" r="2.4"/><circle cx="18" cy="6" r="2.4"/><circle cx="12" cy="18" r="2.4"/><path d="M8.1 7.3 10.7 15m5.2-7.7L13.3 15M8.4 6h7.2"/></svg>'},
   {id:"agent",enabled:true,title:"Agent هوشمند",subtitle:"اتوماسیون فرایندها با AI",description:"Agentهای تخصصی برای تحلیل، تصمیم‌یار و اجرای کنترل‌شده Workflowها.",tags:["Agents","Tools","Workflow"],accent:"#FF8064",r:1.20,e:.74,a:.05,s:.00017,svg:'<svg viewBox="0 0 24 24"><rect x="4" y="7" width="16" height="12" rx="3"/><path d="M9 7V4m6 3V4M8 13h.01M16 13h.01M9 16h6"/></svg>'},
   {id:"voice",enabled:true,title:"دستیار صوتی",subtitle:"تعامل صوتی و گفتگوی طبیعی",description:"ورودی و پاسخ صوتی، خلاصه‌سازی و ثبت سریع اطلاعات.",tags:["STT","TTS","Assistant"],accent:"#68EEEF",r:1.39,e:.67,a:.75,s:-.00014,svg:'<svg viewBox="0 0 24 24"><rect x="9" y="3" width="6" height="12" rx="3"/><path d="M5.5 11.5A6.5 6.5 0 0 0 18.5 11.5M12 18v3m-4 0h8"/></svg>'},
   {id:"alert",enabled:true,title:"هشدار و نظارت",subtitle:"پایش، یادآورها و اعلان‌های هوشمند",description:"پایش SLA، ریسک، تأخیر و اقدامات باز با هشدارهای قابل پیگیری.",tags:["SLA","Risk","Monitoring"],accent:"#FF7459",r:1.29,e:.75,a:1.45,s:.00018,svg:'<svg viewBox="0 0 24 24"><path d="M12 3 2.8 20h18.4L12 3Z"/><path d="M12 9v5M12 17.5v.5"/></svg>'},
   {id:"security",enabled:true,title:"هویت و امنیت",subtitle:"مدیریت کاربران و دسترسی‌ها",description:"OIDC، MFA، Tenant، نقش‌ها، Secret Management و Anti-Bot.",tags:["Keycloak","MFA","RBAC"],accent:"#67F1D0",r:1.45,e:.62,a:2.25,s:-.00013,svg:'<svg viewBox="0 0 24 24"><path d="M12 3 19 6v5c0 4.5-2.5 7.7-7 10-4.5-2.3-7-5.5-7-10V6z"/><path d="m9.2 12 1.8 1.8 3.8-4"/></svg>'}
  ]
 };
 let config=fallback,root=null,wrap=null,canvas=null,ctx=null,layer=null,tooltip=null,nodes=[],selected=null,raf=0,last=0,card=null,observer=null;
 let assetsPromise=null,configPromise=null;

 const num=(v,d)=>Number.isFinite(Number(v))?Number(v):d;
 const safeText=v=>String(v??"");
 async function fetchText(url){const r=await fetch(url,{cache:"no-store"});if(!r.ok)throw Error("asset");return (await r.text()).trim()}
 async function asset(prefix,count){
  const parts=await Promise.all(Array.from({length:count},(_,i)=>fetchText(sceneRoot+prefix+"-"+i+".b64")));
  return "data:image/webp;base64,"+parts.join("");
 }
 function loadAssets(){
  if(!assetsPromise)assetsPromise=Promise.all([asset("bg",5),asset("globe",2)]).catch(()=>["",""]);
  return assetsPromise;
 }
 function loadConfig(){
  if(!configPromise)configPromise=fetch(appearanceUrl+(appearanceUrl.includes("?")?"&":"?")+"v="+Date.now(),{cache:"no-store"})
   .then(r=>r.ok?r.json():fallback).catch(()=>fallback);
  return configPromise;
 }
 function mergeConfig(raw){
  const result={...fallback,...(raw&&typeof raw==="object"?raw:{})};
  result.elements=Array.isArray(raw?.elements)&&raw.elements.length?raw.elements:fallback.elements;
  return result;
 }

 function applySceneStyle(background){
  root.style.setProperty("--scene-bg-brightness",String(num(config.background_brightness,1.1)));
  root.style.setProperty("--scene-dim",String(num(config.background_dim,.05)));
  root.style.setProperty("--globe-scale",String(num(config.globe_scale,1.18)));
  root.style.setProperty("--globe-brightness",String(num(config.globe_brightness,1.24)));
  root.style.setProperty("--globe-saturation",String(num(config.globe_saturation,1.18)));
  root.style.setProperty("--globe-glow",String(num(config.globe_glow,1.15)));
  root.style.setProperty("--node-size",num(config.node_size,68)+"px");
  root.style.setProperty("--hover-scale",String(num(config.hover_scale,1.22)));
  const bg=config.background_image||background;
  const backdrop=root.querySelector(".avan-live-backdrop");
  if(bg)backdrop.style.backgroundImage='url("'+bg.replaceAll('"','%22')+'")';
  backdrop.style.backgroundPosition=config.background_position||"center";
  root.classList.toggle("hide-orbits",config.show_orbits===false);
  root.classList.toggle("idle-cards",!!config.show_idle_cards);
  ["card","tooltip","label","glow","none"].forEach(x=>root.classList.toggle("hover-"+x,(config.hover_mode||"card")===x));
 }

 async function makeScene(){
  if(root)return;
  const [appearance,assets]=await Promise.all([loadConfig(),loadAssets()]);
  config=mergeConfig(appearance);
  if(!document.querySelector(".login-reveal-card,.panel.login,.signin-panel.login-reveal-card"))return;
  root=document.createElement("div");
  root.className="avan-live-scene avan-v3-scene";
  root.setAttribute("data-avan-live-scene","configurable-v3");
  const backdrop=document.createElement("div");backdrop.className="avan-live-backdrop";
  const stage=document.createElement("div");stage.className="avan-live-stage";
  wrap=document.createElement("div");wrap.className="avan-globe-wrap";wrap.setAttribute("aria-hidden","true");
  wrap.innerHTML='<div class="avan-globe-halo"></div><img class="avan-globe-image" alt=""><canvas class="avan-globe-canvas"></canvas><svg class="avan-globe-orbits" viewBox="0 0 100 100" preserveAspectRatio="none"><ellipse class="o1" cx="50" cy="50" rx="49" ry="23" transform="rotate(-14 50 50)"/><ellipse class="o2" cx="50" cy="50" rx="45" ry="28" transform="rotate(47 50 50)"/><ellipse class="o3" cx="50" cy="50" rx="43" ry="37" transform="rotate(86 50 50)"/></svg>';
  const globe=wrap.querySelector(".avan-globe-image");if(assets[1])globe.src=assets[1];
  stage.append(wrap);
  layer=document.createElement("div");layer.className="avan-orbit-layer";
  tooltip=document.createElement("aside");tooltip.className="avan-scene-tooltip";tooltip.setAttribute("role","status");tooltip.setAttribute("aria-live","polite");
  root.append(backdrop,stage,layer,tooltip);document.body.prepend(root);
  canvas=wrap.querySelector(".avan-globe-canvas");ctx=canvas.getContext("2d");
  applySceneStyle(assets[0]);renderNodes();resizeCanvas();root.classList.add("is-ready");
  last=performance.now();cancelAnimationFrame(raf);raf=requestAnimationFrame(animate);
 }

 function renderNodes(){
  layer.replaceChildren();nodes=[];selected=null;
  const items=(config.elements||[]).filter(x=>x&&x.enabled!==false).slice(0,12);
  for(const cap of items){
   const el=document.createElement("button");el.type="button";el.className="avan-orbit-node";
   el.style.setProperty("--node-accent",cap.accent||"#63ECFF");el.setAttribute("aria-label",safeText(cap.title));
   const icon=document.createElement("span");icon.className="avan-orbit-icon";icon.innerHTML=cap.svg||fallback.elements[0].svg;
   const label=document.createElement("span");label.className="avan-orbit-label";label.textContent=safeText(cap.title);
   const cardBox=document.createElement("span");cardBox.className="avan-cap-card";
   const title=document.createElement("strong");title.textContent=safeText(cap.title);
   const sub=document.createElement("small");sub.textContent=safeText(cap.subtitle);
   const tagBox=document.createElement("span");tagBox.className="avan-cap-card-tags";
   for(const tag of (Array.isArray(cap.tags)?cap.tags:[]).slice(0,8)){const t=document.createElement("em");t.textContent=safeText(tag);tagBox.append(t)}
   cardBox.append(title,sub,tagBox);el.append(icon,label,cardBox);
   const node={cap:{...cap,r:num(cap.radius??cap.r,1.2),e:num(cap.ellipse??cap.e,.7),a:num(cap.angle??cap.a,0),s:num(cap.speed??cap.s,.00015)},el,pause:false};
   el.addEventListener("mouseenter",()=>{if(config.pause_on_hover)node.pause=true;if(config.hover_mode==="tooltip")showTip(node)});
   el.addEventListener("mouseleave",()=>{node.pause=false;if(selected!==node)hideTip()});
   el.addEventListener("focus",()=>{if(config.pause_on_hover)node.pause=true;if(config.hover_mode==="tooltip")showTip(node)});
   el.addEventListener("blur",()=>{node.pause=false;if(selected!==node)hideTip()});
   el.addEventListener("click",()=>{selected=selected===node?null:node;nodes.forEach(x=>x.el.classList.toggle("is-selected",x===selected));if(selected&&config.hover_mode==="tooltip")showTip(node);else if(!selected)hideTip()});
   layer.append(el);nodes.push(node);
  }
 }

 function globeGeometry(){const r=wrap.getBoundingClientRect();return {cx:r.left+r.width/2,cy:r.top+r.height/2,rad:r.width*.40}}
 function showTip(node){
  const c=node.cap;tooltip.replaceChildren();
  const title=document.createElement("strong");title.textContent=safeText(c.title);
  const p=document.createElement("p");p.textContent=safeText(c.description||c.subtitle);
  const tags=document.createElement("div");tags.className="avan-scene-tags";
  for(const tag of (Array.isArray(c.tags)?c.tags:[]).slice(0,8)){const t=document.createElement("span");t.textContent=safeText(tag);tags.append(t)}
  tooltip.append(title,p,tags);tooltip.classList.add("is-visible");positionTip(node);
 }
 function positionTip(node){
  const rr=node.el.getBoundingClientRect(),tw=Math.min(360,innerWidth-28),th=165;let left=rr.right+14,top=rr.top-28;
  if(left+tw>innerWidth-14)left=rr.left-tw-14;left=Math.max(14,left);top=Math.max(14,Math.min(innerHeight-th-14,top));
  tooltip.style.left=left+"px";tooltip.style.top=top+"px";
 }
 function hideTip(){tooltip?.classList.remove("is-visible")}

 function resizeCanvas(){
  if(!wrap||!canvas||!ctx)return;const r=wrap.getBoundingClientRect(),dpr=Math.min(devicePixelRatio||1,2);
  canvas.width=Math.max(1,Math.round(r.width*dpr));canvas.height=Math.max(1,Math.round(r.height*dpr));canvas.style.width=r.width+"px";canvas.style.height=r.height+"px";ctx.setTransform(dpr,0,0,dpr,0,0);
 }
 function drawGlobe(t){
  if(!ctx||!wrap)return;const r=wrap.getBoundingClientRect(),W=r.width,H=r.height,cx=W/2,cy=H/2,R=W*.39;ctx.clearRect(0,0,W,H);const rot=t*.00022;
  ctx.save();ctx.globalCompositeOperation="screen";
  const ring=ctx.createRadialGradient(cx,cy,R*.55,cx,cy,R*1.02);ring.addColorStop(0,"rgba(20,176,216,.015)");ring.addColorStop(.76,"rgba(37,220,245,.04)");ring.addColorStop(1,"rgba(89,242,255,.28)");
  ctx.fillStyle=ring;ctx.beginPath();ctx.arc(cx,cy,R*1.02,0,Math.PI*2);ctx.fill();
  for(let lat=-70;lat<=70;lat+=10){const la=lat*Math.PI/180,cl=Math.cos(la),sl=Math.sin(la);for(let lon=0;lon<360;lon+=12){const lo=lon*Math.PI/180+rot,x3=cl*Math.cos(lo),y3=sl,z3=cl*Math.sin(lo);if(z3<-.18)continue;const x=cx+x3*R,y=cy-y3*R*.98,alpha=.12+.48*((z3+1)/2);ctx.fillStyle="rgba(102,240,251,"+alpha+")";ctx.beginPath();ctx.arc(x,y,z3>.45?1.5:.8,0,Math.PI*2);ctx.fill()}}
  ctx.lineWidth=1.35;ctx.shadowBlur=15;ctx.shadowColor="#62eff9";
  for(let i=0;i<3;i++){ctx.strokeStyle=i===1?"rgba(255,112,83,.42)":"rgba(88,232,246,.44)";ctx.beginPath();ctx.ellipse(cx,cy,R*(1.05+i*.08),R*(.46+i*.07),rot*(i%2?-.55:.7)+i*.8,0,Math.PI*2);ctx.stroke()}
  for(let i=0;i<24;i++){const a=rot*2.5+i*.57,rr=R*(1.03+(i%5)*.075);ctx.fillStyle=i%5===0?"rgba(255,108,78,.82)":"rgba(94,239,250,.76)";ctx.beginPath();ctx.arc(cx+Math.cos(a)*rr,cy+Math.sin(a)*rr*.62,(i%3?1.2:2),0,Math.PI*2);ctx.fill()}
  ctx.restore();
 }
 function animate(now){
  if(!root||!wrap)return;const dt=Math.min(40,Math.max(0,now-last));last=now;const g=globeGeometry(),speed=num(config.orbit_speed,1);
  for(const node of nodes){const c=node.cap;if(!node.pause)c.a+=dt*c.s*speed;const rr=g.rad*c.r,x=g.cx+Math.cos(c.a)*rr,y=g.cy+Math.sin(c.a)*rr*c.e+Math.sin(now*.0018+c.r*9)*3.5,half=(node.el.offsetWidth||num(config.node_size,68))/2;node.el.style.transform="translate3d("+(x-half)+"px,"+(y-half)+"px,0)";node.el.classList.toggle("card-left",x<g.cx);node.el.classList.toggle("card-right",x>=g.cx);if(selected===node&&config.hover_mode==="tooltip")positionTip(node)}
  drawGlobe(now);raf=requestAnimationFrame(animate);
 }
 function isInteractive(target){return !!target.closest("input,textarea,select,button,a,label,form,.avan-captcha,.otp-motion")}
 function enableDrag(target){
  if(!target||target.dataset.avanDraggable==="1")return;target.dataset.avanDraggable="1";let active=false,pid=null,sx=0,sy=0,bx=0,by=0;
  const move=e=>{if(!active||e.pointerId!==pid)return;const cx=Number(target.dataset.dragX||0),cy=Number(target.dataset.dragY||0),rect=target.getBoundingClientRect(),baseLeft=rect.left-cx,baseTop=rect.top-cy,margin=12;let nx=bx+(e.clientX-sx),ny=by+(e.clientY-sy);nx=Math.min(innerWidth-margin-baseLeft-rect.width,Math.max(margin-baseLeft,nx));ny=Math.min(innerHeight-margin-baseTop-rect.height,Math.max(margin-baseTop,ny));target.dataset.dragX=String(nx);target.dataset.dragY=String(ny);target.style.translate=nx+"px "+ny+"px"};
  const end=e=>{if(!active||e.pointerId!==pid)return;active=false;target.dataset.dragging="0";target.classList.remove("is-login-dragging");bx=Number(target.dataset.dragX||0);by=Number(target.dataset.dragY||0);try{target.releasePointerCapture(pid)}catch(_){}pid=null};
  target.addEventListener("pointerdown",e=>{if(e.button!==0||innerWidth<820||isInteractive(e.target))return;active=true;pid=e.pointerId;sx=e.clientX;sy=e.clientY;bx=Number(target.dataset.dragX||0);by=Number(target.dataset.dragY||0);target.dataset.dragging="1";target.classList.add("is-login-dragging");target.setPointerCapture(pid);e.preventDefault()});
  target.addEventListener("pointermove",move);target.addEventListener("pointerup",end);target.addEventListener("pointercancel",end);target.addEventListener("dblclick",e=>{if(isInteractive(e.target))return;target.dataset.dragX="0";target.dataset.dragY="0";target.style.translate="0px 0px"});
 }
 function teardown(){cancelAnimationFrame(raf);raf=0;last=0;selected=null;nodes=[];root?.remove();root=wrap=canvas=ctx=layer=tooltip=null;document.body.classList.remove("avan-live-login-enabled")}
 function sync(){
  const next=document.querySelector(".login-reveal-card,.panel.login,.signin-panel.login-reveal-card");
  if(next){card=next;document.body.classList.add("avan-live-login-enabled");makeScene().catch(()=>{});enableDrag(card)}
  else if(root){teardown();card=null}
 }
 addEventListener("resize",()=>{resizeCanvas();if(selected&&config.hover_mode==="tooltip")positionTip(selected)},{passive:true});
 document.addEventListener("pointermove",e=>{if(!wrap||innerWidth<900)return;wrap.style.translate=((e.clientX/innerWidth-.5)*8)+"px "+((e.clientY/innerHeight-.5)*6)+"px"},{passive:true});
 if(document.readyState==="loading")document.addEventListener("DOMContentLoaded",sync,{once:true});else sync();
 observer=new MutationObserver(sync);observer.observe(document.documentElement,{subtree:true,childList:true});
})();