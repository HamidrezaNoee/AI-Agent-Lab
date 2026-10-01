"use strict";
(function(){
 const script=document.currentScript||document.querySelector('script[src*="login-scene.js"]');
 const appearanceUrl=script?.dataset.appearanceUrl||"/admin/api/appearance/public";
 const sceneRoot=script?.dataset.sceneRoot||"/admin/assets/scene-data/";
 const icons={
  docs:'<svg viewBox="0 0 24 24"><path d="M6 3h8l4 4v14H6z"/><path d="M14 3v5h5M9 12h6m-6 4h6"/></svg>',
  bi:'<svg viewBox="0 0 24 24"><path d="M4 19V10m5 9V5m5 14v-7m5 7V8"/><path d="M3 19h18"/></svg>',
  meetings:'<svg viewBox="0 0 24 24"><circle cx="8" cy="9" r="3"/><circle cx="16" cy="9" r="3"/><path d="M3.5 19c.8-3.2 2.8-5 5.5-5s4.7 1.8 5.5 5M12.5 15c.8-.7 1.8-1 2.9-1 2.6 0 4.5 1.7 5.1 5"/></svg>',
  bpms:'<svg viewBox="0 0 24 24"><circle cx="6" cy="6" r="2.4"/><circle cx="18" cy="6" r="2.4"/><circle cx="12" cy="18" r="2.4"/><path d="M8.1 7.3 10.7 15m5.2-7.7L13.3 15M8.4 6h7.2"/></svg>',
  agent:'<svg viewBox="0 0 24 24"><rect x="4" y="7" width="16" height="12" rx="3"/><path d="M9 7V4m6 3V4M8 13h.01M16 13h.01M9 16h6"/></svg>',
  voice:'<svg viewBox="0 0 24 24"><rect x="9" y="3" width="6" height="12" rx="3"/><path d="M5.5 11.5A6.5 6.5 0 0 0 18.5 11.5M12 18v3m-4 0h8"/></svg>',
  alert:'<svg viewBox="0 0 24 24"><path d="M12 3 2.8 20h18.4L12 3Z"/><path d="M12 9v5M12 17.5v.5"/></svg>',
  security:'<svg viewBox="0 0 24 24"><path d="M12 3 19 6v5c0 4.5-2.5 7.7-7 10-4.5-2.3-7-5.5-7-10V6z"/><path d="m9.2 12 1.8 1.8 3.8-4"/></svg>'
 };
 const baseElements=[
  ["docs","مدیریت اسناد","استخراج، طبقه‌بندی و جستجوی هوشمند","#63ECFF",1.22,.70,4.35,-.00014],
  ["bi","تحلیل و گزارشات","داشبوردها و هوش تجاری","#65EEF2",1.40,.64,3.35,.00013],
  ["meetings","جلسات و مصوبات","مدیریت جلسات، مصوبات و پیگیری","#FF7358",1.25,.76,2.85,-.00016],
  ["bpms","اتصالات BPMS","ProcessMaker، Camunda و سایر موتورها","#61EAF7",1.42,.62,5.55,-.00012],
  ["agent","Agent هوشمند","اتوماسیون فرایندها با AI","#FF8064",1.20,.74,.05,.00017],
  ["voice","دستیار صوتی","تعامل صوتی و گفتگوی طبیعی","#68EEEF",1.39,.67,.75,-.00014],
  ["alert","هشدار و نظارت","پایش، یادآورها و اعلان‌های هوشمند","#FF7459",1.29,.75,1.45,.00018],
  ["security","هویت و امنیت","مدیریت کاربران و دسترسی‌ها","#67F1D0",1.45,.62,2.25,-.00013]
 ];
 const fallback={
  version:5,background_image:"",background_fit:"cover",background_position_x:50,background_position_y:50,
  background_brightness:1.12,background_contrast:1.08,background_saturation:1.08,background_blur:0,background_dim:.03,
  overlay_color:"#031522",overlay_opacity:.05,background_parallax:6,
  globe_image:"",globe_visible:true,globe_x:29,globe_y:44,globe_scale:1.22,globe_opacity:1,globe_brightness:1.32,
  globe_contrast:1.10,globe_saturation:1.22,globe_hue:0,globe_glow:1.30,globe_wobble:1,globe_rotation_speed:1,
  globe_point_density:1,globe_point_size:1,globe_point_opacity:1,
  node_size:70,node_opacity:1,node_border_width:1,node_glow:1,hover_scale:1.24,hover_duration:180,
  hover_mode:"card",pause_on_hover:true,show_orbits:true,show_idle_cards:true,orbit_speed:.22,orbit_mode:"orbit",
  orbit_line_width:1.15,orbit_opacity:.78,orbit_glow:1,orbit_primary:"#50EAF7",orbit_secondary:"#FF7053",
  card_width:176,card_opacity:.94,
  elements:baseElements.map(([id,title,subtitle,accent,radius,ellipse,angle,speed])=>({
   id,enabled:true,title,subtitle,description:subtitle,tags:[],svg:icons[id],accent,radius,ellipse,angle,speed,
   size:0,hover_scale:0,glow:1,opacity:1,card_side:"auto",label_mode:"inherit"
  }))
 };
 let config=fallback,root=null,wrap=null,canvas=null,ctx=null,layer=null,tooltip=null,nodes=[],selected=null,raf=0,last=0,card=null,observer=null;
 let assetsPromise=null,configPromise=null,backdrop=null,creating=null,geometry=null,sceneTime=0;
 const reduced=matchMedia("(prefers-reduced-motion: reduce)");
 const compact=matchMedia("(max-width: 819px)");
 const loginSelector=".login-reveal-card,.panel.login,.signin-panel.signin-otp";
 const animating=()=>root&&!document.hidden&&!reduced.matches&&!compact.matches;

 const num=(v,d)=>Number.isFinite(Number(v))?Number(v):d;
 const safeText=v=>String(v??"");
 const clamp=(v,a,b)=>Math.max(a,Math.min(b,v));
 function hexRgb(hex){
  const m=/^#([0-9a-f]{6})$/i.exec(String(hex||""));if(!m)return [80,234,247];
  const n=parseInt(m[1],16);return [(n>>16)&255,(n>>8)&255,n&255];
 }
 function rgba(hex,a){const [r,g,b]=hexRgb(hex);return "rgba("+r+","+g+","+b+","+clamp(a,0,1)+")"}
 function loadAssets(){
  if(!assetsPromise)assetsPromise=Promise.resolve([sceneRoot+"boardroom-v5.webp",sceneRoot+"globe-v5.webp"]);
  return assetsPromise;
 }
 function loadConfig(){
  if(!configPromise)configPromise=fetch(appearanceUrl+(appearanceUrl.includes("?")?"&":"?")+"v="+Date.now(),{cache:"no-store"})
   .then(r=>r.ok?r.json():fallback).catch(()=>fallback);
  return configPromise;
 }
 function mergeConfig(raw){const r={...fallback,...(raw&&typeof raw==="object"?raw:{})};r.elements=Array.isArray(raw?.elements)?raw.elements:fallback.elements;return r}

 function applySceneStyle(background){
  const set=(k,v)=>root.style.setProperty(k,String(v));
  set("--scene-bg-brightness",num(config.background_brightness,1.12));
  set("--scene-bg-contrast",num(config.background_contrast,1.08));
  set("--scene-bg-saturation",num(config.background_saturation,1.08));
  set("--scene-bg-blur",num(config.background_blur,0)+"px");
  set("--overlay-rgba",rgba(config.overlay_color||"#031522",num(config.overlay_opacity,.05)));
  set("--scene-dim",num(config.background_dim,.03));
  set("--globe-x",num(config.globe_x,29)+"%");
  set("--globe-y",num(config.globe_y,44)+"%");
  set("--globe-scale",num(config.globe_scale,1.22));
  set("--globe-opacity",num(config.globe_opacity,1));
  set("--globe-brightness",num(config.globe_brightness,1.32));
  set("--globe-contrast",num(config.globe_contrast,1.10));
  set("--globe-saturation",num(config.globe_saturation,1.22));
  set("--globe-hue",num(config.globe_hue,0)+"deg");
  set("--globe-glow",num(config.globe_glow,1.30));
  const wobble=num(config.globe_wobble,1);
  set("--globe-wobble",wobble);
  set("--globe-rot-a",(-.7*wobble)+"deg");
  set("--globe-rot-b",(.8*wobble)+"deg");
  set("--globe-rot-c",(-.25*wobble)+"deg");
  set("--globe-scale-b",1+.018*wobble);
  set("--globe-scale-c",1+.008*wobble);
  set("--node-size",num(config.node_size,70)+"px");
  set("--node-opacity",num(config.node_opacity,1));
  set("--node-border-width",num(config.node_border_width,1)+"px");
  set("--node-glow",num(config.node_glow,1));
  set("--hover-scale",num(config.hover_scale,1.24));
  set("--hover-duration",num(config.hover_duration,180)+"ms");
  set("--orbit-line-width",num(config.orbit_line_width,1.15));
  set("--orbit-opacity",num(config.orbit_opacity,.78));
  set("--orbit-glow",num(config.orbit_glow,1));
  set("--orbit-primary",config.orbit_primary||"#50EAF7");
  set("--orbit-secondary",config.orbit_secondary||"#FF7053");
  set("--card-width",num(config.card_width,176)+"px");
  set("--card-opacity",num(config.card_opacity,.94));
  const bg=config.background_image||background;
  if(bg)backdrop.style.backgroundImage='url("'+bg.replaceAll('"','%22')+'")';
  const fit=config.background_fit||"cover";
  backdrop.style.backgroundSize=fit==="stretch"?"100% 100%":fit==="auto"?"auto":fit;
  backdrop.style.backgroundPosition=num(config.background_position_x,50)+"% "+num(config.background_position_y,50)+"%";
  root.classList.toggle("hide-orbits",config.show_orbits===false);
  root.classList.toggle("hide-globe",config.globe_visible===false);
  root.classList.toggle("idle-cards",!!config.show_idle_cards);
  ["card","tooltip","label","glow","none"].forEach(x=>root.classList.toggle("hover-"+x,(config.hover_mode||"card")===x));
 }

 async function makeScene(){
  if(root)return;
  const [appearance,assets]=await Promise.all([loadConfig(),loadAssets()]);
  config=mergeConfig(appearance);
  if(!document.querySelector(loginSelector))return;
  root=document.createElement("div");root.className="avan-live-scene avan-v4-scene";root.setAttribute("data-avan-live-scene","configurable-v4");
  backdrop=document.createElement("div");backdrop.className="avan-live-backdrop";
  const stage=document.createElement("div");stage.className="avan-live-stage";
  wrap=document.createElement("div");wrap.className="avan-globe-wrap";wrap.setAttribute("aria-hidden","true");
  wrap.innerHTML='<div class="avan-globe-halo"></div><img class="avan-globe-image" alt=""><canvas class="avan-globe-canvas"></canvas><svg class="avan-globe-orbits" viewBox="0 0 100 100" preserveAspectRatio="none"><ellipse class="o1" cx="50" cy="50" rx="49" ry="23" transform="rotate(-14 50 50)"/><ellipse class="o2" cx="50" cy="50" rx="45" ry="28" transform="rotate(47 50 50)"/><ellipse class="o3" cx="50" cy="50" rx="43" ry="37" transform="rotate(86 50 50)"/></svg>';
  const globe=wrap.querySelector(".avan-globe-image");globe.src=config.globe_image||assets[1]||"";
  stage.append(wrap);layer=document.createElement("div");layer.className="avan-orbit-layer";
  tooltip=document.createElement("aside");tooltip.className="avan-scene-tooltip";tooltip.setAttribute("role","status");tooltip.setAttribute("aria-live","polite");
  root.append(backdrop,stage,layer,tooltip);document.body.prepend(root);
  canvas=wrap.querySelector(".avan-globe-canvas");ctx=canvas.getContext("2d");
  applySceneStyle(assets[0]);renderNodes();resizeCanvas();root.classList.add("is-ready");
  updateMotion();
 }

 function renderNodes(){
  layer.replaceChildren();nodes=[];selected=null;
  const items=(config.elements||[]).filter(x=>x&&x.enabled!==false).slice(0,12);
  for(const cap of items){
   const el=document.createElement("button");el.type="button";el.className="avan-orbit-node";
   el.style.setProperty("--node-accent",cap.accent||"#63ECFF");
   el.style.setProperty("--node-size-local",(num(cap.size,0)>0?num(cap.size,70):num(config.node_size,70))+"px");
   el.style.setProperty("--node-hover-local",num(cap.hover_scale,0)>0?num(cap.hover_scale,1.24):num(config.hover_scale,1.24));
   const combinedGlow=num(cap.glow,1)*num(config.node_glow,1);
   el.style.setProperty("--node-glow-local",num(cap.glow,1));
   el.style.setProperty("--node-glow-blur",(28*combinedGlow)+"px");
   el.style.setProperty("--node-hover-glow-blur",(48*combinedGlow)+"px");
   el.style.setProperty("--node-opacity-local",num(cap.opacity,1));
   el.setAttribute("aria-label",safeText(cap.title));
   const icon=document.createElement("span");icon.className="avan-orbit-icon";icon.innerHTML=cap.svg||icons[cap.id]||icons.docs;
   const label=document.createElement("span");label.className="avan-orbit-label";label.textContent=safeText(cap.title);
   const cardBox=document.createElement("span");cardBox.className="avan-cap-card";
   const title=document.createElement("strong");title.textContent=safeText(cap.title);
   const sub=document.createElement("small");sub.textContent=safeText(cap.subtitle);
   const tagBox=document.createElement("span");tagBox.className="avan-cap-card-tags";
   for(const tag of (Array.isArray(cap.tags)?cap.tags:[]).slice(0,8)){const t=document.createElement("em");t.textContent=safeText(tag);tagBox.append(t)}
   const description=document.createElement("span");description.className="avan-cap-description";description.textContent=safeText(cap.description);
   cardBox.append(title,sub,description,tagBox);const surface=document.createElement("span");surface.className="avan-orbit-surface";surface.append(icon);el.append(surface,label,cardBox);
   const mode=cap.label_mode||"inherit";if(mode!=="inherit")el.classList.add("label-"+mode);
   const node={half:(num(cap.size,0)||num(config.node_size,70))/2,side:"",phase:0,cap:{...cap,r:num(cap.radius,1.2),e:num(cap.ellipse,.7),a:num(cap.angle,0),s:num(cap.speed,.00015)},el,pause:false};
   el.addEventListener("mouseenter",()=>{if(config.pause_on_hover)node.pause=true;if(config.hover_mode==="tooltip")showTip(node)});
   el.addEventListener("mouseleave",()=>{node.pause=false;if(selected!==node)hideTip()});
   el.addEventListener("focus",()=>{if(config.pause_on_hover)node.pause=true;if(config.hover_mode==="tooltip")showTip(node)});
   el.addEventListener("blur",()=>{node.pause=false;if(selected!==node)hideTip()});
   el.addEventListener("click",()=>{selected=selected===node?null:node;nodes.forEach(x=>x.el.classList.toggle("is-selected",x===selected));if(selected&&config.hover_mode==="tooltip")showTip(node);else if(!selected)hideTip()});
   layer.append(el);nodes.push(node);
  }
 }

 function globeGeometry(){return geometry}
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
  if(!wrap||!canvas||!ctx)return;const r=wrap.getBoundingClientRect(),dpr=Math.min(devicePixelRatio||1,1.5);
  const cardRect=card?.getBoundingClientRect();
  geometry={cardLeft:cardRect?.left||innerWidth,cx:r.left+r.width/2,cy:r.top+r.height/2,rad:r.width*.40,width:r.width,height:r.height};
  canvas.width=Math.max(1,Math.round(r.width*dpr));canvas.height=Math.max(1,Math.round(r.height*dpr));canvas.style.width=r.width+"px";canvas.style.height=r.height+"px";ctx.setTransform(dpr,0,0,dpr,0,0);
 }
 function drawGlobe(t){
  if(!ctx||!wrap||config.globe_visible===false)return;
  const W=geometry.width,H=geometry.height,cx=W/2,cy=H/2,R=W*.39;ctx.clearRect(0,0,W,H);
  const rot=t*.00022*num(config.globe_rotation_speed,1),density=clamp(num(config.globe_point_density,1),.5,2.5),
        psize=clamp(num(config.globe_point_size,1),.5,2.5),popacity=clamp(num(config.globe_point_opacity,1),.1,1);
  const latStep=Math.max(4,Math.round(10/density)),lonStep=Math.max(5,Math.round(12/density));
  ctx.save();ctx.globalCompositeOperation="screen";
  const ring=ctx.createRadialGradient(cx,cy,R*.55,cx,cy,R*1.02);ring.addColorStop(0,"rgba(20,176,216,.015)");ring.addColorStop(.76,"rgba(37,220,245,.04)");ring.addColorStop(1,rgba(config.orbit_primary,.28*popacity));
  ctx.fillStyle=ring;ctx.beginPath();ctx.arc(cx,cy,R*1.02,0,Math.PI*2);ctx.fill();
  for(let lat=-70;lat<=70;lat+=latStep){
   const la=lat*Math.PI/180,cl=Math.cos(la),sl=Math.sin(la);
   for(let lon=0;lon<360;lon+=lonStep){
    const lo=lon*Math.PI/180+rot,x3=cl*Math.cos(lo),y3=sl,z3=cl*Math.sin(lo);if(z3<-.18)continue;
    const x=cx+x3*R,y=cy-y3*R*.98,alpha=(.12+.48*((z3+1)/2))*popacity;
    ctx.fillStyle=rgba(config.orbit_primary||"#50EAF7",alpha);ctx.beginPath();ctx.arc(x,y,(z3>.45?1.5:.8)*psize,0,Math.PI*2);ctx.fill();
   }
  }
  ctx.lineWidth=num(config.orbit_line_width,1.15);ctx.shadowBlur=15*num(config.orbit_glow,1);ctx.shadowColor=config.orbit_primary||"#50EAF7";
  if(config.show_orbits!==false)for(let i=0;i<3;i++){ctx.strokeStyle=rgba(i===1?config.orbit_secondary:config.orbit_primary,(i===1?.42:.44)*num(config.orbit_opacity,.78));ctx.beginPath();ctx.ellipse(cx,cy,R*(1.05+i*.08),R*(.46+i*.07),rot*(i%2?-.55:.7)+i*.8,0,Math.PI*2);ctx.stroke()}
  for(let i=0;i<24;i++){const a=rot*2.5+i*.57,rr=R*(1.03+(i%5)*.075);ctx.fillStyle=rgba(i%5===0?config.orbit_secondary:config.orbit_primary,(i%5===0?.82:.76)*popacity);ctx.beginPath();ctx.arc(cx+Math.cos(a)*rr,cy+Math.sin(a)*rr*.62,(i%3?1.2:2)*psize,0,Math.PI*2);ctx.fill()}
  ctx.restore();
 }
 function setCardSide(node,x,g){
  const configured=node.cap.card_side||"auto";
  const width=num(config.card_width,176),half=node.half;
  let side=configured;
  if(side==="auto"){
   side=x<g.cx?"left":"right";
   if(side==="left"&&x-half-width-14<12)side="right";
   if(side==="right"&&x+half+width+14>g.cardLeft-18)side="left";
  }
  if(side===node.side)return;
  if(node.side)node.el.classList.remove("card-"+node.side);
  node.el.classList.add("card-"+side);node.side=side;
 }
 function renderFrame(dt){
  const g=globeGeometry();if(!g)return;
  const speed=num(config.orbit_speed,1);
  for(const node of nodes){
   const c=node.cap;
   if(!node.pause&&selected!==node)node.phase+=dt*c.s*speed;
   const angle=config.orbit_mode==="static"?c.a:config.orbit_mode==="orbit"?c.a+node.phase:c.a+Math.sin(node.phase)*.07;
   const rr=g.rad*c.r;
   const x=clamp(g.cx+Math.cos(angle)*rr,node.half+12,innerWidth-node.half-12);
   const y=clamp(g.cy+Math.sin(angle)*rr*c.e,node.half+12,innerHeight-node.half-12);
   node.el.style.transform="translate3d("+(x-node.half)+"px,"+(y-node.half)+"px,0)";
   setCardSide(node,x,g);
   if(selected===node&&config.hover_mode==="tooltip")positionTip(node);
  }
  drawGlobe(sceneTime);
 }
 function animate(now){
  raf=0;if(!animating()){root?.classList.add("scene-paused");return;}
  const elapsed=now-last;
  if(elapsed>=1000/30){const dt=Math.min(80,elapsed);last=now;sceneTime+=dt;renderFrame(dt)}
  raf=requestAnimationFrame(animate);
 }
 function updateMotion(){
  cancelAnimationFrame(raf);raf=0;
  if(!root)return;
  root.classList.toggle("scene-paused",!animating());
  resizeCanvas();renderFrame(0);last=performance.now();
  if(animating())raf=requestAnimationFrame(animate);
 }
 function isInteractive(target){return !!target.closest("input,textarea,select,button,a,label,form,.avan-captcha,.otp-motion")}
 function enableDrag(target){
  if(!target||target.dataset.avanDraggable==="1")return;target.dataset.avanDraggable="1";let active=false,pid=null,sx=0,sy=0,bx=0,by=0;
  const move=e=>{if(!active||e.pointerId!==pid)return;const cx=Number(target.dataset.dragX||0),cy=Number(target.dataset.dragY||0),rect=target.getBoundingClientRect(),baseLeft=rect.left-cx,baseTop=rect.top-cy,margin=12;let nx=bx+(e.clientX-sx),ny=by+(e.clientY-sy);nx=Math.min(innerWidth-margin-baseLeft-rect.width,Math.max(margin-baseLeft,nx));ny=Math.min(innerHeight-margin-baseTop-rect.height,Math.max(margin-baseTop,ny));target.dataset.dragX=String(nx);target.dataset.dragY=String(ny);target.style.translate=nx+"px "+ny+"px"};
  const end=e=>{if(!active||e.pointerId!==pid)return;active=false;target.dataset.dragging="0";target.classList.remove("is-login-dragging");bx=Number(target.dataset.dragX||0);by=Number(target.dataset.dragY||0);try{target.releasePointerCapture(pid)}catch(_){}pid=null};
  target.addEventListener("pointerdown",e=>{if(e.button!==0||innerWidth<820||isInteractive(e.target))return;active=true;pid=e.pointerId;sx=e.clientX;sy=e.clientY;bx=Number(target.dataset.dragX||0);by=Number(target.dataset.dragY||0);target.dataset.dragging="1";target.classList.add("is-login-dragging");target.setPointerCapture(pid);e.preventDefault()});
  target.addEventListener("pointermove",move);target.addEventListener("pointerup",end);target.addEventListener("pointercancel",end);target.addEventListener("dblclick",e=>{if(isInteractive(e.target))return;target.dataset.dragX="0";target.dataset.dragY="0";target.style.translate="0px 0px"});
 }
 function teardown(){cancelAnimationFrame(raf);raf=0;last=0;selected=null;nodes=[];root?.remove();root=wrap=canvas=ctx=layer=tooltip=backdrop=geometry=null;document.body.classList.remove("avan-live-login-enabled")}
 function sync(){
  const next=document.querySelector(loginSelector);
  if(next){card=next;document.body.classList.add("avan-live-login-enabled");if(!root&&!creating)creating=makeScene().catch(()=>{}).finally(()=>{creating=null});enableDrag(card)}
  else if(root){teardown();card=null}
 }
 document.addEventListener("visibilitychange",updateMotion);
 reduced.addEventListener("change",updateMotion);compact.addEventListener("change",updateMotion);
 addEventListener("resize",()=>{updateMotion();if(selected&&config.hover_mode==="tooltip")positionTip(selected)},{passive:true});
 document.addEventListener("pointermove",e=>{
  if(!root||innerWidth<900||reduced.matches||document.hidden)return;
  const px=e.clientX/innerWidth-.5,py=e.clientY/innerHeight-.5,globeShift=8,backShift=num(config.background_parallax,6);

  if(backdrop)backdrop.style.translate=(-px*backShift)+"px "+(-py*backShift*.65)+"px";
 },{passive:true});
 if(document.readyState==="loading")document.addEventListener("DOMContentLoaded",sync,{once:true});else sync();
 observer=new MutationObserver(()=>{if(document.querySelector(loginSelector)!==card)sync()});observer.observe(document.querySelector("#main")||document.body,{subtree:true,childList:true});
})();
