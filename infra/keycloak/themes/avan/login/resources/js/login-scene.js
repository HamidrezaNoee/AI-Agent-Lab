"use strict";
(function(){
 const icons={
  bi:'<svg viewBox="0 0 24 24"><path d="M4 19V10m5 9V5m5 14v-7m5 7V8"/><path d="M3 19h18"/></svg>',
  meetings:'<svg viewBox="0 0 24 24"><rect x="3.5" y="5" width="17" height="15" rx="2"/><path d="M7 3v4m10-4v4M3.5 10h17"/><path d="M8 14h3m2 0h3m-8 3h8"/></svg>',
  bpms:'<svg viewBox="0 0 24 24"><circle cx="6" cy="6" r="2.4"/><circle cx="18" cy="6" r="2.4"/><circle cx="12" cy="18" r="2.4"/><path d="M8.1 7.3 10.7 15m5.2-7.7L13.3 15M8.4 6h7.2"/></svg>',
  agent:'<svg viewBox="0 0 24 24"><path d="m12 2 1.8 5.2L19 9l-5.2 1.8L12 16l-1.8-5.2L5 9l5.2-1.8L12 2Z"/><path d="m19 15 .9 2.6 2.6.9-2.6.9L19 22l-.9-2.6-2.6-.9 2.6-.9L19 15Z"/></svg>',
  voice:'<svg viewBox="0 0 24 24"><rect x="9" y="3" width="6" height="12" rx="3"/><path d="M5.5 11.5A6.5 6.5 0 0 0 18.5 11.5M12 18v3m-4 0h8"/></svg>',
  docs:'<svg viewBox="0 0 24 24"><path d="M6 3h8l4 4v14H6z"/><path d="M14 3v5h5M9 12h6m-6 4h6"/></svg>',
  alert:'<svg viewBox="0 0 24 24"><path d="M12 3 2.8 20h18.4L12 3Z"/><path d="M12 9v5M12 17.5v.5"/></svg>',
  security:'<svg viewBox="0 0 24 24"><path d="M12 3 19 6v5c0 4.5-2.5 7.7-7 10-4.5-2.3-7-5.5-7-10V6z"/><path d="m9.2 12 1.8 1.8 3.8-4"/></svg>'
 };
 const capabilities=[
  {id:"docs",title:"Document Intelligence",desc:"تحلیل قرارداد، صورت‌جلسه، گزارش و فایل؛ استخراج اطلاعات و تبدیل محتوا به Context قابل استفاده برای Agent و جست‌وجوی سازمانی.",tags:["Documents","Extraction","RAG"],r:1.20,e:.72,a:3.50,s:.00018},
  {id:"bi",title:"BI و تحلیل مدیریتی",desc:"اتصال گزارش‌های مدیریتی، KPIها و تحلیل روند به فضای کاری آوان؛ با امکان پرسش‌وپاسخ روی داده و یافتن گلوگاه‌ها.",tags:["Power BI","KPI","Root Cause"],r:1.38,e:.66,a:4.15,s:-.00014},
  {id:"meetings",title:"جلسات و مصوبات",desc:"از برنامه‌ریزی و صورت‌جلسه تا اقدام، مسئول، موعد، درصد پیشرفت، ارزیابی و جلسه بعدی؛ متصل به AI Agent جلسات.",tags:["Minutes","Actions","Follow-up"],r:1.13,e:.78,a:4.95,s:.00020},
  {id:"bpms",title:"اتصالات BPMS",desc:"کاتالوگ یکپارچه اتصال ProcessMaker، Camunda، Appian، UiPath و سایر BPMSها با تست، ویرایش، OAuth و کنترل دسترسی.",tags:["ProcessMaker","BPMS","OAuth"],r:1.46,e:.62,a:5.62,s:-.00013},
  {id:"agent",title:"Agentic Automation",desc:"Agentهای تخصصی برای تحلیل، تصمیم‌یار و اجرای کنترل‌شده کارها؛ هماهنگ با انسان، سیستم و Workflowهای سازمان.",tags:["Agents","Tools","Workflow"],r:1.18,e:.75,a:.10,s:.00018},
  {id:"voice",title:"Voice AI",desc:"ورودی صوتی، تبدیل گفتار به متن، پاسخ صوتی، خلاصه‌سازی جلسه و ثبت سریع داده بدون نیاز به کار با فرم‌های طولانی.",tags:["STT","TTS","Assistant"],r:1.34,e:.69,a:.82,s:-.00016},
  {id:"alert",title:"هشدار و پایش",desc:"پایش تأخیرها، SLA، ریسک و اقدامات باز و ایجاد هشدار برای مدیر، مسئول و دبیر فرایند با قابلیت پیگیری.",tags:["SLA","Risk","Monitoring"],r:1.25,e:.78,a:1.62,s:.00021},
  {id:"security",title:"هویت و امنیت",desc:"ورود سازمانی، MFA، مدیریت Tenant، نقش‌ها، Secret Management و Anti-Bot برای استفاده امن و تجاری آوان.",tags:["Keycloak","MFA","RBAC"],r:1.47,e:.64,a:2.45,s:-.00015}
 ];

 let root=null,wrap=null,canvas=null,ctx=null,layer=null,tooltip=null,nodes=[],selected=null,raf=0,last=0;
 let card=null,observer=null;

 function makeScene(){
  if(root)return;
  root=document.createElement("div");
  root.className="avan-live-scene avan-approved-scene";
  root.setAttribute("data-avan-live-scene","approved-v2");

  const backdrop=document.createElement("div");
  backdrop.className="avan-live-backdrop";

  const stage=document.createElement("div");
  stage.className="avan-live-stage";

  wrap=document.createElement("div");
  wrap.className="avan-globe-wrap";
  wrap.setAttribute("aria-hidden","true");
  wrap.innerHTML='<div class="avan-globe-halo"></div><div class="avan-globe-image"></div><canvas class="avan-globe-canvas"></canvas><svg class="avan-orbit-svg" viewBox="0 0 100 100" preserveAspectRatio="none"><ellipse class="o1" cx="50" cy="50" rx="49" ry="23" transform="rotate(-14 50 50)"/><ellipse class="o2" cx="50" cy="50" rx="45" ry="28" transform="rotate(47 50 50)"/><ellipse class="o3" cx="50" cy="50" rx="43" ry="37" transform="rotate(86 50 50)"/></svg>';
  stage.append(wrap);

  layer=document.createElement("div");
  layer.className="avan-cap-layer";

  tooltip=document.createElement("aside");
  tooltip.className="avan-scene-tooltip";
  tooltip.setAttribute("role","status");
  tooltip.setAttribute("aria-live","polite");

  root.append(backdrop,stage,layer,tooltip);
  document.body.prepend(root);

  canvas=wrap.querySelector(".avan-globe-canvas");
  ctx=canvas.getContext("2d");

  nodes=capabilities.map(cap=>{
   const el=document.createElement("button");
   el.type="button";
   el.className="avan-cap-node"+((cap.id==="meetings"||cap.id==="alert")?" orange":"");
   el.setAttribute("aria-label",cap.title);
   el.innerHTML=icons[cap.id]+'<span class="avan-cap-label">'+cap.title+'</span>';
   const node={cap,el,pause:false};
   el.addEventListener("mouseenter",()=>{node.pause=true;showTip(node)});
   el.addEventListener("mouseleave",()=>{node.pause=false;if(selected!==node)hideTip()});
   el.addEventListener("focus",()=>{node.pause=true;showTip(node)});
   el.addEventListener("blur",()=>{node.pause=false;if(selected!==node)hideTip()});
   el.addEventListener("click",()=>{
    selected=selected===node?null:node;
    nodes.forEach(x=>x.el.classList.toggle("is-selected",x===selected));
    if(selected)showTip(node);else hideTip();
   });
   layer.append(el);
   return node;
  });

  resizeCanvas();
  last=performance.now();
  cancelAnimationFrame(raf);
  raf=requestAnimationFrame(animate);
 }

 function globeGeometry(){
  const r=wrap.getBoundingClientRect();
  return {cx:r.left+r.width/2,cy:r.top+r.height/2,rad:r.width*.40};
 }

 function showTip(node){
  const c=node.cap;
  tooltip.innerHTML='<strong>'+c.title+'</strong><p>'+c.desc+'</p><div class="avan-scene-tags">'+c.tags.map(x=>'<span>'+x+'</span>').join("")+'</div>';
  tooltip.classList.add("is-visible");
  positionTip(node);
 }
 function positionTip(node){
  const rr=node.el.getBoundingClientRect(),tw=Math.min(350,innerWidth-28),th=155;
  let left=rr.right+14,top=rr.top-28;
  if(left+tw>innerWidth-14)left=rr.left-tw-14;
  left=Math.max(14,left);top=Math.max(14,Math.min(innerHeight-th-14,top));
  tooltip.style.left=left+"px";tooltip.style.top=top+"px";
 }
 function hideTip(){if(tooltip)tooltip.classList.remove("is-visible")}

 function resizeCanvas(){
  if(!wrap||!canvas||!ctx)return;
  const r=wrap.getBoundingClientRect(),dpr=Math.min(devicePixelRatio||1,2);
  canvas.width=Math.max(1,Math.round(r.width*dpr));
  canvas.height=Math.max(1,Math.round(r.height*dpr));
  canvas.style.width=r.width+"px";canvas.style.height=r.height+"px";
  ctx.setTransform(dpr,0,0,dpr,0,0);
 }

 function drawGlobe(t){
  if(!ctx||!wrap)return;
  const r=wrap.getBoundingClientRect(),W=r.width,H=r.height,cx=W/2,cy=H/2,R=W*.37;
  ctx.clearRect(0,0,W,H);
  const rot=t*.00020;
  ctx.save();ctx.globalCompositeOperation="screen";
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
   ctx.beginPath();ctx.arc(cx+Math.cos(a)*rr,cy+Math.sin(a)*rr*.62,(i%3?1.15:1.9),0,Math.PI*2);ctx.fill();
  }
  ctx.restore();
 }

 function animate(now){
  if(!root||!wrap)return;
  const dt=Math.min(40,Math.max(0,now-last));last=now;
  const g=globeGeometry();
  nodes.forEach(node=>{
   const c=node.cap;
   if(!node.pause)c.a+=dt*c.s;
   const rr=g.rad*c.r,x=g.cx+Math.cos(c.a)*rr,y=g.cy+Math.sin(c.a)*rr*c.e+Math.sin(now*.0018+c.r*9)*3.5;
   const half=(node.el.offsetWidth||64)/2;
   node.el.style.transform="translate3d("+(x-half)+"px,"+(y-half)+"px,0)";
   if(selected===node)positionTip(node);
  });
  drawGlobe(now);
  raf=requestAnimationFrame(animate);
 }

 function isInteractive(target){
  return !!target.closest("input,textarea,select,button,a,label,form,.avan-captcha,.otp-motion");
 }

 function enableDrag(target){
  if(!target||target.dataset.avanDraggable==="1")return;
  target.dataset.avanDraggable="1";
  let active=false,pid=null,sx=0,sy=0,bx=0,by=0;
  const move=e=>{
   if(!active||e.pointerId!==pid)return;
   const currentX=Number(target.dataset.dragX||0),currentY=Number(target.dataset.dragY||0);
   const rect=target.getBoundingClientRect();
   const baseLeft=rect.left-currentX,baseTop=rect.top-currentY;
   const margin=12;
   let nx=bx+(e.clientX-sx),ny=by+(e.clientY-sy);
   nx=Math.min(innerWidth-margin-baseLeft-rect.width,Math.max(margin-baseLeft,nx));
   ny=Math.min(innerHeight-margin-baseTop-rect.height,Math.max(margin-baseTop,ny));
   target.dataset.dragX=String(nx);target.dataset.dragY=String(ny);
   target.style.translate=nx+"px "+ny+"px";
  };
  const end=e=>{
   if(!active||e.pointerId!==pid)return;
   active=false;target.dataset.dragging="0";target.classList.remove("is-login-dragging");
   bx=Number(target.dataset.dragX||0);by=Number(target.dataset.dragY||0);
   try{target.releasePointerCapture(pid)}catch(_){}
   pid=null;
  };
  target.addEventListener("pointerdown",e=>{
   if(e.button!==0||innerWidth<820||isInteractive(e.target))return;
   active=true;pid=e.pointerId;sx=e.clientX;sy=e.clientY;
   bx=Number(target.dataset.dragX||0);by=Number(target.dataset.dragY||0);
   target.dataset.dragging="1";target.classList.add("is-login-dragging");
   target.setPointerCapture(pid);e.preventDefault();
  });
  target.addEventListener("pointermove",move);
  target.addEventListener("pointerup",end);
  target.addEventListener("pointercancel",end);
  target.addEventListener("dblclick",e=>{
   if(isInteractive(e.target))return;
   target.dataset.dragX="0";target.dataset.dragY="0";target.style.translate="0px 0px";
  });
 }

 function teardown(){
  cancelAnimationFrame(raf);raf=0;last=0;selected=null;nodes=[];
  if(root)root.remove();
  root=wrap=canvas=ctx=layer=tooltip=null;
  document.body.classList.remove("avan-live-login-enabled");
 }

 function sync(){
  const next=document.querySelector(".login-reveal-card,.panel.login,.signin-panel.login-reveal-card");
  if(next){
   card=next;
   document.body.classList.add("avan-live-login-enabled");
   makeScene();enableDrag(card);
  }else if(root){
   teardown();card=null;
  }
 }

 addEventListener("resize",()=>{resizeCanvas();if(selected)positionTip(selected)},{passive:true});
 document.addEventListener("pointermove",e=>{
  if(!wrap||innerWidth<900)return;
  const dx=(e.clientX/innerWidth-.5)*7,dy=(e.clientY/innerHeight-.5)*5;
  wrap.style.translate=dx+"px "+dy+"px";
 },{passive:true});

 if(document.readyState==="loading")document.addEventListener("DOMContentLoaded",sync,{once:true});else sync();
 observer=new MutationObserver(sync);
 observer.observe(document.documentElement,{subtree:true,childList:true});
})();