// Browser smoke uses isolated API fixtures and validates the CURRENT user-scoped UI.
// It intentionally does not claim live Keycloak/ProcessMaker integration.
const {chromium}=require('playwright');
const http=require('node:http'),fs=require('node:fs'),path=require('node:path');
const web=path.resolve(__dirname,'../web');
const sourceId='aaaaaaaaaaaaaaaaaaaaaaaa';

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
 const browser=await chromium.launch({
  ...(process.env.CHROMIUM_PATH?{executablePath:process.env.CHROMIUM_PATH}:{}),
  headless:true,args:['--no-sandbox','--disable-dev-shm-usage','--disable-gpu']
 });
 const page=await browser.newPage({viewport:{width:1400,height:1000}});
 page.setDefaultTimeout(10000);
 const errors=[];page.on('pageerror',e=>errors.push(e.message));

 const answer={
  conversation_id:'conversation1',turn_id:'turn1',model:'test',
  meetings_considered:12,actions_considered:40,
  claims:[
   {text:'واحد لجستیک پنج اقدام باز دارد.',kind:'fact',sources:['T:1']},
   {text:'تمرکز تأخیر در ترخیص نیازمند بررسی است.',kind:'analysis',sources:['T:1']},
   {text:'در جلسه آینده رفع مانع مجوز بررسی شود.',kind:'recommendation',sources:['T:1']}
  ],
  evidence:[{id:'T:1',title:'گزارش اقدامات',result:{metrics:{total:8,open:5,closed:3,overdue:2}}}],
  notes:[],coverage_complete:true,as_of_utc:'2026-10-03'
 };
 const bi={
  metrics:{cases:2,open_cases:1,completed_cases:1,open_tasks:2,overdue_tasks:1,median_cycle_hours:48},
  processes:[{process_uid:'p',title:'خرید قطعات',total:2,open:1,completed:1,overdue_tasks:1,average_cycle_hours:48}],
  statuses:{TO_DO:1,COMPLETED:1},
  monthly:[{month:'1405/07',count:2}],
  tasks:[{title:'تأیید خرید',open:2,overdue:1,average_wait_hours:3,average_work_hours:4}],
  owners:[{name:'مسئول خرید',unit:'خرید',open:2,overdue:1}],
  rows:[{case_number:9,process_title:'خرید قطعات',status:'TO_DO',created_at:'2026-10-02'}],
  has_more:false,coverage_complete:true,notes:[]
 };

 await page.route('**/api/**',async route=>{
  const rawPath=new URL(route.request().url()).pathname;
  const apiPath=rawPath.replace('/api/sources/'+sourceId,'/api');
  let data={};

  if(apiPath==='/api/me')data={
   name:'کاربر کنترل کیفیت',company:'سازمان',role:'SysAdmin',department:'مدیریت',
   csrf:'test',subject:'bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb',
   modules:[1,2,3,4],workspace_access:true,workspace_navigation:true,
   is_godadmin:true,platform_access:true,
   bpms_sources:[{
    source_id:sourceId,source_name:'ProcessMaker اصلی',engine:'processmaker',
    external_user_id:'0123456789abcdef0123456789abcdef',
    external_username:'person',external_display_name:'کاربر ProcessMaker',
    capabilities:['overview','meetings','assistant','bi']
   }]
  };
  else if(apiPath==='/api/meetings')data={meetings:[],has_more:false};
  else if(apiPath==='/api/questions')data={questions:['عملکرد واحدها در اجرای مصوبات چگونه بوده است؟']};
  else if(apiPath==='/api/agent/status')data={enabled:true,voice_enabled:true,model:'test',modules:[1,2,3,4]};
  else if(rawPath==='/api/platform/status')data={enabled:true,voice_enabled:true,sources:[],processmaker_access:false};
  else if(apiPath==='/api/conversations')data={conversations:[{id:'conversation1',title:'گفتگوی ذخیره‌شده',updated_at:'2026-10-03'}]};
  else if(apiPath==='/api/conversations/conversation1')data={turns:[{id:'turn1',question:'گفتگوی ذخیره‌شده',created_at:'2026-10-03',answer}]};
  else if(apiPath==='/api/ask')data=answer;
  else if(apiPath==='/api/voice/transcribe')data={text:'کدام اقدامات تأخیر دارند؟'};
  else if(apiPath==='/api/process-workspace')data={processes:[]};
  else if(apiPath==='/api/bi/processes')data=bi;
  else if(apiPath.endsWith('/bi/processes/export'))return route.fulfill({contentType:'text/csv',body:'process,count\nخرید,2'});
  else if(rawPath==='/admin/api/state')data={authenticated:true,password_changed:true,mfa_enrolled:true,mfa_authenticated:true,csrf:'test'};
  else if(rawPath==='/admin/api/settings')data={ai:{enabled:true,model:'gpt-4.1-mini',voice_enabled:true,api_key:'********'},mysql:{},processmaker:{},sql:{},password_state:{changed:true,totp:true}};
  else if(rawPath==='/admin/api/agent-db/connections')data={active_id:null,connections:[]};
  else if(rawPath==='/admin/api/bpms/catalog')data={
   connections:[{
    id:sourceId,name:'ProcessMaker اصلی',connection_type:'processmaker',engine:'processmaker',active:true,
    mysql:{host:'host.docker.internal',port:3306,database:'bitnami_pm',username:'avan_reader',tls:false,timezone:'Asia/Tehran'},
    oauth:{base_url:'http://host.docker.internal:84',workspace:'workflow',client_id:'client',token_managed:true}
   }],
   types:[{id:'processmaker',label:'ProcessMaker',native:true},{id:'camunda',label:'Camunda',native:false},{id:'other',label:'سایر / AVAN REST v1',native:false}]
  };
  else if(rawPath==='/admin/api/identity/status')data={connected:true,realm:'avan'};
  else if(rawPath==='/admin/api/ai/save')data={saved:true};
  else if(rawPath==='/admin/api/license/status')data={valid:true,max_users:10,active_users:3,remaining_days:30,modules:[1,2,3,4]};

  await route.fulfill({json:data});
 });

 await page.goto(origin+'/');

 await page.getByText('ProcessMaker اصلی',{exact:true}).first().waitFor();
 await page.getByRole('button',{name:'دستیار همین ProcessMaker',exact:true}).click();
 await page.getByRole('button',{name:'گفتگوی ذخیره‌شده',exact:true}).click();
 await page.locator('.claim').first().waitFor();

 await page.getByRole('button',{name:'گفت‌وگوی تازه',exact:true}).click();
 await page.getByLabel('انتخاب فایل صوت برای تبدیل به متن').setInputFiles({
  name:'voice.webm',mimeType:'audio/webm',buffer:Buffer.from([0x1a,0x45,0xdf,0xa3])
 });
 await page.waitForFunction(()=>document.querySelector('#management-question').value.includes('تأخیر'));
 await page.getByRole('button',{name:'دریافت پاسخ',exact:true}).click();
 await page.locator('.claim').first().waitFor();
 if(await page.locator('.claim').count()!==3)throw Error('Missing assistant claims');

 await page.locator('[data-page=source-bi][data-source-id="'+sourceId+'"]').click();
 await page.getByText('تأیید خرید',{exact:true}).waitFor();
 if(await page.locator('meter').count()!==3)throw Error('Missing scoped BI charts');
 const csv=page.waitForEvent('download');
 await page.getByRole('button',{name:'دریافت CSV فرایندها'}).click();
 await csv;

 // Connected BPMS report must include native ProcessMaker even with zero AVAN REST v1 adapters.
 await page.locator('[data-page=platform-bi]').click();
 await page.getByRole('heading',{name:'گزارش BPMSهای متصل',exact:true}).waitFor();
 await page.getByText('ProcessMaker اصلی',{exact:true}).last().waitFor();
 if(await page.getByText('هنوز هیچ مبدل خواندنی AVAN REST v1 فعال نشده است.',{exact:true}).count())throw Error('Native ProcessMaker incorrectly hidden behind REST-v1 empty state');
 await page.getByRole('button',{name:'باز کردن BI این اتصال',exact:true}).click();
 await page.getByText('تأیید خرید',{exact:true}).waitFor();

 await page.setViewportSize({width:390,height:844});
 if(await page.evaluate(()=>document.documentElement.scrollWidth>window.innerWidth+2))throw Error('Mobile horizontal overflow');
 await page.setViewportSize({width:1400,height:1000});

 await page.locator('[data-page=system-management]').click();
 const adminFrame=page.frameLocator('.system-admin-frame');
 if(await adminFrame.getByRole('button',{name:'ProcessMaker',exact:true}).count())throw Error('ProcessMaker must not be a top-level settings tab');
 if(await adminFrame.locator('.settings-guide').count())throw Error('Inline management guides must not be rendered');
 const bpmsTop=adminFrame.getByRole('button',{name:'اتصالات BPMS',exact:true});
 if(await bpmsTop.count()!==1)throw Error('Unified BPMS settings tab missing');
 await bpmsTop.click();
 await adminFrame.getByText('ProcessMaker اصلی',{exact:true}).waitFor();
 await adminFrame.getByRole('button',{name:'+ اتصال جدید',exact:true}).click();
 const bpmsType=adminFrame.locator('select[name="bpms_type"]');
 await bpmsType.waitFor();
 if(await bpmsType.inputValue()!=='processmaker')throw Error('New BPMS wizard should default to ProcessMaker');
 await adminFrame.getByRole('button',{name:'انصراف',exact:true}).click();
 if(await adminFrame.locator('a.help-launch[target="_blank"]').count()<1)throw Error('New-tab help lamp missing');

 await adminFrame.getByRole('button',{name:'هوش مصنوعی',exact:true}).click();
 await adminFrame.locator('input[name=api_key]').fill('private-test-value');
 await adminFrame.getByRole('button',{name:'ذخیره تنظیمات',exact:true}).click();
 await adminFrame.getByText('تنظیمات ذخیره شد.',{exact:true}).waitFor();
 if(await adminFrame.locator('input[name=api_key]').inputValue())throw Error('Key not cleared');

 await browser.close();server.close();
 if(errors.length)throw Error(errors.join('\n'));
 console.log('UI PASS: bound BPMS workspace, scoped assistant/BI, unified system management and mobile layout');
})().catch(e=>{console.error(e);server.close();process.exit(1)});
