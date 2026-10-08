const {chromium}=require('playwright');
(async()=>{
 const browser=await chromium.launch({...(process.env.CHROMIUM_PATH?{executablePath:process.env.CHROMIUM_PATH}:{}),headless:true,args:['--no-sandbox']});
 try{
 const page=await browser.newPage({viewport:{width:1200,height:1000}});
 await page.setContent('<html lang="fa" dir="rtl"><main id="test"></main></html>');
 await page.addScriptTag({path:process.cwd()+'/commercial/web/admin/app.js'});
 await page.addStyleTag({path:process.cwd()+'/commercial/web/admin/app.css'}).catch(()=>{});
 await page.evaluate(()=>{
  window.calls=[];
  api=async (path,body)=>{window.calls.push({path,body});return path==='ai/models'?{models:['model-a','model-b']}:{model:body.model}};
  renderAI(document.getElementById('test'),{enabled:true,model:'model-a'});
 });
 await page.getByRole('button',{name:'دریافت مدل‌های حساب',exact:true}).click();
 await page.getByLabel('مدل‌های در دسترس حساب').selectOption('model-b');
 if(await page.locator('input[name=model]').inputValue()!=='model-b')throw Error('selection failed');
 await page.getByRole('button',{name:'بررسی مدل انتخاب‌شده پیش از ذخیره',exact:true}).click();
 await page.getByRole('button',{name:'ذخیره تنظیمات',exact:true}).click();
 const calls=await page.evaluate(()=>window.calls);
 if(calls.find(x=>x.path==='ai/save').body.model!=='model-b')throw Error('save failed');
 await page.screenshot({path:'/tmp/avan-model-picker.png'});
 console.log('Model list, selection, unsaved probe and save passed');
 }finally{await browser.close()}
})().catch(e=>{console.error(e);process.exit(1)});
