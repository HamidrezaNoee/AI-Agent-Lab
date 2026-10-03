// Actual admin DOM with mocked APIs; exercises closed editors and selected-user writes.
const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path');
const {JSDOM}=require('jsdom');
const dom=new JSDOM('<main id="main"></main>',{url:'http://127.0.0.1:8188/admin/',runScripts:'outside-only'}),w=dom.window;
const uid='bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb',source='1'.repeat(24),calls=[];
const user={subject:uid,username:'person',name:'Person',email:'p@example.com',enabled:true,role:'Expert'};
w.fetch=async(url,options={})=>{
 calls.push({url,options});let data={};
 const name=url.replace('/admin/api/','').split('?')[0];
 const fixtures={'users/mapped':{users:[user]},'users/identities':{users:[user]},'users/pending':{pending:[]},'user-bindings/sources':{sources:[{id:source,name:'ProcessMaker',engine:'processmaker'}]},'license/status':{valid:true,modules:[1,2]},'identity/status':{godadmin_local:true,godadmin_username:'godadmin'},'company':{company_name:'Company'},'user-bindings/list':{bindings:[]},'user-bindings/directory':{users:[{external_user_id:'p'.repeat(32),display_name:'BPMS Person',username:'person',active:true}],suggestions:[]}};
 if(fixtures[name])data=fixtures[name];
 else if(!['users/password','users/profile','users/delete','user-bindings/bind'].includes(name))throw Error('Unexpected '+url);
 return {ok:true,json:async()=>data};
};
let code=fs.readFileSync(path.join(__dirname,'../web/admin/app.js'),'utf8').replace('document.addEventListener("DOMContentLoaded",start);','');
w.eval(code+'\nstate.csrf="csrf";showSettings=async()=>{const m=document.getElementById("main");m.replaceChildren();await renderUsers(m)};window.renderUsers=renderUsers;');
const tick=()=>new Promise(r=>setTimeout(r,20));
const button=(root,label)=>[...root.querySelectorAll('button')].find(b=>b.textContent===label);
const person=()=>[...w.document.querySelectorAll('.connection-list > section')].find(p=>p.querySelector('h2').textContent==='Person');
(async()=>{
 await w.renderUsers(w.document.getElementById('main'));
 assert.equal(w.document.querySelectorAll('form').length,0);
 button(person(),'ویرایش').click();assert.equal(w.document.querySelectorAll('form').length,1);
 button(person(),'تغییر رمز').click(); // clicking another action must open its own editor
 assert(w.document.querySelector('input[name=password]'));
 let f=w.document.querySelector('form');f.elements.password.value='new-password-123456';f.elements.repeat.value='new-password-123456';
 f.dispatchEvent(new w.Event('submit',{bubbles:true,cancelable:true}));await tick();
 const reset=calls.find(c=>c.url.endsWith('/users/password'));assert(reset);assert.equal(JSON.parse(reset.options.body).subject,uid);assert.equal(reset.options.headers['X-AVAN-ADMIN-CSRF'],'csrf');assert.equal(w.document.querySelectorAll('form').length,0);
 button(person(),'دسترسی‌ها').click();await tick();assert(w.document.body.textContent.includes('ProcessMaker'));
 button(person(),'انتخاب کاربر BPMS').click();await tick();assert(w.document.querySelector('select[name=external_user_id]'));
 button(person(),'انصراف').click();await tick();
 const local=[...w.document.querySelectorAll('.avan-user-card')].find(p=>p.querySelector('h2').textContent==='GodAdmin');
 assert(!button(local,'حذف کاربر'));
 button(person(),'حذف کاربر').click();assert(button(person(),'حذف قطعی کاربر'));
 assert(!calls.some(c=>c.url.endsWith('/users/delete')));
 button(person(),'انصراف').click();assert(!calls.some(c=>c.url.endsWith('/users/delete')));
 button(person(),'حذف کاربر').click();button(person(),'حذف قطعی کاربر').click();await tick();
 const deletion=calls.find(c=>c.url.endsWith('/users/delete'));assert.equal(JSON.parse(deletion.options.body).subject,uid);assert.equal(deletion.options.headers['X-AVAN-ADMIN-CSRF'],'csrf');
 dom.window.close();console.log('Users DOM passed: closed fields, selected-user password, CSRF, per-BPMS editor and confirmed deletion.');
})().catch(e=>{dom.window.close();console.error(e);process.exitCode=1});
