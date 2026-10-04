// Render the real UI with deterministic API fixtures. No live PM/IdP credentials.
const {chromium}=require('playwright');
const assert=require('node:assert/strict'),http=require('node:http'),fs=require('node:fs'),path=require('node:path');
const web=path.resolve(__dirname,'../web/production');
const source='1'.repeat(24),pack='2'.repeat(24);
let tasks=[{stage:'invitation_approval',stage_label:'تأیید دعوت‌نامه',title:'بررسی برنامه واردات فصل پاییز',number:'۱۴۰۵۰۱۲',case_uid:'a'.repeat(32),index:1,pack_id:pack,available:true},{stage:'action_execution',stage_label:'اجرای اقدام',title:'تکمیل گزارش وضعیت مجوزهای واردات',number:'۱۴۰۵۰۱۳',case_uid:'b'.repeat(32),index:1,pack_id:pack,available:true}];
const server=http.createServer((req,res)=>{
 let name=req.url.split('?')[0];name=name==='/'?'index.html':name.replace(/^\/assets\//,'');
 const file=path.resolve(web,name);if(!file.startsWith(web+path.sep)){res.writeHead(403);return res.end()}
 fs.readFile(file,(err,data)=>{if(err){res.writeHead(404);return res.end()}
 const type=path.extname(file);res.setHeader('Content-Type',({'.html':'text/html','.css':'text/css','.js':'text/javascript','.woff2':'font/woff2'})[type]||'application/octet-stream');
 if(name==='app.js')data=data.toString().replace('document.addEventListener("DOMContentLoaded",init);','')+`\ndocument.addEventListener('DOMContentLoaded',()=>{app.user={modules:[2]};app.csrf='fixture';document.body.classList.remove('auth-screen');document.querySelector('#nav').hidden=false;document.querySelector('#person-name').textContent='کارتابل من';secretaryPage('${source}')});`;
 res.end(data);
 });
});
(async()=>{
 await new Promise(r=>server.listen(0,'127.0.0.1',r));let browser;
 try{
  browser=await chromium.launch({headless:true,...(process.env.CHROMIUM_PATH?{executablePath:process.env.CHROMIUM_PATH}:{}),args:['--no-sandbox','--disable-dev-shm-usage']});
  const page=await browser.newPage({viewport:{width:1440,height:1100}});const errors=[];page.on('pageerror',e=>errors.push(e.message));
  await page.route('**/api/**',r=>{
   if(r.request().url().endsWith('/tasks/open'))return r.fulfill({json:{task:tasks[0],draft:{values:{MTG_InvitationApproval:''},revision:1,status:'draft',history:[]},form:{MTG_InvitationApproval:{label:'رأی رئیس جلسه',type:'dropdown',options:[{value:'Approved',label:'تأیید'},{value:'NeedsRevision',label:'نیاز به اصلاح'}]}},people:[],context:{},assistant:{summary:'جلسه بررسی برنامه واردات فصل پاییز؛ دعوت‌نامه برای تصمیم شما آماده است.',message:'دعوت‌نامه را بررسی کنید و رأی خود را اعلام کنید.',missing:[{field:'MTG_InvitationApproval',question:'رأی شما چیست؟'}]}}});
   return r.fulfill({json:{tasks,notifications:[],packs:[{id:pack,title:'مدیریت جلسات و مصوبات'}],oauth_connected:true,sessions:[]}});
  });
  await page.goto('http://127.0.0.1:'+server.address().port+'/');await page.locator('.secretary-step').first().waitFor();
  assert.equal(await page.locator('.secretary-step').count(),7);
  assert.equal(await page.locator('.secretary-step:not(:disabled)').count(),2);
  assert.equal(await page.locator('.secretary-step:disabled .secretary-step-count').count(),0);
  assert.equal(await page.locator('[data-action="new-invitation"]').count(),1);
  assert.equal(await page.locator('.secretary-task-card').count(),2);
  await page.locator('[data-stage="action_execution"]').click();
  assert.equal(await page.locator('.secretary-task-card').count(),1);
  assert.match(await page.locator('.secretary-task-card').innerText(),/مجوزهای واردات/);
  await page.getByRole('button',{name:'همه وظایف',exact:true}).click();
  if(process.env.AVAN_SCREENSHOT_DIR){fs.mkdirSync(process.env.AVAN_SCREENSHOT_DIR,{recursive:true});await page.screenshot({path:path.join(process.env.AVAN_SCREENSHOT_DIR,'secretary-desktop.png'),fullPage:true})}
  await page.setViewportSize({width:390,height:844});
  assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1),'Mobile horizontal overflow');
  if(process.env.AVAN_SCREENSHOT_DIR)await page.screenshot({path:path.join(process.env.AVAN_SCREENSHOT_DIR,'secretary-mobile.png'),fullPage:true});
  await page.setViewportSize({width:1440,height:1100});
  await page.locator('[data-case-uid]').first().click();
  await page.locator('.secretary-conversation').waitFor();
  assert.equal(await page.locator('[aria-current="step"]').innerText(),'۲ · تأیید دعوت‌نامه');
  assert.equal(await page.locator('.secretary-hero').isVisible(),false);
  if(process.env.AVAN_SCREENSHOT_DIR)await page.screenshot({path:path.join(process.env.AVAN_SCREENSHOT_DIR,'secretary-editor.png'),fullPage:true});
  await page.getByRole('button',{name:'← بازگشت به میز کار',exact:true}).click();
  await page.locator('.secretary-hero').waitFor();
  tasks=[];await page.getByRole('button',{name:'↻ تازه‌سازی',exact:true}).click();
  await page.waitForFunction(()=>document.querySelectorAll('.secretary-task-card').length===0);
  assert.equal(await page.locator('.secretary-step:not(:disabled)').count(),0);
  assert.equal(await page.locator('.secretary-step-count').count(),0);
  assert.equal(await page.locator('[data-action="new-invitation"]').isEnabled(),true);
  assert.deepEqual(errors,[]);console.log('Secretary desk browser passed: stage order, case gates, counts, filtering, responsive layout.');
 }finally{if(browser)await browser.close();server.close()}
})().catch(e=>{console.error(e);process.exitCode=1;server.close()});
