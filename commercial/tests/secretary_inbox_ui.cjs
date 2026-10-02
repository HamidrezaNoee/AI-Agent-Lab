// DOM integration with mocked source APIs; not a rendered browser test.
const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path');
const {JSDOM}=require('jsdom');
const dom=new JSDOM('<html dir="rtl"><body><main id="main"></main><div id="toast"></div></body></html>',{url:'https://avan.example',runScripts:'outside-only'}),w=dom.window;
w.structuredClone=structuredClone;w.HTMLMediaElement.prototype.pause=()=>{};w.HTMLElement.prototype.scrollIntoView=()=>{};
const source='1'.repeat(24),pack='2'.repeat(24),caseid='a'.repeat(32),calls=[];
const task={case_uid:caseid,index:1,pack_id:pack,stage:'invitation_approval',stage_label:'تأیید دعوت‌نامه',title:'<script>unsafe</script>',number:'100',available:true};
let row={values:{MTG_InvitationApproval:'',MTG_InvitationChairComment:''},revision:1,status:'draft',questions:[]};
function view(){return {task,draft:structuredClone(row),form:{MTG_InvitationApproval:{type:'hidden',label:'رأی رئیس'},MTG_InvitationChairComment:{type:'textarea',label:'نظر رئیس'}},missing:row.values.MTG_InvitationApproval?[]:[{field:'MTG_InvitationApproval',question:'رأی شما چیست؟'}],context:{MTG_MeetingTitle:task.title},people:[]}}
w.fetch=async(url,options={})=>{
 calls.push({url,options});let data;
 if(url.endsWith('/inbox'))data={tasks:[task],notifications:[],packs:[{id:pack,title:'مدیریت جلسات'}],oauth_connected:true,sessions:[]};
 else if(url.endsWith('/tasks/open')||url.endsWith('/tasks/load'))data=view();
 else if(url.includes('/edit?')){const body=JSON.parse(options.body);assert.equal(body.revision,row.revision);row={...row,values:body.values,revision:row.revision+1};data=view()}
 else if(url.includes('/submit?')){const body=JSON.parse(options.body);assert.equal(body.revision,row.revision);assert.equal(body.confirmed,true);data={status:'sent'}}
 else throw Error('Unexpected API '+url);
 return {ok:true,status:200,json:async()=>data};
};
let code=fs.readFileSync(path.join(__dirname,'../web/production/app.js'),'utf8').replace('document.addEventListener("DOMContentLoaded",init);','');
w.eval(code+'\nwindow.testAVAN={app,secretaryPage,cleanMedia};');w.testAVAN.app.user={modules:[2]};w.testAVAN.app.csrf='csrf-test';
const tick=()=>new Promise(resolve=>setTimeout(resolve,15));
(async()=>{
 await w.testAVAN.secretaryPage(source);
 const buttons=()=>Array.from(w.document.querySelectorAll('button'));
 buttons().find(b=>b.textContent.startsWith('تأیید دعوت‌نامه')).click();await tick();
 const vote=w.document.querySelector('[aria-label="رأی رئیس"]');assert(vote);assert.equal(vote.value,'');
 const send=()=>buttons().find(b=>b.textContent.includes('تأیید بازبینی و ارسال'));
 assert(send().disabled);assert.equal(w.document.querySelectorAll('script').length,0);
 vote.value='Approved';vote.dispatchEvent(new w.Event('input',{bubbles:true}));assert(send().disabled);
 buttons().find(b=>b.textContent==='ذخیره اصلاحات').click();await tick();assert.equal(row.revision,2);assert(!send().disabled);
 send().click();await tick();const submit=calls.find(c=>c.url.includes('/submit?'));assert(submit);assert.equal(submit.options.headers['X-AVAN-CSRF'],'csrf-test');
 assert(calls.every(c=>c.url.startsWith('/api/sources/'+source+'/')));assert(w.document.body.textContent.includes('به مرحله بعد ارسال شد'));
 w.testAVAN.cleanMedia();w.close();console.log('Secretary DOM integration passed: chair vote, dirty guard, revision, CSRF, source scope, text escaping.');
})().catch(e=>{w.close();console.error(e);process.exitCode=1});
