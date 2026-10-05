// DOM integration with mocked source APIs; not a rendered browser test.
const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path');
const {JSDOM}=require('jsdom');
const dom=new JSDOM('<html dir="rtl"><body><main id="main"></main><div id="toast"></div></body></html>',{url:'https://avan.example',runScripts:'outside-only'}),w=dom.window;
w.structuredClone=structuredClone;w.requestAnimationFrame=fn=>setTimeout(fn,0);w.HTMLMediaElement.prototype.pause=()=>{};w.HTMLElement.prototype.scrollIntoView=()=>{};
const source='1'.repeat(24),pack='2'.repeat(24),caseid='a'.repeat(32),calls=[];
const task={case_uid:caseid,index:1,pack_id:pack,stage:'invitation_approval',stage_label:'تأیید دعوت‌نامه',title:'<script>unsafe</script>',number:'100',available:true};
let row={values:{MTG_InvitationApproval:'',MTG_InvitationChairComment:''},revision:1,status:'draft',questions:[],history:[{role:'assistant',text:'دعوت‌نامه آماده تصمیم شماست.'}]},failTurn=false;
function view(){return {task,draft:structuredClone(row),form:{MTG_InvitationApproval:{type:'hidden',label:'رأی رئیس'},MTG_InvitationChairComment:{type:'textarea',label:'نظر رئیس'}},missing:row.values.MTG_InvitationApproval?[]:[{field:'MTG_InvitationApproval',question:'رأی شما چیست؟'}],context:{MTG_MeetingTitle:task.title},people:[]}}
w.fetch=async(url,options={})=>{
 calls.push({url,options});let data;
 if(url.endsWith('/inbox'))data={tasks:[task],notifications:[],packs:[{id:pack,title:'مدیریت جلسات'}],oauth_connected:true,sessions:[]};
 else if(url.endsWith('/flow-graph'))data={
  person:{uid:'u1',name:'مدیر سیستم',username:'administrator'},
  summary:{total_cases:1,active_cases:1,completed_cases:0,waiting_my_action:0,average_progress:29},
  rows:[{case_uid:caseid,case_number:100,meeting_no:'MTG-100',title:'جلسه تست',status:'active',status_label:'فعال',
   current_stage:'invitation_approval',current_stage_title:'تأیید دعوت‌نامه',current_owners:[{uid:'u2',name:'مدیرعامل',unit:'مدیریت'}],
   current_owner_label:'مدیرعامل',my_roles:['secretary'],my_role_label:'دبیر',progress_percent:29,
   nodes:[
    {key:'invitation',title:'دعوت جلسه',role:'دبیر',index:1,state:'done'},
    {key:'invitation_approval',title:'تأیید دعوت‌نامه',role:'رئیس جلسه',index:2,state:'current'},
    {key:'minutes',title:'ثبت صورت‌جلسه',role:'دبیر',index:3,state:'future'},
    {key:'minutes_approval',title:'تأیید صورت‌جلسه',role:'رئیس جلسه',index:4,state:'future'},
    {key:'action_execution',title:'اجرای اقدام',role:'اقدام‌کننده',index:5,state:'future'},
    {key:'action_review',title:'بررسی اقدام',role:'دبیر',index:6,state:'future'},
    {key:'monitoring',title:'پایش و اختتام',role:'دبیر',index:7,state:'future'}],
   actions:{total:1,open:1,review:0,closed:0},
   action_branches:[{action_no:'A-01',title:'پیگیری قرارداد',case_uid:'c'.repeat(32),case_number:900,
    owner:{uid:'u2',name:'مدیرعامل',username:'ceo',unit:'مدیریت'},current_owner:{uid:'u2',name:'مدیرعامل',username:'ceo',unit:'مدیریت'},
    stage:'action_execution',stage_label:'اجرای اقدام',state:'execution',progress_percent:60}],
   history:[{case_uid:caseid,index:1,stage:'invitation',stage_title:'دعوت جلسه',owner:{name:'مدیر سیستم',username:'administrator'},state:'done',delegated_at:'2026-10-05 09:00:00'}]}],
  filters:{people:[{uid:'u1',name:'مدیر سیستم',username:'administrator'}],owners:[{uid:'u2',name:'مدیرعامل'}],units:['مدیریت'],
   roles:[{value:'secretary',label:'دبیر'}],stages:[{value:'invitation_approval',label:'تأیید دعوت‌نامه'}],statuses:[{value:'active',label:'فعال'}]},
  total:1,offset:0,limit:30,has_more:false,truncated:false
 };
 else if(url.endsWith('/tasks/open')||url.endsWith('/tasks/load'))data=view();
 else if(url.includes('/turn?')){const body=JSON.parse(options.body);assert.equal(body.revision,row.revision);if(failTurn){failTurn=false;return {ok:false,status:503,json:async()=>({detail:'سرویس هوش مصنوعی در زمان مقرر پاسخ نداد؛ دوباره تلاش کنید.'})}}row={...row,revision:row.revision+1,history:[...row.history,{role:'user',text:body.text},{role:'assistant',text:'پیام شما بررسی شد.'}]};data={...view(),assistant:{message:'پیام شما بررسی شد.',summary:'',missing:view().missing},draft:structuredClone(row)}}
 else if(url.includes('/edit?')){const body=JSON.parse(options.body);assert.equal(body.revision,row.revision);row={...row,values:body.values,revision:row.revision+1};data=view()}
 else if(url.includes('/submit?')){const body=JSON.parse(options.body);assert.equal(body.revision,row.revision);assert.equal(body.confirmed,true);data={status:'sent'}}
 else throw Error('Unexpected API '+url);
 return {ok:true,status:200,json:async()=>data};
};
let code=fs.readFileSync(path.join(__dirname,'../web/production/app.js'),'utf8').replace('document.addEventListener("DOMContentLoaded",init);','');
w.eval(code+'\nwindow.testAVAN={app,secretaryPage,cleanMedia};');w.testAVAN.app.user={modules:[2]};w.testAVAN.app.csrf='csrf-test';
const tick=()=>new Promise(resolve=>setTimeout(resolve,15));
(async()=>{
 await w.testAVAN.secretaryPage(source);await tick();
 assert(w.document.body.textContent.includes('نقشه جریان پرونده‌ها'));
 assert.equal(w.document.querySelectorAll('.case-git-node').length,7);
 assert(w.document.body.textContent.includes('مدیرعامل'));
 assert(w.document.body.textContent.includes('شاخه‌های اقدامات'));
 assert.equal(w.document.querySelectorAll('.case-branch').length,1);
 assert(w.document.body.textContent.includes('نمای سریع'));
 assert(w.document.querySelector('[aria-label="مرتب‌سازی"]'));
 const buttons=()=>Array.from(w.document.querySelectorAll('button'));
 const steps=Array.from(w.document.querySelectorAll('.secretary-step'));
 assert.equal(steps.length,7);
 assert.equal(steps[0].dataset.stage,'invitation');
 assert.equal(steps[6].dataset.stage,'monitoring');
 assert.equal(steps.filter(b=>!b.disabled).length,1);
 assert.equal(steps[1].querySelector('.secretary-step-count').textContent,'۱');
 assert.equal(w.document.querySelectorAll('[data-action="new-invitation"]').length,1);
 assert.equal(w.document.querySelectorAll('.secretary-step:disabled .secretary-step-count').length,0);
 w.document.querySelector('[data-case-uid]').click();await tick();
 assert(w.document.body.textContent.includes('گفت‌وگو با دبیر هوشمند'));
 assert(w.document.querySelector('input[aria-label="افزودن فایل به گفت‌وگوی دبیر"]'));
 assert(buttons().some(b=>b.textContent.includes('تأیید و ارسال')));
 const chatInput=w.document.querySelector('textarea[aria-label="پیام به دبیر هوشمند"]');assert(chatInput);
 chatInput.value='این پیام آزمایشی من است';
 buttons().find(b=>b.textContent==='↑').click();
 assert(w.document.body.textContent.includes('این پیام آزمایشی من است'));
 assert(w.document.body.textContent.includes('دبیر در حال بررسی پیام شماست'));
 await tick();
 assert(w.document.body.textContent.includes('پیام شما بررسی شد.'));
 assert(!w.document.body.textContent.includes('دبیر در حال بررسی پیام شماست'));
 const input2=w.document.querySelector('textarea[aria-label="پیام به دبیر هوشمند"]');input2.value='این پیام باید دوباره تلاش شود';failTurn=true;
 buttons().find(b=>b.textContent==='↑').click();assert.equal(input2.value,'');await tick();
 assert(w.document.body.textContent.includes('↻ تلاش مجدد'));
 assert.equal(w.document.querySelector('textarea[aria-label="پیام به دبیر هوشمند"]').value,'');
 buttons().find(b=>b.textContent.includes('تلاش مجدد')).click();await tick();
 assert(w.document.body.textContent.includes('پیام شما بررسی شد.'));
 const vote=w.document.querySelector('[aria-label="رأی رئیس"]');assert(vote);assert.equal(vote.value,'');
 const send=()=>buttons().find(b=>b.textContent.includes('تأیید بازبینی و ارسال'));
 assert(send().disabled);assert.equal(w.document.querySelectorAll('script').length,0);
 vote.value='Approved';vote.dispatchEvent(new w.Event('input',{bubbles:true}));assert(send().disabled);
 buttons().find(b=>b.textContent==='ذخیره اصلاحات').click();await tick();assert.equal(row.revision,4);assert(!send().disabled);
 send().click();await tick();const submit=calls.find(c=>c.url.includes('/submit?'));assert(submit);assert.equal(submit.options.headers['X-AVAN-CSRF'],'csrf-test');
 assert(calls.every(c=>c.url.startsWith('/api/sources/'+source+'/')));assert(w.document.body.textContent.includes('به مرحله بعد ارسال شد'));
 w.testAVAN.cleanMedia();w.close();console.log('Secretary DOM integration passed: chair vote, dirty guard, revision, CSRF, source scope, text escaping.');
})().catch(e=>{w.close();console.error(e);process.exitCode=1});

