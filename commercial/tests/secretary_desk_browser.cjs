// Render the real UI with deterministic API fixtures. No live PM/IdP credentials.
const {chromium}=require('playwright');
const assert=require('node:assert/strict'),http=require('node:http'),fs=require('node:fs'),path=require('node:path');
const web=path.resolve(__dirname,'../web/production');
const source='1'.repeat(24),pack='2'.repeat(24);
let tasks=[{stage:'invitation_approval',stage_label:'تأیید دعوت‌نامه',title:'بررسی برنامه واردات فصل پاییز',number:'۱۴۰۵۰۱۲',case_uid:'a'.repeat(32),index:1,pack_id:pack,available:true},{stage:'action_execution',stage_label:'اجرای اقدام',title:'تکمیل گزارش وضعیت مجوزهای واردات',number:'۱۴۰۵۰۱۳',case_uid:'b'.repeat(32),index:1,pack_id:pack,available:true}];
const stageDefs=[['invitation','دعوت جلسه'],['invitation_approval','تأیید دعوت‌نامه'],['minutes','ثبت صورت‌جلسه'],['minutes_approval','تأیید صورت‌جلسه'],['action_execution','اجرای اقدام'],['action_review','بررسی اقدام'],['monitoring','پایش و اختتام']];
const nodes=stageDefs.map(([key,title],i)=>({key,title,state:i<4?'done':i===4?'current':'future',role:'دبیر'}));
const person={uid:'u'.repeat(32),name:'علی رضایی',username:'administrator'};
const branches=[1,2].map(i=>({action_no:'A-00'+i,title:i===1?'تکمیل مدارک مجوز واردات':'تهیه گزارش مالی',state:'execution',stage:'action_execution',stage_label:'اجرای اقدام',owner:person,current_owner:person,case_number:200+i,nodes:nodes.slice(4,6),history:i===1?[{stage:'action_execution'},{stage:'action_review'},{stage:'action_execution'}]:[]}));
const flowRows=[{case_uid:'a'.repeat(32),case_number:100,meeting_no:'MTG-100',title:'بررسی برنامه واردات فصل پاییز',status:'active',status_label:'فعال',current_stage_title:'اجرای اقدامات',current_owner_label:person.name,current_owners:[person],my_role_label:'دبیر',nodes,action_branches:branches,actions:{planned:2,total:2},progress_percent:60,history:[]},
{case_uid:'b'.repeat(32),case_number:101,meeting_no:'MTG-101',title:'پیش‌نویس جلسه توسعه آوان',status:'active',status_label:'پیش‌نویس',current_stage_title:'ثبت صورت‌جلسه',current_owner_label:person.name,current_owners:[person],my_role_label:'دبیر',nodes,action_branches:[],actions:{planned:5,total:0},progress_percent:30,history:[]}];
const flow={rows:flowRows,summary:{total_cases:2,active_cases:2,completed_cases:0,waiting_my_action:1,average_progress:45},total:2,person,filters:{people:[person],owners:[person],roles:[],statuses:[],stages:[],units:[]}};
let savedPreferences=null,chatRevision=1;
const server=http.createServer((req,res)=>{
 let name=req.url.split('?')[0];name=name==='/'?'index.html':name.replace(/^\/assets\//,'');
 const file=path.resolve(web,name);if(!file.startsWith(web+path.sep)){res.writeHead(403);return res.end()}
 fs.readFile(file,(err,data)=>{if(err){res.writeHead(404);return res.end()}
 const type=path.extname(file);res.setHeader('Content-Type',({'.html':'text/html','.css':'text/css','.js':'text/javascript','.woff2':'font/woff2'})[type]||'application/octet-stream');
 if(name==='app.js')data=data.toString().replace('document.addEventListener("DOMContentLoaded",init);','')+`\ndocument.addEventListener('DOMContentLoaded',()=>{window.avanQA={settings:userSettingsPage,logs:supportLogsPage,toast};app.user={modules:[2],subject:'actor',role:'Expert',name:'علی رضایی',username:'administrator'};app.csrf='fixture';document.body.classList.remove('auth-screen');document.querySelector('#nav').hidden=false;document.querySelector('#person-name').textContent='کارتابل من';secretaryPage('${source}')});`;
 res.end(data);
 });
});
(async()=>{
 await new Promise(r=>server.listen(0,'127.0.0.1',r));let browser;
 try{
  browser=await chromium.launch({headless:true,...(process.env.CHROMIUM_PATH?{executablePath:process.env.CHROMIUM_PATH}:{}),args:['--no-sandbox','--disable-dev-shm-usage']});
  const page=await browser.newPage({viewport:{width:1440,height:1100}});const errors=[];page.on('pageerror',e=>errors.push(e.message));
  await page.route('**/api/**',r=>{
   const url=new URL(r.request().url());
   if(url.pathname.endsWith('/flow-graph'))return r.fulfill({json:flow});
   if(url.pathname==='/api/user/preferences'){
    if(r.request().method()==='POST')savedPreferences=r.request().postDataJSON();
    return r.fulfill({json:savedPreferences||{secretary_auto_play_voice:false,voice_auto_transcribe:true,voice_auto_send:false}});
   }
   if(url.pathname==='/api/support/logs')return r.fulfill({json:{scope:'self',logs:[{id:'1',actor_id:'actor',actor_name:person.name,event_code:'SECRETARY_PROCESSING_FAILED',happened_at:'2026-10-07T12:00:00Z',detail:{case_uid:'case-100',source_id:source,process_uid:'meeting-process',stage:'minutes',error:'نمونه گزارش بررسی اتصال'}}],filters:{actors:[{id:'actor',name:person.name}],sources:[source],processes:['meeting-process'],stages:['minutes']}}});
   if(url.pathname.endsWith('/sessions'))return r.fulfill({json:{id:'new-draft'}});
   if(url.pathname.includes('/sessions/new-draft')){
    const turned=url.pathname.endsWith('/turn'),done=turned&&r.request().postDataJSON().text!=='پاک کن';
    return r.fulfill({json:{session:{id:'new-draft',status:'draft',revision:turned?2:1,values:{MTG_MeetingTitle:done?'جلسه کامل':''},history:[]},task:{stage:'invitation'},form:{MTG_MeetingTitle:{type:'text',label:'عنوان جلسه'}},people:[],assistant:{message:done?'اطلاعات کامل است.':'عنوان جلسه را بگویید.',missing:done?[]:[{field:'MTG_MeetingTitle',question:'عنوان چیست؟'}]}}});
   }
   if(url.pathname.endsWith('/turn')||url.pathname.endsWith('/undo')){
    const undo=url.pathname.endsWith('/undo'),value=undo?'':'بررسی مجوزها در دستور جلسه قرار گیرد';chatRevision++;
    return r.fulfill({json:{task:tasks[0],draft:{values:{MTG_InvitationApproval:'',MTG_InvitationChairComment:value},revision:chatRevision,status:'draft',history:[{role:'assistant',text:undo?'آخرین تغییر بازگردانده شد.':'**نظر رئیس** در پیش‌نویس ثبت شد.\n- هنوز ارسال نشده است.'}],last_change:{count:1,items:[{label:'نظر رئیس',before:undo?value:'خالی',after:value||'خالی'}]},agent_receipt:{label:'اصلاح پیش‌نویس'},can_undo:!undo},assistant:{message:'ثبت شد.',missing:[{field:'MTG_InvitationApproval',question:'رأی شما چیست؟'}]}}});
   }
   if(r.request().url().endsWith('/tasks/open'))return r.fulfill({json:{task:tasks[0],draft:{values:{MTG_InvitationApproval:''},revision:1,status:'draft',history:[]},form:{MTG_InvitationChairComment:{label:'نظر رئیس',type:'textarea'},MTG_InvitationApproval:{label:'رأی رئیس جلسه',type:'dropdown',options:[{value:'Approved',label:'تأیید'},{value:'NeedsRevision',label:'نیاز به اصلاح'}]}},people:[],context:{},assistant:{summary:'جلسه بررسی برنامه واردات فصل پاییز؛ دعوت‌نامه برای تصمیم شما آماده است.',message:'دعوت‌نامه را بررسی کنید و رأی خود را اعلام کنید.',missing:[{field:'MTG_InvitationApproval',question:'رأی شما چیست؟'}]}}});
   return r.fulfill({json:{tasks,notifications:[],packs:[{id:pack,title:'مدیریت جلسات و مصوبات'}],oauth_connected:true,sessions:[]}});
  });
  await page.goto('http://127.0.0.1:'+server.address().port+'/');await page.locator('.secretary-step').first().waitFor();
  assert.equal(await page.locator('.secretary-step').count(),7);
  assert.equal(await page.locator('.secretary-step:not(:disabled)').count(),2);
  assert.equal(await page.locator('.secretary-step:disabled .secretary-step-count').count(),0);
  assert.equal(await page.locator('[data-action="new-invitation"]').count(),1);
  assert.equal(await page.locator('.secretary-task-card').count(),2);
  await page.locator('.secretary-step[data-stage="action_execution"]').click();
  assert.equal(await page.locator('.secretary-task-card').count(),1);
  assert.match(await page.locator('.secretary-task-card').innerText(),/مجوزهای واردات/);
  await page.getByRole('button',{name:'همه وظایف',exact:true}).click();
  await page.locator('.case-flow-connections path').first().waitFor({state:'attached'});
  assert.equal(await page.locator('.case-flow-connections path').count(),6);
  assert.equal(await page.locator('.meeting-flow-case').nth(1).locator('.case-branch-lane').count(),0);
  assert.equal(await page.locator('.case-rework-loop').count(),1);
  if(process.env.AVAN_SCREENSHOT_DIR){fs.mkdirSync(process.env.AVAN_SCREENSHOT_DIR,{recursive:true});await page.screenshot({path:path.join(process.env.AVAN_SCREENSHOT_DIR,'secretary-desktop.png'),fullPage:true});await page.locator('.meeting-flow-list').screenshot({path:path.join(process.env.AVAN_SCREENSHOT_DIR,'case-graph.png')})}
  await page.setViewportSize({width:390,height:844});
  assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1),'Mobile horizontal overflow');
  if(process.env.AVAN_SCREENSHOT_DIR)await page.screenshot({path:path.join(process.env.AVAN_SCREENSHOT_DIR,'secretary-mobile.png'),fullPage:true});
  await page.setViewportSize({width:1440,height:1100});
  await page.locator('[data-case-uid]').first().click();
  await page.locator('.secretary-conversation').waitFor();
  assert.equal(await page.locator('[aria-current="step"]').innerText(),'۲ · تأیید دعوت‌نامه');
  assert.equal(await page.locator('.secretary-hero').isVisible(),false);
  if(process.env.AVAN_SCREENSHOT_DIR)await page.screenshot({path:path.join(process.env.AVAN_SCREENSHOT_DIR,'secretary-editor.png'),fullPage:true});
  await page.locator('.secretary-form-details>summary').click();
  await page.getByRole('textbox',{name:'پیام به دبیر هوشمند',exact:true}).fill('نظر رئیس را اصلاح کن');
  await page.getByRole('button',{name:'↑',exact:true}).click();
  await page.getByText('نظر رئیس',{exact:true}).first().waitFor();
  await page.waitForFunction(()=>document.querySelector('[aria-label="نظر رئیس"]')?.value==='بررسی مجوزها در دستور جلسه قرار گیرد');
  assert.equal(await page.locator('.chat-bubble-text strong').last().innerText(),'نظر رئیس');
  assert.equal(await page.locator('.secretary-change-receipt').isVisible(),true);
  if(process.env.AVAN_SCREENSHOT_DIR)await page.screenshot({path:path.join(process.env.AVAN_SCREENSHOT_DIR,'secretary-chat-receipt.png'),fullPage:true});
  await page.getByRole('button',{name:'بازگردانی آخرین تغییر',exact:true}).click();
  await page.waitForFunction(()=>document.querySelector('[aria-label="نظر رئیس"]')?.value==='');
  assert.equal(await page.getByRole('button',{name:'بازگردانی آخرین تغییر',exact:true}).count(),0);
  await page.getByRole('button',{name:'← بازگشت به میز کار',exact:true}).click();
  await page.locator('.secretary-hero').waitFor();
  tasks=[];await page.getByRole('button',{name:'↻ تازه‌سازی',exact:true}).click();
  await page.waitForFunction(()=>document.querySelectorAll('.secretary-task-card').length===0);
  assert.equal(await page.locator('.secretary-step:not(:disabled)').count(),0);
  assert.equal(await page.locator('.secretary-step-count').count(),0);
  assert.equal(await page.locator('[data-action="new-invitation"]').isEnabled(),true);
  await page.locator('[data-action="new-invitation"]').click();
  const start=page.getByRole('button',{name:'ایجاد گام اول و ارسال به رئیس',exact:true});
  assert.equal(await start.count(),0);
  await page.getByRole('textbox',{name:'پیام به دبیر هوشمند',exact:true}).fill('جلسه کامل');
  await page.getByRole('button',{name:'↑',exact:true}).click();
  await start.waitFor({state:'visible'});assert(await start.isEnabled());
  if(process.env.AVAN_SCREENSHOT_DIR)await page.screenshot({path:path.join(process.env.AVAN_SCREENSHOT_DIR,'invitation-ready.png'),fullPage:true});
  await page.getByRole('textbox',{name:'پیام به دبیر هوشمند',exact:true}).fill('پاک کن');
  await page.getByRole('button',{name:'↑',exact:true}).click();
  await start.waitFor({state:'hidden'});
  await page.clock.install();
  await page.clock.pauseAt(new Date(Date.now()+1000));
  await page.evaluate(()=>window.avanQA.toast('این وظیفه جاری به حساب متصل شما تعلق ندارد.',{error:true}));
  assert(await page.getByRole('button',{name:'بستن پیام',exact:true}).isVisible());
  await page.clock.fastForward(9999);assert(await page.locator('#toast').isVisible());
  await page.clock.fastForward(1);assert.equal(await page.locator('#toast').isVisible(),false);
  await page.evaluate(()=>window.avanQA.toast('پیام دوم'));
  await page.getByRole('button',{name:'بستن پیام',exact:true}).click();
  assert.equal(await page.locator('#toast').isVisible(),false);
  await page.evaluate(()=>window.avanQA.settings());
  await page.locator('.settings-layout').waitFor();
  await page.locator('[data-preference="secretary_auto_play_voice"]').check();
  await page.getByRole('button',{name:'ذخیره تنظیمات گفتگو',exact:true}).click();
  await page.getByText('تنظیمات شخصی ذخیره شد.',{exact:true}).waitFor();
  assert.equal(savedPreferences.secretary_auto_play_voice,true);
  assert.equal(await page.getByText('رمز فعلی GodAdmin',{exact:true}).count(),0);
  if(process.env.AVAN_SCREENSHOT_DIR)await page.screenshot({path:path.join(process.env.AVAN_SCREENSHOT_DIR,'settings-desktop.png'),fullPage:true});
  await page.evaluate(()=>window.avanQA.logs());
  await page.locator('.support-log-row').waitFor();
  await page.getByLabel('فرایند',{exact:true}).selectOption('meeting-process');
  await page.locator('.support-log-row').waitFor();
  assert.match(await page.locator('.support-log-row').innerText(),/case-100/);
  if(process.env.AVAN_SCREENSHOT_DIR)await page.screenshot({path:path.join(process.env.AVAN_SCREENSHOT_DIR,'logs-desktop.png'),fullPage:true});
  assert.deepEqual(errors,[]);console.log('Secretary desk browser passed: stage order, case gates, counts, filtering, responsive layout.');
 }finally{if(browser)await browser.close();server.close()}
})().catch(e=>{console.error(e);process.exitCode=1;server.close()});


