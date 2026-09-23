const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const {matches} = require('../dist/catalog-search.js');
const html = fs.readFileSync('dist/catalog/index.html', 'utf8');
const cards = [...html.matchAll(/<article class="catalog-card" data-category="([^"]+)" data-search="([^"]+)"[^>]*>[\s\S]*?<h2><a href="([^"]+)"/g)].map(([,category, text,url])=>({category,text,url}));
const find = query => cards.filter(card=>matches(card.text,query)).map(card=>card.url);
test('all 26 products remain discoverable with an empty query',()=>assert.equal(find('').length,26));
test('ordinary hyphen and Unicode dash find the same wheel size',()=>{
  assert.deepEqual(find('R17-R22'),['/catalog/chehly-dlya-koles/']);
  assert.deepEqual(find('r17–r22'),find('R17-R22'));
});
test('colloquial product names and ё/e spelling are searchable',()=>{
  assert.ok(find('липучка').includes('/catalog/lenta-kontaktnaya/'));
  assert.ok(find('чехлы колес').includes('/catalog/chehly-dlya-koles/'));
});
test('size and name combine; unknown words give no results',()=>{
  assert.deepEqual(find('баул 237'),['/catalog/sumki-bauly/']);
  assert.deepEqual(find('несуществующийтовар'),[]);
});
