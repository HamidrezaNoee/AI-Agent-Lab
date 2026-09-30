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
  else data={};
  await route.fulfill({json:data});
 });
 await page.goto(origin+'/admin/');
 const card=page.locator('.login-reveal-card');
 await card.waitFor();
 await page.locator('.avan-live-scene').waitFor();
 await page.locator('.avan-globe-wrap').waitFor();
 if(await page.locator('.avan-cap-node').count()!==8)throw Error('Expected 8 live capability nodes');
 await page.waitForFunction(()=>getComputedStyle(document.documentElement).getPropertyValue('--avan-approved-login-bg').includes('data:image/webp;base64,'));
 await page.waitForFunction(()=>getComputedStyle(document.documentElement).getPropertyValue('--avan-approved-globe').includes('data:image/png;base64,'));
 const bg=await page.evaluate(()=>getComputedStyle(document.documentElement).getPropertyValue('--avan-approved-login-bg'));
 const globe=await page.evaluate(()=>getComputedStyle(document.documentElement).getPropertyValue('--avan-approved-globe'));
 if(bg.length<10000)throw Error('Approved cleaned boardroom background did not load completely');
 if(globe.length<100000)throw Error('Approved independent globe sprite did not load completely');
 if(await page.locator('[data-avan-live-scene="approved-v2"]').count()!==1)throw Error('Approved V2 scene marker missing');
 if(await page.locator('.avan-live-scene .login-card').count())throw Error('Prototype login-card image must never replace the real AVAN login card');
 const globeBox=await page.locator('.avan-globe-wrap').boundingBox();
 const cardStart=await card.boundingBox();
 if(!globeBox||!cardStart)throw Error('Live globe or login card has no layout box');
 if(globeBox.x+globeBox.width/2>=cardStart.x+cardStart.width/2)throw Error('Approved layout regression: globe must stay left of login card');
 const first=page.locator('.avan-cap-node').first();
 await first.hover();
 await page.locator('.avan-scene-tooltip.is-visible').waitFor();
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
 await browser.close();server.close();
 console.log('LOGIN SCENE PASS: approved V2 background, animated independent globe, 8 interactive nodes, tooltip/select and real unchanged draggable login card');
})().catch(e=>{console.error(e);try{server.close()}catch(_){}process.exit(1)});