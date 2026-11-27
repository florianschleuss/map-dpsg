/* Regression checks for shared geometry and full-width room data surfaces.
 * Run after python tools/render_layout_fixtures.py. Playwright is an optional dev dependency.
 */
const fs=require('fs'),path=require('path');
const engines=require(process.env.MAP_PLAYWRIGHT_MODULE||'playwright');
const engine=engines[process.env.MAP_BROWSER_TYPE||'chromium'];
const repo=path.resolve(process.env.MAP_LAYOUT_SOURCE||'.');
const fixtures=path.resolve(process.env.MAP_LAYOUT_FIXTURES||'docs/.rendered/layout');
const pages=JSON.parse(fs.readFileSync(path.join(fixtures,'pages.json'),'utf8')).filter(p=>!process.env.MAP_LAYOUT_PAGES||process.env.MAP_LAYOUT_PAGES.split(',').includes(p.name));
const widths=process.env.MAP_LAYOUT_WIDTHS?process.env.MAP_LAYOUT_WIDTHS.split(',').map(Number):[360,390,768,1280,1440,1920];
const adminPathFile=path.join(fixtures,'django-admin-static-path.txt');
const adminStatic=process.env.MAP_DJANGO_ADMIN_STATIC||(fs.existsSync(adminPathFile)?fs.readFileSync(adminPathFile,'utf8').trim():'');
const results=[],failures=[];
const near=(a,b)=>Math.abs(a-b)<1.5;
const requireThat=(ok,message)=>{if(!ok)throw Error(message);};
(async()=>{const browser=await engine.launch({headless:true,...(process.env.MAP_BROWSER_EXECUTABLE?{executablePath:process.env.MAP_BROWSER_EXECUTABLE}:{})});try{
 for(const theme of ['light','dark'])for(const width of widths){
  const context=await browser.newContext({viewport:{width,height:900},colorScheme:theme});
  await context.addInitScript(()=>{window.layoutShifts=[];if(PerformanceObserver.supportedEntryTypes?.includes('layout-shift'))new PerformanceObserver(list=>{for(const e of list.getEntries())if(!e.hadRecentInput)window.layoutShifts.push(e.value);}).observe({type:'layout-shift',buffered:true});});
  await context.route('**/*',route=>{const u=new URL(route.request().url());if(u.pathname.startsWith('/audit/'))return route.fulfill({body:fs.readFileSync(path.join(fixtures,u.pathname.split('/').pop()+'.html')),contentType:'text/html; charset=utf-8'});
   if(u.pathname==='/admin/jsi18n/')return route.fulfill({body:fs.readFileSync(path.join(fixtures,'admin-i18n.js')),contentType:'application/javascript'});
   if(u.pathname==='/raeume/konflikte/')return route.fulfill({contentType:'application/json',body:JSON.stringify({valid:true,count:0,html:'Keine Überschneidung.'})});
   if(u.pathname.startsWith('/static/')){const rel=u.pathname.slice(8),roots=[path.join(repo,'static'),adminStatic].filter(Boolean);const file=roots.map(r=>path.join(r,rel)).find(f=>fs.existsSync(f)&&fs.statSync(f).isFile());if(file)return route.fulfill({body:fs.readFileSync(file),contentType:file.endsWith('.css')?'text/css':file.endsWith('.js')?'application/javascript':file.endsWith('.svg')?'image/svg+xml':'image/png'});}
   return route.fulfill({body:'Isolated layout test target'});
  });
  const page=await context.newPage(),errors=[];page.on('pageerror',e=>errors.push(e.message));let roomTabsY=null,brandX=null;
  for(const item of pages){try{
   await page.goto('https://map.example.org/audit/'+item.name,{waitUntil:'load'});await page.waitForTimeout(100);
   const m=await page.evaluate(()=>{const box=selector=>{const e=document.querySelector(selector);if(!e)return null;const r=e.getBoundingClientRect(),s=getComputedStyle(e);return{x:r.x,y:r.y,w:r.width,h:r.height,right:r.right,bg:s.backgroundColor,color:s.color};};return {brand:box('.map-brand'),header:box('.map-topbar'),module:box('.map-module-nav a'),crumb:box('.map-breadcrumbs ol'),footer:box('.map-footer'),tabs:box('.room-tabs'),wide:box('.room-data-wide'),filter:box('[data-room-filter-details]'),filterOpen:document.querySelector('[data-room-filter-details]')?.open,overflow:document.documentElement.scrollWidth>document.documentElement.clientWidth+1,cls:(window.layoutShifts||[]).reduce((a,b)=>a+b,0),active:[...document.querySelectorAll('.room-tabs a[aria-current],.map-settings-nav a[aria-current],.map-module-nav a[aria-current]')].map(e=>{const r=e.getBoundingClientRect(),n=e.parentNode.getBoundingClientRect(),s=getComputedStyle(e);return {x:r.x,right:r.right,parentX:n.x,parentRight:n.right,bg:s.backgroundColor,color:s.color};})};});
   requireThat(!m.overflow,'Whole page overflow');
   if(brandX===null)brandX=m.brand.x;
   requireThat(near(m.brand.x,brandX),'Logo moved between pages');
   if(m.module)requireThat(near(m.module.x,brandX),'Module navigation edge moved');
   if(m.crumb)requireThat(near(m.crumb.x,brandX),'Breadcrumb edge differs');
   requireThat(near(m.header.w,m.footer.w)&&near(m.header.x,m.footer.x),'Footer shell differs');
   for(const a of m.active){requireThat(a.bg==='rgb(71, 121, 92)'&&a.color==='rgb(255, 255, 255)','Wrong active tab contrast/palette');requireThat(a.x>=a.parentX-1&&a.right<=a.parentRight+1,'Active tab outside visible rail');}
   if(item.name==='admin-stages'){const tab=page.locator('.map-module-nav a[aria-current=page]');await tab.hover();await page.waitForTimeout(250);const hover=await tab.evaluate(e=>({color:getComputedStyle(e).color,bg:getComputedStyle(e).backgroundColor}));requireThat(hover.color==='rgb(255, 255, 255)'&&hover.bg==='rgb(54, 94, 71)','Admin active hover contrast differs: '+JSON.stringify(hover));await page.mouse.move(0,0);}
   if(['bookings','calendar','calendar-week','pending','groups','booking-new'].includes(item.name)){if(roomTabsY===null)roomTabsY=m.tabs.y;requireThat(near(m.tabs.y,roomTabsY),'Room tab row moved');}
   if(m.filter){const expected=item.name==='bookings'&&width>760;requireThat(m.filterOpen===expected,'Wrong initial filter state');requireThat(m.filter.w<=1133,'Filter expanded with the table');}
   if(['bookings','calendar','calendar-week','pending'].includes(item.name)){requireThat(m.wide&&near(m.wide.x,width<=760?16:24),'Room data surface not full width');if(width>=1440)requireThat(m.wide.w>1132,'Room data surface still constrained');}
   if(['bookings','booking-new','wizard-6'].includes(item.name))requireThat(m.cls<.015,'Initial layout shifted: '+m.cls);
   if(item.name==='calendar'){const heights=await page.locator('.room-calendar-nav>a').evaluateAll(links=>links.map(e=>e.getBoundingClientRect().height));requireThat(heights.every(h=>near(h,44)),'Calendar controls differ in height');}
   if(item.name==='event-mail-edit'){const back=page.getByRole('link',{name:'Alle Vorlagen',exact:true});requireThat(near((await back.boundingBox()).height,44),'Return action wraps');}
   if(['bookings','calendar','booking-new','event-settings','sso','wizard-2'].includes(item.name)){
    const filter=page.locator('[data-room-filter-details]');if(await filter.count()&&!await filter.evaluate(e=>e.open))await filter.locator(':scope>summary').click();
    const trigger=page.locator('.map-date-open').first();if(await trigger.count()&&await trigger.isVisible()){await trigger.click();const popup=page.locator('.map-calendar:visible').first();const b=await popup.boundingBox();requireThat(b&&b.x>=0&&b.y>=0&&b.x+b.width<=width+1&&b.y+b.height<=901,'Date popup outside viewport');await popup.getByRole('button',{name:'Nächster Monat',exact:true}).click();requireThat(await popup.isVisible(),'Month navigation closed picker');await page.keyboard.press('Escape');requireThat(!await popup.isVisible(),'Escape did not close picker');}
   }
   results.push({name:item.name,theme,width,cls:m.cls,ok:true});
  }catch(error){failures.push({name:item.name,theme,width,error:error.message});}}
  if(errors.length)failures.push({theme,width,pageErrors:errors});await context.close();console.log(theme+' '+width+': layout regressions checked');
 }
 fs.writeFileSync(path.join(fixtures,'layout-results-'+(process.env.MAP_BROWSER_TYPE||'chromium')+'.json'),JSON.stringify({checks:results.length+failures.length,passed:results.length,failures},null,2));
 if(failures.length)throw Error(JSON.stringify(failures,null,2));console.log(results.length+' geometry and interaction regression checks passed.');
}finally{await browser.close();}})().catch(e=>{console.error(e);process.exit(1)});
