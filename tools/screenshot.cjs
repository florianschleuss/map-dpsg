// Requires optional developer dependency: npm install --no-save playwright
// Uses installed Chrome when CHROME_PATH is set; no app server is started.
const fs=require('node:fs');const path=require('node:path');
const {chromium}=require(process.env.PLAYWRIGHT_MODULE || 'playwright');
(async()=>{
 const root=path.resolve(__dirname,'..');
 const browser=await chromium.launch({headless:true,...(process.env.CHROME_PATH?{executablePath:process.env.CHROME_PATH}:{})});
 const results=[];
 try{
 for(const name of ['dashboard','anmeldungen','statistik','formularbaukasten','elternformular']){
  const page=await browser.newPage({viewport:{width:1440,height:1080},deviceScaleFactor:1});
  const errors=[];page.on('pageerror',e=>errors.push(e.message));
  await page.route('**/*',async route=>{
   const url=new URL(route.request().url());
   if(url.origin!=='https://map.example.org'||!url.pathname.startsWith('/static/'))return route.abort();
   const relative=decodeURIComponent(url.pathname.slice(8));
   const candidates=[path.join(root,'static',relative),path.join(root,'map/static',relative),...(process.env.DJANGO_STATIC_ROOT?[path.join(process.env.DJANGO_STATIC_ROOT,relative)]:[])];
   const file=candidates.find(p=>fs.existsSync(p)&&fs.statSync(p).isFile());
   if(!file)return route.abort();
   const ext=path.extname(file);await route.fulfill({body:fs.readFileSync(file),contentType:({'.js':'application/javascript','.css':'text/css','.svg':'image/svg+xml','.png':'image/png'})[ext]||'application/octet-stream'});
  });
  await page.setContent(fs.readFileSync(path.join(root,'docs/.rendered',name+'.html'),'utf8'),{waitUntil:'networkidle'});
  if(name==='formularbaukasten'){
   // Open the privacy library block to exercise the configurable label.
   const block=page.locator('.map-library-item').filter({hasText:'Datenschutz'});await block.click();
   await page.locator('.map-builder-section').last().locator(':scope > summary').click();
  }
  const overflow=await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth);
  if(overflow||errors.length)throw new Error(name+': '+JSON.stringify({overflow,errors}));
  await page.screenshot({path:path.join(root,'docs/screenshots',name+'.png'),fullPage:true});
  await page.setViewportSize({width:390,height:844});
  if(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth))throw new Error(name+' mobile overflow');
  if(name==='elternformular')await page.screenshot({path:path.join(root,'docs/screenshots','mobil.png'),fullPage:true});
  results.push({page:name,desktopOverflow:false,mobileOverflow:false,scriptErrors:errors});await page.close();
 }
 }finally{await browser.close();}
 fs.writeFileSync(path.join(root,'docs/screenshots/checks.json'),JSON.stringify(results,null,2));console.log(JSON.stringify(results));
})().catch(e=>{console.error(e);process.exit(1)});
