const {chromium}=require('playwright');
const http=require('node:http'),fs=require('node:fs'),path=require('node:path'),crypto=require('node:crypto');
const web=path.resolve(__dirname,'../web/admin');
const server=http.createServer((req,res)=>{
 const u=new URL(req.url,'http://localhost');
 let name=u.pathname.replace('/admin/','').replace(/^assets\//,'')||'index.html';
 const file=path.resolve(web,name);
 if(!file.startsWith(web+path.sep)){res.writeHead(403);return res.end()}
 fs.readFile(file,(err,data)=>{
  if(err){res.writeHead(404);return res.end()}
  res.setHeader('Content-Type',({'.js':'text/javascript','.css':'text/css','.html':'text/html'})[path.extname(file)]||'application/octet-stream');
  res.end(data);
 });
});
(async()=>{
 await new Promise(r=>server.listen(0,'127.0.0.1',r));
 const origin='http://127.0.0.1:'+server.address().port;
 const browser=await chromium.launch({
  ...(process.env.CHROMIUM_PATH?{executablePath:process.env.CHROMIUM_PATH}:{}),
  headless:true,args:['--no-sandbox','--disable-dev-shm-usage','--disable-gpu']
 });
 const page=await browser.newPage({viewport:{width:1440,height:900}});
 page.setDefaultTimeout(10000);
 const errors=[];page.on('pageerror',e=>errors.push(e.message));
 const challenge=crypto.createHash('sha256').update('salt0').digest('hex');
 await page.route('**/assets/theme.css',r=>r.fulfill({contentType:'text/css',body:''}));
 await page.route('**/assets/theme.js',r=>r.fulfill({contentType:'text/javascript',body:''}));
 await page.route('**/admin/api/**',async route=>{
  const p=new URL(route.request().url()).pathname;
  let data={};
  if(p==='/admin/api/state')data={authenticated:false,password_changed:true,mfa_enrolled:true,mfa_authenticated:false,csrf:null,auth_mode:'bootstrap'};
  else if(p==='/admin/api/captcha/config')data={provider:'hybrid',cloudflare:{enabled:false},local:{provider:'altcha-self-hosted',algorithm:'SHA-256',challenge,maxNumber:1000,salt:'salt',signature:'x',expiresIn:120}};
  else if(p==='/admin/api/appearance/public')data={
    version:4,background_image:'',background_fit:'cover',background_position_x:47,background_position_y:52,
    background_brightness:1.15,background_contrast:1.12,background_saturation:1.1,background_blur:0,background_dim:.02,overlay_color:'#031522',overlay_opacity:.04,background_parallax:7,
    globe_image:'',globe_visible:true,globe_x:28,globe_y:43,globe_scale:1.25,globe_opacity:1,globe_brightness:1.4,globe_contrast:1.1,globe_saturation:1.2,globe_hue:0,globe_glow:1.3,
    globe_wobble:1,globe_rotation_speed:1.2,globe_point_density:1.1,globe_point_size:1.1,globe_point_opacity:.95,
    node_size:72,node_opacity:1,node_border_width:1.2,node_glow:1.1,hover_scale:1.3,hover_duration:220,
    hover_mode:'tooltip',pause_on_hover:true,show_orbits:true,show_idle_cards:false,orbit_speed:1.1,orbit_line_width:1.4,orbit_opacity:.8,orbit_glow:1.2,orbit_primary:'#50EAF7',orbit_secondary:'#FF7053',card_width:185,card_opacity:.94,
    elements:[
      {id:'docs',enabled:true,title:'مدیریت اسناد',subtitle:'جستجوی هوشمند',description:'تحلیل سند',tags:['RAG'],svg:'<svg viewBox="0 0 24 24"><path d="M6 3h8l4 4v14H6z"/></svg>',accent:'#63ECFF',radius:1.2,ellipse:.7,angle:3.5,speed:.00018,size:88,hover_scale:1.5,glow:1.4,opacity:.9,card_side:'top',label_mode:'always'},
      {id:'bi',enabled:true,title:'تحلیل و گزارشات',subtitle:'داشبورد',description:'KPI',tags:['BI'],svg:'<svg viewBox="0 0 24 24"><path d="M4 19V10m5 9V5"/></svg>',accent:'#65EEF2',radius:1.4,ellipse:.64,angle:4.1,speed:-.00014},
      {id:'meetings',enabled:true,title:'جلسات و مصوبات',subtitle:'پیگیری',description:'جلسه',tags:['Actions'],svg:'<svg viewBox="0 0 24 24"><circle cx="8" cy="9" r="3"/></svg>',accent:'#FF7358',radius:1.25,ellipse:.76,angle:4.9,speed:.0002},
      {id:'bpms',enabled:true,title:'اتصالات BPMS',subtitle:'ProcessMaker',description:'BPMS',tags:['OAuth'],svg:'<svg viewBox="0 0 24 24"><circle cx="6" cy="6" r="2"/></svg>',accent:'#61EAF7',radius:1.4,ellipse:.62,angle:5.6,speed:-.00013},
      {id:'agent',enabled:true,title:'Agent هوشمند',subtitle:'AI',description:'Agent',tags:['Agent'],svg:'<svg viewBox="0 0 24 24"><rect x="4" y="7" width="16" height="12"/></svg>',accent:'#FF8064',radius:1.2,ellipse:.74,angle:.1,speed:.00018},
      {id:'voice',enabled:true,title:'دستیار صوتی',subtitle:'Voice',description:'Voice',tags:['TTS'],svg:'<svg viewBox="0 0 24 24"><rect x="9" y="3" width="6" height="12"/></svg>',accent:'#68EEEF',radius:1.34,ellipse:.69,angle:.8,speed:-.00016},
      {id:'alert',enabled:true,title:'هشدار و نظارت',subtitle:'SLA',description:'Alert',tags:['SLA'],svg:'<svg viewBox="0 0 24 24"><path d="M12 3 2 20h20z"/></svg>',accent:'#FF7459',radius:1.25,ellipse:.78,angle:1.6,speed:.00021},
      {id:'security',enabled:true,title:'هویت و امنیت',subtitle:'MFA',description:'Security',tags:['MFA'],svg:'<svg viewBox="0 0 24 24"><path d="M12 3 19 6v5c0 4-3 8-7 10-4-2-7-6-7-10V6z"/></svg>',accent:'#67F1D0',radius:1.47,ellipse:.64,angle:2.4,speed:-.00015}
    ]
  };
  else data={};
  await route.fulfill({json:data});
 });
 if(process.env.AVAN_APPEARANCE_FIXTURE)await page.route('**/admin/api/appearance/public*',r=>r.fulfill({json:JSON.parse(fs.readFileSync(process.env.AVAN_APPEARANCE_FIXTURE,'utf8'))}));
 await page.goto(origin+'/admin/');
 const card=page.locator('.login-reveal-card');
 await card.waitFor();
 await page.locator('.avan-live-scene').waitFor();
 await page.locator('.avan-globe-wrap').waitFor();
 await page.locator('[data-avan-live-scene="configurable-v4"]').waitFor();
 if(await page.locator('.avan-orbit-node').count()!==8)throw Error('Expected 8 live capability nodes');
 await page.waitForFunction(()=>document.querySelector('.avan-live-backdrop')?.style.backgroundImage.includes('boardroom-v5.webp'));
 await page.waitForFunction(()=>document.querySelector('.avan-globe-image')?.src.endsWith('globe-v5.webp'));
 if(process.env.AVAN_SCREENSHOT){
  await page.waitForTimeout(800);
  await page.screenshot({path:process.env.AVAN_SCREENSHOT});
  console.log(await page.locator('.avan-globe-image').evaluate(el=>({width:el.naturalWidth,loaded:el.complete})));
  await browser.close();server.close();return;
 }
 const globeOpacity=await page.locator('.avan-globe-image').evaluate(el=>getComputedStyle(el).opacity);
 if(Number(globeOpacity)<.95)throw Error('Globe regression: live globe is faded or invisible');
 const rootVars=await page.locator('.avan-live-scene').evaluate(el=>({
   node:el.style.getPropertyValue('--node-size'),hover:el.style.getPropertyValue('--hover-scale'),
   bright:el.style.getPropertyValue('--globe-brightness')
 }));
 if(rootVars.node!=='72px'||rootVars.hover!=='1.3'||rootVars.bright!=='1.4')throw Error('Appearance settings did not reach login scene');
 const firstVars=await page.locator('.avan-orbit-node').first().evaluate(el=>({
   size:el.style.getPropertyValue('--node-size-local'),hover:el.style.getPropertyValue('--node-hover-local')
 }));
 if(firstVars.size!=='88px'||firstVars.hover!=='1.5')throw Error('Per-node V4 override did not reach runtime');
 const globeBox=await page.locator('.avan-globe-wrap').boundingBox();
 const cardStart=await card.boundingBox();
 if(!globeBox||!cardStart)throw Error('Live globe or login card has no layout box');
 if(globeBox.x+globeBox.width/2>=cardStart.x+cardStart.width/2)throw Error('Layout regression: globe must stay left of login card');
 const first=page.locator('.avan-orbit-node').first();
 const hit=await first.boundingBox();
 await page.mouse.move(hit.x+hit.width/2,hit.y+hit.height/2);
 await page.locator('.avan-scene-tooltip.is-visible').waitFor();
 // A stationary pointer near the edge must not repeatedly leave/re-enter as the icon scales.
 const bounds=await first.boundingBox();
 await page.mouse.move(bounds.x+bounds.width-3,bounds.y+bounds.height/2);
 const beforeHover=await first.boundingBox();
 await page.waitForTimeout(700);
 const afterHover=await first.boundingBox();
 if(Math.abs(beforeHover.x-afterHover.x)>1||Math.abs(beforeHover.width-afterHover.width)>1)throw Error('Hover moved/scaled the hit target');
 if(!await first.evaluate(el=>el.matches(':hover')))throw Error('Stationary pointer lost hover');
 await first.click();
 if(!await first.evaluate(el=>el.classList.contains('is-selected')))throw Error('Capability node selection failed');
 const before=await card.boundingBox();
 const heading=card.locator('h2');
 const hb=await heading.boundingBox();
 await page.mouse.move(hb.x+hb.width/2,hb.y+hb.height/2);
 await page.mouse.down();
 await page.mouse.move(hb.x+hb.width/2+90,hb.y+hb.height/2+55,{steps:8});
 await page.mouse.up();
 const after=await card.boundingBox();
 if(Math.abs(after.x-before.x)<30&&Math.abs(after.y-before.y)<20)throw Error('Login card drag did not move');
 if(errors.length)throw Error('Browser errors: '+errors.join(' | '));
 // First-step panel reveals on hover and collapses on leave; orbit hit target stays stable.
 await page.mouse.move(0,0);
 await page.waitForFunction(()=>document.querySelector('.login-reveal-card')?.classList.contains('is-collapsed'));
 if(await page.locator('input[name="username"]').isVisible())throw Error('Login form did not collapse');
 const revealBox=await card.boundingBox();
 await page.mouse.move(revealBox.x+revealBox.width/2,revealBox.y+revealBox.height/2);
 await page.waitForFunction(()=>document.querySelector('.login-reveal-card')?.classList.contains('is-expanded'));
 if(!await page.locator('input[name="username"]').isVisible())throw Error('Login form did not reveal');
 if(await page.locator('input[name="username"]').inputValue()!=='')throw Error('Username prefilled');
 await page.emulateMedia({reducedMotion:'reduce'});
 await page.waitForTimeout(100);
 await page.locator('.avan-live-scene.scene-paused').waitFor();
 const position=await first.evaluate(el=>el.style.transform);
 await page.waitForTimeout(100);
 if(position!==await first.evaluate(el=>el.style.transform))throw Error('Reduced motion ignored');
 await page.setViewportSize({width:390,height:844});
 await page.mouse.move(0,0);
 await page.waitForTimeout(250);
 await page.locator('.login-reveal-toggle').click({force:true});
 if(!await page.locator('input[name="username"]').isVisible())throw Error('Mobile form hidden');
 if(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth))throw Error('Mobile horizontal overflow');
 await browser.close();server.close();
 console.log('LOGIN SCENE PASS: configurable V4 background, visible globe, settings-driven nodes, tooltip/select and unchanged draggable login card');
})().catch(e=>{console.error(e);try{server.close()}catch(_){}process.exit(1)});
