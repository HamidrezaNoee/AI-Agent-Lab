// Actual admin DOM with mocked APIs; exercises closed editors and selected-user writes.
const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path');
const {JSDOM}=require('jsdom');
const dom=new JSDOM('<main id="main"></main>',{url:'http://127.0.0.1:8188/admin/',runScripts:'outside-only'}),w=dom.window;
const uid='bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb',source='1'.repeat(24),calls=[];
const user={subject:uid,username:'person',name:'Person',email:'p@example.com',enabled:true,role:'Expert'},legacy={subject:'cccccccc-cccc-4ccc-8ccc-cccccccccccc',username:'legacy',name:'Legacy User',email:'legacy@example.com',identity_enabled:true};
w.fetch=async(url,options={})=>{
 calls.push({url,options});let data={};
 const name=url.replace('/admin/api/','').split('?')[0];
 const fixtures={'users/mapped':{users:[user]},'users/identities':{users:[user,legacy]},'users/pending':{pending:[]},'user-bindings/sources':{sources:[{id:source,name:'ProcessMaker',engine:'processmaker'}]},'license/status':{valid:true,modules:[1,2]},'identity/status':{godadmin_local:true,godadmin_username:'godadmin'},'company':{company_name:'Company'},'user-bindings/list':{bindings:[]},'user-bindings/directory':{users:[{external_user_id:'p'.repeat(32),display_name:'BPMS Person',username:'person',active:true}],suggestions:[]}};
 if(fixtures[name])data=fixtures[name];
 else if(!['users/create-identity','users/activate-managed','users/password','users/profile','users/role','users/delete','user-bindings/bind'].includes(name))throw Error('Unexpected '+url);
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

 // Creating a user requires an immediately usable password plus confirmation.
 button(w.document,'افزودن کاربر').click();
 let create=w.document.querySelector('form');
 assert(create.elements.password);assert(create.elements.repeat);
 create.elements.username.value='new.person';
 create.elements.name.value='New Person';
 create.elements.email.value='new.person@example.com';
 create.elements.password.value='new-password-123456';
 create.elements.repeat.value='different-password';
 create.dispatchEvent(new w.Event('submit',{bubbles:true,cancelable:true}));await tick();
 assert(!calls.some(c=>c.url.endsWith('/users/create-identity')));
 create.elements.repeat.value='new-password-123456';
 create.dispatchEvent(new w.Event('submit',{bubbles:true,cancelable:true}));await tick();
 const created=calls.find(c=>c.url.endsWith('/users/create-identity'));assert(created);
 const createBody=JSON.parse(created.options.body);
 assert.equal(createBody.temporary_password,'new-password-123456');
 assert.equal(created.options.headers['X-AVAN-ADMIN-CSRF'],'csrf');

 button(person(),'ویرایش').click();assert.equal(w.document.querySelectorAll('form').length,1);
 button(person(),'تغییر رمز').click(); // clicking another action must open its own editor
 assert(w.document.querySelector('input[name=password]'));
 let f=w.document.querySelector('form');f.elements.password.value='new-password-123456';f.elements.repeat.value='new-password-123456';
 f.dispatchEvent(new w.Event('submit',{bubbles:true,cancelable:true}));await tick();
 const reset=calls.find(c=>c.url.endsWith('/users/password'));assert(reset);assert.equal(JSON.parse(reset.options.body).subject,uid);assert.equal(reset.options.headers['X-AVAN-ADMIN-CSRF'],'csrf');assert.equal(w.document.querySelectorAll('form').length,0);
 button(person(),'تغییر نقش').click();let roleForm=w.document.querySelector('form');assert(roleForm.elements.role);roleForm.elements.role.value='Manager';roleForm.dispatchEvent(new w.Event('submit',{bubbles:true,cancelable:true}));await tick();
 const roleChange=calls.find(c=>c.url.endsWith('/users/role'));assert(roleChange);assert.deepEqual(JSON.parse(roleChange.options.body),{subject:uid,role:'Manager'});
 button(person(),'دسترسی‌ها').click();await tick();assert(w.document.body.textContent.includes('ProcessMaker'));
 button(person(),'انتخاب کاربر BPMS').click();await tick();assert(w.document.querySelector('select[name=external_user_id]'));
 button(person(),'انصراف').click();await tick();
 const legacyCard=[...w.document.querySelectorAll('.avan-user-card')].find(p=>p.querySelector('h2').textContent==='Legacy User');
 assert(legacyCard.textContent.includes('هویت بدون دسترسی AVAN'));
 w.confirm=()=>true;
 button(legacyCard,'فعال‌سازی حساب موجود').click();await tick();
 const activated=calls.find(c=>c.url.endsWith('/users/activate-managed'));
 assert(activated);assert.equal(JSON.parse(activated.options.body).subject,legacy.subject);
 const local=[...w.document.querySelectorAll('.avan-user-card')].find(p=>p.querySelector('h2').textContent==='GodAdmin');
 assert(!button(local,'حذف کاربر'));
 button(person(),'حذف کاربر').click();assert(button(person(),'حذف قطعی کاربر'));
 assert(!calls.some(c=>c.url.endsWith('/users/delete')));
 button(person(),'انصراف').click();assert(!calls.some(c=>c.url.endsWith('/users/delete')));
 button(person(),'حذف کاربر').click();button(person(),'حذف قطعی کاربر').click();await tick();
 const deletion=calls.find(c=>c.url.endsWith('/users/delete'));assert.equal(JSON.parse(deletion.options.body).subject,uid);assert.equal(deletion.options.headers['X-AVAN-ADMIN-CSRF'],'csrf');
 dom.window.close();console.log('Users DOM passed: confirmed login password creation, selected-user reset, CSRF, BPMS editor and deletion.');
})().catch(e=>{dom.window.close();console.error(e);process.exitCode=1});
