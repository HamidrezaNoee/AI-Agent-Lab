// Real Chromium/WebAudio/MediaRecorder; synthetic sound and mocked service callbacks.
// This does not establish microphone quality, paid-model latency or live PM routing.
const {chromium}=require('playwright');
const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),http=require('node:http');
const web=path.resolve(__dirname,'../web/production');
const server=http.createServer((req,res)=>{
 if(req.url==='/') {res.setHeader('Content-Type','text/html');return res.end('<html lang="fa" dir="rtl"><head><meta charset="utf-8"><link rel="stylesheet" href="/app.css"><script src="/live-voice.js"></script></head><body><button id="open">گفتگوی صوتی</button></body></html>')}
 const name=req.url.slice(1);
 if(!['app.css','live-voice.js'].includes(name)){res.writeHead(404);return res.end()}
 res.setHeader('Content-Type',name.endsWith('.js')?'text/javascript':'text/css');res.end(fs.readFileSync(path.join(web,name)));
});
(async()=>{
 await new Promise(r=>server.listen(0,'127.0.0.1',r));let browser;
 try{
  browser=await chromium.launch({headless:true,...(process.env.CHROMIUM_PATH?{executablePath:process.env.CHROMIUM_PATH}:{}),args:['--no-sandbox','--disable-dev-shm-usage','--autoplay-policy=no-user-gesture-required']});
  const page=await browser.newPage({viewport:{width:1280,height:900}});const errors=[];page.on('pageerror',e=>errors.push(e.message));
  await page.goto('http://127.0.0.1:'+server.address().port+'/');
  await page.evaluate(()=>{
   window.calls=[];
   navigator.mediaDevices.getUserMedia=async()=>{
    window.inputContext=new AudioContext();await inputContext.resume();
    const oscillator=inputContext.createOscillator(),gain=inputContext.createGain(),destination=inputContext.createMediaStreamDestination();
    gain.gain.value=.12;oscillator.connect(gain);gain.connect(destination);oscillator.start();
    window.inputStream=destination.stream;return inputStream;
   };
   function wav(){
    const rate=16000,length=rate*3,b=new ArrayBuffer(44+length*2),v=new DataView(b);
    const text=(at,s)=>{for(let i=0;i<s.length;i++)v.setUint8(at+i,s.charCodeAt(i))};
    text(0,'RIFF');v.setUint32(4,36+length*2,true);text(8,'WAVE');text(12,'fmt ');v.setUint32(16,16,true);v.setUint16(20,1,true);v.setUint16(22,1,true);v.setUint32(24,rate,true);v.setUint32(28,rate*2,true);v.setUint16(32,2,true);v.setUint16(34,16,true);text(36,'data');v.setUint32(40,length*2,true);
    for(let i=0;i<length;i++)v.setInt16(44+i*2,Math.sin(i*2*Math.PI*220/rate)*5000,true);
    return new Blob([b],{type:'audio/wav'});
   }
   document.querySelector('#open').onclick=()=>{
    window.voice=new AvanLiveVoice({
     transcribe:async(blob,signal)=>{calls.push(['stt',blob.size,signal.aborted]);return 'عنوان جلسه را اصلاح کن'},
     turn:async text=>{calls.push(['turn',text])},
     speech:async()=>{calls.push(['tts']);return {blob:wav(),parts:1}},
     cancelCurrent:()=>calls.push(['cancel'])
    });voice.open();
   };
  });
  await page.locator('#open').click();
  await page.waitForFunction(()=>voice.state==='listening'&&voice.heard&&voice.level>.1);
  const directory=process.env.AVAN_SCREENSHOT_DIR;
  if(directory){fs.mkdirSync(directory,{recursive:true});await page.screenshot({path:path.join(directory,'voice-desktop.png')})}
  await page.getByRole('button',{name:'پایان صحبت',exact:true}).click();
  await page.waitForFunction(()=>voice.state==='speaking'&&voice.level>.1);
  assert.deepEqual(await page.evaluate(()=>calls.filter(c=>c[0]!=='cancel').map(c=>c[0])),['stt','turn','tts']);
  assert.ok(await page.evaluate(()=>calls[0][1]>16));
  await page.getByRole('button',{name:'نوبت من',exact:true}).click();
  await page.waitForFunction(()=>voice.state==='listening'&&voice.audio===null);
  await page.setViewportSize({width:390,height:844});
  if(directory)await page.screenshot({path:path.join(directory,'voice-mobile.png')});
  assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
  await page.getByRole('button',{name:'پایان گفتگو',exact:true}).click();
  assert.ok(await page.evaluate(()=>!voice.active&&voice.controller.signal.aborted&&inputStream.getTracks().every(t=>t.readyState==='ended')));
  assert.equal(await page.locator('dialog').count(),0);
  await page.evaluate(()=>inputContext.close());
  assert.deepEqual(errors,[]);
  console.log('PASS: reactive input/output orb, STT/turn/TTS, interruption, mobile layout, track cleanup');
 }finally{await browser?.close();await new Promise(r=>server.close(r))}
})().catch(e=>{console.error(e);process.exitCode=1});
