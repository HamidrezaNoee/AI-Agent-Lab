// Process-specific navigation and stale-response regression using a mocked DOM/API.
const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),{JSDOM}=require('jsdom');
const html=fs.readFileSync(path.join(__dirname,'../web/production/index.html'),'utf8');
const dom=new JSDOM(html,{url:'https://avan.example',runScripts:'outside-only'}),w=dom.window;
w.structuredClone=structuredClone;w.HTMLElement.prototype.scrollIntoView=()=>{};w.HTMLMediaElement.prototype.pause=()=>{};
const sid='1'.repeat(24),meeting='2'.repeat(24),purchase='3'.repeat(24),calls=[];
const manifests={
 [meeting]:{process:{id:meeting,title:'جلسات',renderer:'meeting',processes:[]},section:'inbox',navigation:[{id:'inbox',label:'کارتابل من',count:1},{id:'drafts',label:'جلسه جدید',view:'drafts',count:0},{id:'approvals',label:'تأییدهای من',count:1}],tasks:[{case_uid:'a'.repeat(32),index:1,pack_id:meeting,stage:'invitation_approval',stage_label:'تأیید دعوت‌نامه',title:'محرمانه جلسه',number:'100',available:true}],notifications:[],sessions:[]},
 [purchase]:{process:{id:purchase,title:'خرید خارجی',renderer:'generic',processes:[{process_uid:'c'.repeat(32),title:'خرید خارجی'}]},section:'inbox',navigation:[{id:'inbox',label:'درخواست‌های خرید',view:'tasks',count:1},{id:'overview',label:'نمای خرید',view:'overview',count:1}],tasks:[{case_uid:'b'.repeat(32),index:2,pack_id:purchase,stage:'review',stage_label:'بررسی خرید',title:'خرید کالا',number:'200',available:true,read_only:true}],notifications:[],sessions:[]}
};
let hold=false,release;
w.fetch=async(url,options={})=>{calls.push(url);let value;
 if(url.endsWith('/process-workspace'))value={processes:[manifests[meeting].process,manifests[purchase].process]};
 else if(url.includes('/process-workspace/')){const id=url.split('/process-workspace/')[1].split('?')[0];if(hold&&id===meeting){hold=false;await new Promise(resolve=>release=resolve)}value=structuredClone(manifests[id]);value.section=new URL(url,'https://avan.example').searchParams.get('section')||'inbox'}
 else if(url.includes('/secretary/inbox'))value={...manifests[meeting],packs:[manifests[meeting].process],oauth_connected:true};
 else throw Error('Unexpected API '+url);
 return {ok:true,status:200,json:async()=>value};
};
const code=fs.readFileSync(path.join(__dirname,'../web/production/app.js'),'utf8').replace('document.addEventListener("DOMContentLoaded",init);','');
w.eval(code+'\nwindow.testAVAN={app,setupUser,select,cleanMedia};');
const tick=()=>new Promise(resolve=>setTimeout(resolve,25));
(async()=>{
 w.testAVAN.setupUser({name:'رئیس',role:'Expert',company:'شرکت',subject:'actor',modules:[1,2],csrf:'csrf',workspace_access:true,workspace_navigation:true,bpms_sources:[{source_id:sid,source_name:'PM',engine:'processmaker',capabilities:['overview','secretary']}]});await tick();
 assert(w.document.getElementById('pm-nav').hidden);
 assert(w.document.querySelector('[data-section="approvals"]'));
 hold=true;w.document.querySelector('[data-section="approvals"]').click();await tick();assert(release);
 const choose=w.document.querySelector('[aria-label="فرایند · PM"]');choose.value=purchase;choose.dispatchEvent(new w.Event('change',{bubbles:true}));await tick();
 release();await tick();
 assert(!w.document.querySelector('[data-section="approvals"]'));
 assert(w.document.querySelector('[data-section="overview"]'));
 const main=w.document.getElementById('main').textContent;assert(main.includes('خرید خارجی'));assert(main.includes('بررسی خرید'));assert(!main.includes('محرمانه جلسه'));
 assert(!calls.some(url=>url.includes('/secretary')&&url.includes(purchase)));
 w.testAVAN.cleanMedia();w.close();console.log('Process DOM integration passed: distinct menus, selected inbox, generic renderer and stale-response isolation.');
})().catch(e=>{w.close();console.error(e);process.exitCode=1});
