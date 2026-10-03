import test from 'node:test';
import assert from 'node:assert/strict';
import React from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { ApplyReportLedger } from '../src/pages/apply/ApplyReportLedger.tsx';
import { Ledger } from '../src/pages/preview/Ledger.tsx';
import { api } from '../src/api.ts';
import { directoryListing } from '../src/lib/directoryCache.ts';

test('10,000 outcome records render only 50 ledger rows', () => {
  const items = Array.from({length: 10000}, (_, i) => ({ item_id: String(i), source_name: `${i}.pdf`, target_name: `new-${i}.pdf`, status: 'renamed', reason: null }));
  const start = performance.now();
  const html = renderToStaticMarkup(React.createElement(ApplyReportLedger, {items}));
  assert.equal((html.match(/class="result-row"/g) ?? []).length, 50);
  assert.match(html, /of 10000/);
  console.log(`10,000-item report: ${Math.round(performance.now()-start)} ms; 50 rows; ${html.length} HTML bytes`);
});
test('preview page retains off-page selection and exposes full result count', () => {
  const items = Array.from({length: 50}, (_, i) => ({id: String(i),current_name: `${i}.pdf`,proposed_name: `new-${i}.pdf`,status:'ready'}));
  const noop = () => {};
  const html = renderToStaticMarkup(React.createElement(Ledger, {visibleItems:items,selected:new Set(['0','9999']),activeId:'0',query:'',error:'',allVisibleSelected:false,selectableCount:50,page:0,totalItems:10000,onPageChange:noop,onQueryChange:noop,onToggle:noop,onSelectVisible:noop,onClear:noop,onActivate:noop,onDismissError:noop}));
  assert.equal((html.match(/role="option"/g) ?? []).length,50);
  assert.match(html,/aria-setsize="10000"/);
  assert.equal((html.match(/aria-selected="true"/g) ?? []).length,1);
});
test('API requests lightweight plan, item detail and shallow directory counts', async () => {
  const urls=[];
  globalThis.window={ location:{origin:'http://localhost'},fetch:async (url)=>{urls.push(url);return {ok:true,json:async()=>({})};} };
  await api.plan('p'); await api.item('p','i'); await api.filesystem('/folder');
  assert.deepEqual(urls,['/api/v1/plans/p?include_metadata=false','/api/v1/plans/p/items/i','/api/v1/filesystem?path=%2Ffolder&include_counts=false']);
});
test('directory cache reuses recent entries, refreshes and evicts at 20 entries', async () => {
  let calls=0;
  api.filesystem=async path=>{calls++;return {path,parent:null,entries:[],pdf_count:calls};};
  assert.equal((await directoryListing('/cached')).pdf_count,1);
  assert.equal((await directoryListing('/cached')).pdf_count,1);
  assert.equal((await directoryListing('/cached',true)).pdf_count,2);
  for(let i=0;i<20;i++) await directoryListing(`/other${i}`);
  await directoryListing('/cached'); assert.equal(calls,23);
});

test('older directory response cannot overwrite an explicit refresh', async () => {
  let resolveOld;
  api.filesystem=()=>new Promise(resolve=>{resolveOld=resolve;});
  const old=directoryListing('/racing');
  api.filesystem=async path=>({path,parent:null,entries:[],pdf_count:22});
  await directoryListing('/racing',true);
  resolveOld({path:'/racing',parent:null,entries:[],pdf_count:1});
  await old;
  assert.equal((await directoryListing('/racing')).pdf_count,22);
});

test('directory cache hits refresh LRU recency without extending lifetime', async () => {
  let calls=0;
  api.filesystem=async path=>({path,parent:null,entries:[],pdf_count:++calls});
  for(let i=0;i<20;i++) await directoryListing(`/lru-${i}`);
  await directoryListing('/lru-0');
  await directoryListing('/lru-20');
  assert.equal((await directoryListing('/lru-0')).pdf_count,1);
  assert.equal(calls,21);
  await directoryListing('/lru-1');
  assert.equal(calls,22);
});
