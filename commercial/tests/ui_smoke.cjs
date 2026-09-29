// UI smoke tests use synthetic API fixtures; they do not claim live integration.
const {chromium}=require('playwright');
const http=require('node:http'),fs=require('node:fs'),path=require('node:path');
const web=path.resolve(__dirname,'../web');
const server=http.createServer((req,res)=>{
 const url=new URL(req.url,'http://localhost');const admin=url.pathname.startsWith('/admin/');
 const name=url.pathname.replace(admin?'/admin/':'/','').replace(/^assets\//,'')||'index.html';
 const root=path.join(web,admin?'admin':'production'),file=path.resolve(root,name);
 if(!file.startsWith(root+path.sep)){res.writeHead(403);return res.end()}
 fs.readFile(file,(err,data)=>{if(err){res.writeHead(404);return res.end()}
 res.setHeader('Content-Type',({'.js':'text/javascript','.css':'text/css','.html':'text/html','.svg':'image/svg+xml','.woff2':'font/woff2'})[path.extname(file)]||'application/octet-stream');res.end(data)})
});
(async()=>{
 await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
 const origin='http://127.0.0.1:'+server.address().port;
 const browser=await chromium.launch({...(process.env.CHROMIUM_PATH?{executablePath:process.env.CHROMIUM_PATH}:{}),headless:true,args:['--no-sandbox','--disable-dev-shm-usage','--disable-gpu']});
 const page=await browser.newPage({viewport:{width:1400,height:1000}});page.setDefaultTimeout(10000);
 const errors=[];page.on('pageerror',e=>errors.push(e.message));let ack=false,sub=false;
 let draft={id:'draft1',revision:1,status:'draft',meeting_id:1,meeting_no:'1001',payload:{summary:'پیگیری مجوز ترخیص',actions:[{description:'تکمیل مجوز ترخیص',source_quote:'مجوز تکمیل شود',owner_uid:'u1',suggested_role:'لجستیک',owner_reason:'مسئول مرتبط',priority:'high',proposed_due_date:'2026-09-25',due_reason:'پیگیری',needs_clarification:false}],candidate_owners:[{uid:'u1',name:'مسئول لجستیک'}],questions:[]}};
 const answer={conversation_id:'conversation1',turn_id:'turn1',model:'test',meetings_considered:12,actions_considered:40,claims:[{text:'واحد لجستیک پنج اقدام باز دارد.',kind:'fact',sources:['T:1']},{text:'تمرکز تأخیر در ترخیص نیازمند بررسی است.',kind:'analysis',sources:['T:1']},{text:'در جلسه آینده رفع مانع مجوز بررسی شود.',kind:'recommendation',sources:['T:1']}],evidence:[{id:'T:1',title:'گزارش اقدامات',result:{metrics:{total:8,open:5,closed:3,overdue:2}}}],notes:[],coverage_complete:true,as_of_utc:'2026-09-22'};
 await page.route('**/api/**',async route=>{
  const path=new URL(route.request().url()).pathname,method=route.request().method();let data={};
  if(path==='/api/me')data={name:'کاربر کنترل کیفیت',company:'سازمان',role:'SysAdmin',department:'مدیریت',csrf:'test',modules:[1,2,3,4],workspace_access:true,is_godadmin:true};
  else if(path==='/api/meetings')data={meetings:[{meeting_id:1,meeting_no:'1001',title:'پیگیری ترخیص خودرو',meeting_status:'Open',meeting_date_utc:'2026-09-20'}],has_more:false};
  else if(path==='/api/meetings/1')data={meeting_id:1,meeting_no:'1001',title:'پیگیری ترخیص خودرو',meeting_date_utc:'2026-09-20',actions:[]};
  else if(path==='/api/questions')data={questions:['عملکرد واحدها در اجرای مصوبات چگونه بوده است؟']};
  else if(path==='/api/agent/status')data={enabled:true,voice_enabled:true,model:'test',modules:[1,2,3,4]};
  else if(path==='/api/conversations')data={conversations:[{id:'conversation1',title:'گفتگوی ذخیره‌شده',updated_at:'2026-09-22'}]};
  else if(path==='/api/conversations/conversation1')data={turns:[{id:'turn1',question:'گفتگوی ذخیره‌شده',created_at:'2026-09-22',answer}]};
  else if(path==='/api/ask')data=answer;
  else if(path==='/api/voice/transcribe')data={text:'کدام اقدامات تأخیر دارند؟'};
  else if(path==='/api/secretary/drafts')data=method==='GET'?{drafts:[]}:draft;
  else if(path.endsWith('/edit')){draft={...draft,revision:2,payload:{...draft.payload,...route.request().postDataJSON().payload}};data=draft}
  else if(path.endsWith('/approve')){draft={...draft,revision:3,status:'approved'};data=draft}
  else if(path.endsWith('/reopen')){draft={...draft,revision:4,status:'draft'};data=draft}
  else if(path.endsWith('/processmaker'))data={processmaker_written:false,rows:[{MTG_ActionDescription:'تکمیل مجوز'}]};
  else if(path==='/api/monitor')data={subscription:{enabled:sub},total:1,coverage_complete:true,as_of_utc:'2026-09-22',alerts:[{id:'alert1',acknowledged:ack,first_seen:'2026-09-22',kind:'overdue',severity:'high',reason:'موعد گذشته است',description:'تکمیل مجوز',source:{meeting_id:1,meeting_no:'1001',action_no:'A-1'},owner_name:'مسئول',progress_percent:50}],notes:[]};
  else if(path==='/api/monitor/subscribe'){sub=route.request().postDataJSON().enabled;data={enabled:sub}}
  else if(path.endsWith('/acknowledge')){ack=true;data={acknowledged:true}}
  else if(path==='/api/bi/processes')data={metrics:{cases:2,open_cases:1,completed_cases:1,open_tasks:2,overdue_tasks:1,median_cycle_hours:48},processes:[{process_uid:'p',title:'خرید قطعات',total:2,open:1,completed:1,overdue_tasks:1,average_cycle_hours:48}],statuses:{TO_DO:1,COMPLETED:1},monthly:[{month:'1405/06',count:2}],tasks:[{title:'تأیید خرید',open:2,overdue:1,average_wait_hours:3,average_work_hours:4}],owners:[{name:'مسئول خرید',unit:'خرید',open:2,overdue:1}],rows:[{case_number:9,process_title:'خرید قطعات',status:'TO_DO',created_at:'2026-09-21'}],has_more:false,coverage_complete:true,notes:[]};
  else if(path==='/api/bi/ask')data={...answer,report_type:'process_bi'};
  else if(path.endsWith('/export'))return route.fulfill({contentType:'text/csv',body:'process,count\nخرید,2'});
  else if(path==='/admin/api/state')data={authenticated:true,password_changed:true,mfa_enrolled:true,mfa_authenticated:true,csrf:'test'};
  else if(path==='/admin/api/settings')data={ai:{enabled:true,model:'gpt-4.1-mini',voice_enabled:true,api_key:'********'},mysql:{},processmaker:{},sql:{},password_state:{changed:true,totp:true}};
  else if(path==='/admin/api/ai/save')data={saved:true};
  else if(path==='/admin/api/license/status')data={valid:true,max_users:10,active_users:3,remaining_days:30,modules:[1,2,3,4]};
  await route.fulfill({json:data});
 });
 await page.goto(origin+'/');
 await page.locator('[data-page=assistant]').click();
 await page.getByRole('button',{name:'گفتگوی ذخیره‌شده',exact:true}).click();
 await page.locator('.claim').first().waitFor();
 await page.getByRole('button',{name:'گفت‌وگوی تازه',exact:true}).click();
 await page.getByLabel('انتخاب فایل صوت برای تبدیل به متن').setInputFiles({name:'voice.webm',mimeType:'audio/webm',buffer:Buffer.from([0x1a,0x45,0xdf,0xa3])});
 await page.waitForFunction(()=>document.querySelector('#management-question').value.includes('تأخیر'));
 await page.getByRole('button',{name:'دریافت پاسخ',exact:true}).click();await page.locator('.claim').first().waitFor();
 if(await page.locator('.claim').count()!==3)throw Error('Missing claims');
 await page.locator('[data-page=secretary]').click();
 await page.getByLabel('شماره جلسه',{exact:true}).fill('1001');await page.getByLabel('متن جلسه',{exact:true}).fill('مصوب شد مجوز تکمیل شود');
 await page.getByRole('button',{name:'استخراج مصوبات',exact:true}).click();
 await page.getByLabel('شرح اقدام',{exact:true}).fill('تکمیل مجوز ترخیص اصلاح‌شده');
 if(!await page.getByRole('button',{name:'تأیید نسخه ذخیره‌شده'}).isDisabled())throw Error('Dirty draft can approve');
 await page.getByRole('button',{name:'ذخیره اصلاحات'}).click();await page.getByText('بازبینی پیش‌نویس · نسخه ۲').waitFor();
 await page.getByLabel('این نسخه را بازبینی کرده‌ام.').check();await page.getByRole('button',{name:'تأیید نسخه ذخیره‌شده'}).click();
 const dl=page.waitForEvent('download');await page.getByRole('button',{name:'دریافت ردیف‌های فرم ProcessMaker'}).click();await dl;
 await page.getByRole('button',{name:'بازگشایی برای اصلاح'}).click();await page.getByText('بازبینی پیش‌نویس · نسخه ۴').waitFor();
 await page.locator('[data-page=monitor]').click();await page.getByRole('button',{name:'دیده شد',exact:true}).click();await page.getByText('دیده‌شده',{exact:true}).waitFor();
 await page.getByRole('button',{name:'فعال‌سازی پایش'}).click();await page.getByText('پایش پس‌زمینه فعال شد.',{exact:true}).waitFor();
 await page.getByRole('button',{name:'متن یادآوری'}).click();if(!(await page.locator('textarea').inputValue()).includes('یادآوری'))throw Error('Reminder missing');
 await page.locator('[data-page=bi]').click();await page.getByText('تأیید خرید',{exact:true}).waitFor();if(await page.locator('meter').count()!==3)throw Error('Missing BI charts');
 await page.getByRole('button',{name:'تحلیل فرایندها',exact:true}).click();await page.locator('.claim').first().waitFor();
 const csv=page.waitForEvent('download');await page.getByRole('button',{name:'دریافت CSV فرایندها'}).click();await csv;
 await page.setViewportSize({width:390,height:844});
 if(await page.evaluate(()=>document.documentElement.scrollWidth>window.innerWidth+2))throw Error('Mobile horizontal overflow');
 await page.setViewportSize({width:1400,height:1000});
 await page.locator('[data-page=system-management]').click();
 const adminFrame=page.frameLocator('.system-admin-frame');
 const processMakerTop=adminFrame.getByRole('button',{name:'ProcessMaker',exact:true});
 if(await processMakerTop.count()!==1)throw Error('ProcessMaker must have exactly one top-level settings owner');
 if(await adminFrame.getByRole('button',{name:'داده‌های ProcessMaker',exact:true}).count())throw Error('Legacy duplicate ProcessMaker settings tab still exists');
 await processMakerTop.click();
 await adminFrame.getByRole('button',{name:'داده‌ها و MySQL',exact:true}).waitFor();
 await adminFrame.getByRole('button',{name:'OAuth و API',exact:true}).click();
 await adminFrame.getByText('اتصال ProcessMaker',{exact:true}).waitFor();
 await adminFrame.getByRole('button',{name:'هوش مصنوعی',exact:true}).click();
 await adminFrame.locator('input[name=api_key]').fill('private-test-value');
 await adminFrame.getByRole('button',{name:'ذخیره تنظیمات',exact:true}).click();
 await adminFrame.getByText('تنظیمات ذخیره شد.',{exact:true}).waitFor();
 if(await adminFrame.locator('input[name=api_key]').inputValue())throw Error('Key not cleared');
 await browser.close();server.close();if(errors.length)throw Error(errors.join('\n'));console.log('UI PASS: organization workspace, clean single-owner management IA, ProcessMaker subtabs, AI settings, mobile layout and core workflows');
})().catch(e=>{console.error(e);server.close();process.exit(1)});
