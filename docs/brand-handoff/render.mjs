// Print the embedded local fonts and original SVG with Chromium.
// Usage: node render.mjs /absolute/path/to/playwright
import { createRequire } from 'node:module';
import { fileURLToPath, pathToFileURL } from 'node:url';
import path from 'node:path';
import fs from 'node:fs/promises';
const require = createRequire(import.meta.url);
const { chromium } = require(process.argv[2] || 'playwright');
const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..');
const tmp = path.join(root, 'tmp/pdfs/brand-handoff');
const browser = await chromium.launch({headless:true,channel:'chrome'});
try {
  const page = await browser.newPage({viewport:{width:1000,height:1200},deviceScaleFactor:1});
  const errors=[];
  page.on('pageerror',e=>errors.push(String(e)));
  page.on('console',m=>{if(m.type()==='error')errors.push(m.text());});
  await page.goto(pathToFileURL(path.join(tmp,'guide.html')).href);
  await page.emulateMedia({media:'print'});
  await page.evaluate(()=>document.fonts.ready);
  const checks = await page.evaluate(()=>({
    images:[...document.images].map(i=>({loaded:i.complete&&i.naturalWidth>0})),
    fonts:[...document.fonts].map(f=>({family:f.family,status:f.status})),
    pages:[...document.querySelectorAll('.page')].map(p=>{
      const r=p.getBoundingClientRect(),m=p.querySelector('main').getBoundingClientRect(),f=p.querySelector('footer').getBoundingClientRect();
      return {number:Number(p.dataset.page),width:r.width,height:r.height,contentBottom:m.bottom-r.top,footerTop:f.top-r.top,clearance:f.top-m.bottom,overflow:p.scrollWidth>p.clientWidth};
    }),
    remoteResources:performance.getEntriesByType('resource').filter(r=>/^https?:/.test(r.name)).map(r=>r.name)
  }));
  if(errors.length || checks.images.some(i=>!i.loaded) || checks.pages.some(p=>p.clearance<14||p.overflow) || checks.fonts.some(f=>f.status!=='loaded')) {
    console.log(JSON.stringify({errors,...checks},null,2));
    throw new Error('Print layout or resource check failed');
  }
  await page.pdf({path:path.join(root,'output/pdf/Needle-Shark-Brand-Guide.pdf'),preferCSSPageSize:true,printBackground:true,tagged:true});
  await fs.writeFile(path.join(tmp,'layout-check.json'),JSON.stringify({errors,...checks},null,2));
  console.log(JSON.stringify({pdf:'output/pdf/Needle-Shark-Brand-Guide.pdf',pages:checks.pages.length,minimumClearance:Math.min(...checks.pages.map(p=>p.clearance)),fonts:checks.fonts,remoteResources:checks.remoteResources},null,2));
} finally {
  await browser.close();
}
