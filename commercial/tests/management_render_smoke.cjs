// Focused regression: management tabs must never render as a blank page.
const {chromium}=require('playwright');
const http=require('node:http'),fs=require('node:fs'),path=require('node:path');
const web=path.resolve(__dirname,'../web');

const server=http.createServer((req,res)=>{
  const url=new URL(req.url,'http://localhost');
  const admin=url.pathname.startsWith('/admin/');
  let name=url.pathname.replace(admin?'/admin/':'/','').replace(/^assets\//,'')||'index.html';
  if(name==='help/'||name==='help')name='help.html';
  const root=path.join(web,admin?'admin':'production'),file=path.resolve(root,name);
  if(!file.startsWith(root+path.sep)){res.writeHead(403);return res.end()}
  fs.readFile(file,(err,data)=>{
    if(err){res.writeHead(404);return res.end()}
    res.setHeader('Content-Type',({'.js':'text/javascript','.css':'text/css','.html':'text/html'})[path.extname(file)]||'application/octet-stream');
    res.end(data);
  });
});

(async()=>{
  await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
  const origin='http://127.0.0.1:'+server.address().port;
  const browser=await chromium.launch({
    ...(process.env.CHROMIUM_PATH?{executablePath:process.env.CHROMIUM_PATH}:{}),
    headless:true,args:['--no-sandbox','--disable-dev-shm-usage','--disable-gpu']
  });
  const page=await browser.newPage({viewport:{width:1400,height:1000}});
  page.setDefaultTimeout(8000);
  const pageErrors=[];
  page.on('pageerror',e=>pageErrors.push(e.message));
  let failBpms=false;

  await page.route('**/admin/api/**',async route=>{
    const p=new URL(route.request().url()).pathname;
    let data={};
    if(p==='/admin/api/state')data={
      authenticated:true,password_changed:true,mfa_enrolled:true,mfa_authenticated:true,
      csrf:'test',auth_mode:'oidc'
    };
    else if(p==='/admin/api/settings')data={
      ai:{enabled:false,model:'gpt-4.1-mini',api_key:''},
      mysql:{},processmaker:{},company:{},sql:{},
      installation_id:'11111111-1111-1111-1111-111111111111',
      publisher_public_key_installed:true,password_state:{changed:true,totp:true}
    };
    else if(p==='/admin/api/agent-db/connections')data={active_id:null,connections:[]};
    else if(p==='/admin/api/appearance')data={
      version:4,background_image:'',background_fit:'cover',background_position_x:50,background_position_y:50,background_brightness:1.12,background_contrast:1.08,background_saturation:1.08,background_blur:0,background_dim:.03,overlay_color:'#031522',overlay_opacity:.05,background_parallax:6,
      globe_image:'',globe_visible:true,globe_x:29,globe_y:44,globe_scale:1.22,globe_opacity:1,globe_brightness:1.32,globe_contrast:1.1,globe_saturation:1.22,globe_hue:0,globe_glow:1.3,globe_wobble:1,globe_rotation_speed:1,globe_point_density:1,globe_point_size:1,globe_point_opacity:1,
      node_size:70,node_opacity:1,node_border_width:1,node_glow:1,hover_scale:1.24,hover_duration:180,hover_mode:'card',pause_on_hover:true,show_orbits:true,show_idle_cards:true,orbit_speed:1,orbit_line_width:1.15,orbit_opacity:.78,orbit_glow:1,orbit_primary:'#50EAF7',orbit_secondary:'#FF7053',card_width:176,card_opacity:.94,
      elements:[{id:'docs',enabled:true,title:'مدیریت اسناد',subtitle:'جستجوی هوشمند',description:'اسناد',tags:['RAG'],
        svg:'<svg viewBox="0 0 24 24"><path d="M6 3h8l4 4v14H6z"/></svg>',accent:'#63ECFF',radius:1.2,ellipse:.7,angle:1,speed:.00015,size:0,hover_scale:0,glow:1,opacity:1,card_side:'auto',label_mode:'inherit'}]
    };
    else if(p==='/admin/api/bpms/catalog'){
      if(failBpms)return route.fulfill({status:503,contentType:'application/json',body:JSON.stringify({detail:'خطای آزمایشی کاتالوگ BPMS'})});
      data={connections:[{
        id:'aaaaaaaaaaaaaaaaaaaaaaaa',name:'ProcessMaker اصلی',
        connection_type:'processmaker',engine:'processmaker',active:true,
        mysql:{host:'host.docker.internal',port:3306,database:'bitnami_pm',username:'avan_reader',tls:false,timezone:'Asia/Tehran'},
        oauth:{base_url:'http://host.docker.internal:84',workspace:'workflow',client_id:'client',token_managed:true}
      }],types:[
        {id:'processmaker',label:'ProcessMaker',native:true},
        {id:'camunda',label:'Camunda',native:false},
        {id:'appian',label:'Appian',native:false},
        {id:'uipath',label:'UiPath',native:false},
        {id:'servicenow',label:'ServiceNow',native:false},
        {id:'other',label:'سایر / AVAN REST v1',native:false}
      ]};
    }
    else if(p==='/admin/api/identity/status')data={connected:true,realm:'avan'};
    else if(p==='/admin/api/company')data={tenant_id:'tenant-test',company_name:'سازمان تست'};
    else if(p==='/admin/api/license/status')data={
      valid:true,mode:'licensed',active_users:1,max_users:10,remaining_seats:9,
      remaining_days:30,expires_at:'2026-12-31T00:00:00Z',modules:[1,2,3,4]
    };
    else if(p==='/admin/api/users/mapped')data={users:[]};
    else if(p==='/admin/api/users/pending')data={pending:[]};
    else if(p==='/admin/api/processmaker/users')data={users:[]};
    else data={};
    await route.fulfill({json:data});
  });

  await page.goto(origin+'/admin/?embedded=1');
  await page.getByRole('heading',{name:'مدیریت سامانه',exact:true}).waitFor();

  const tabs=[
    ['وضعیت سامانه','connections'],
    ['اتصالات BPMS','bpms'],
    ['بانک Agent','agentdb'],
    ['هوش مصنوعی','ai'],
    ['سازمان و دسترسی','organization'],
    ['تنظیمات ظاهری','appearance'],
    ['لایسنس','license']
  ];
  for(const [label,code] of tabs){
    await page.getByRole('button',{name:label,exact:true}).click();
    const host=page.locator('[data-settings-page="'+code+'"]');
    await host.waitFor();
    if(await host.locator('.panel').count()<1)throw Error('Blank management tab: '+label);
    const box=await host.boundingBox();
    if(!box||box.height<40)throw Error('Collapsed management tab: '+label);
    if(!(await host.innerText()).trim())throw Error('Empty management tab text: '+label);
  }

  // Exact regression from the reported screenshot: BPMS API failure must not leave white space.
  await page.getByRole('button',{name:'وضعیت سامانه',exact:true}).click();
  failBpms=true;
  await page.getByRole('button',{name:'اتصالات BPMS',exact:true}).click();
  const bpms=page.locator('[data-settings-page="bpms"]');
  await bpms.getByText(/فهرست اتصالات BPMS قابل دریافت نیست/).waitFor();
  await bpms.getByRole('button',{name:'تلاش دوباره',exact:true}).waitFor();
  if(await bpms.locator('.panel').count()<1)throw Error('BPMS failure rendered blank');

  if(pageErrors.length)throw Error('Browser page errors: '+pageErrors.join(' | '));
  await browser.close();server.close();
  console.log('MANAGEMENT RENDER PASS: every tab renders content; BPMS 503 shows recoverable error instead of blank page');
})().catch(async e=>{
  console.error(e);
  try{server.close()}catch(_){}
  process.exit(1);
});