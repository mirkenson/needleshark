import test from 'node:test';
import assert from 'node:assert/strict';
import vm from 'node:vm';
import fs from 'node:fs';
const source = fs.readFileSync(new URL('../dist/vk-pixel.js', import.meta.url), 'utf8');
function setup(host='needle-shark.ru', existing=false) {
  const scripts=[];
  const context=vm.createContext({window:{}, URL, Date,
    location:{hostname:host,protocol:'https:',href:`https://${host}/catalog/?email=private@example.test#secret`},
    document:{referrer:'https://example.test/path?contact=secret', getElementById:()=>existing,
      createElement:()=>({}),head:{appendChild:s=>scripts.push(s)}}});
  return {context,scripts,run:()=>vm.runInContext(source,context)};
}
test('queues only one page view and removes query and fragment',()=>{
 const t=setup();t.run();t.run();const q=t.context.window._tmr;
 assert.equal(q.length,1);assert.equal(q[0].id,'3766157');assert.equal(q[0].url,'https://needle-shark.ru/catalog/');
 assert.equal(q[0].referrer,'https://example.test/path');assert.equal(q[0].type,'pageView');
 assert.equal(q[0].userid,undefined);assert.equal(q[0].params,undefined);assert.equal(t.scripts.length,1);
});
test('does not track previews',()=>{const t=setup('localhost');t.run();assert.equal(t.context.window._tmr,undefined);assert.equal(t.scripts.length,0);});
test('does not load a second copy of the SDK',()=>{const t=setup('needle-shark.ru',true);t.run();assert.equal(t.scripts.length,0);assert.equal(t.context.window._tmr.length,1);});
