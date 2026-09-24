// Exercise production inspector request ordering and focus/scroll restoration.
const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const vm=require('node:vm');
const source=fs.readFileSync(path.join(__dirname,'../../src/benchmark_board/web/app.js'),'utf8');
const detail=source.slice(source.indexOf('async function detail('),source.indexOf('\nfunction pair('));
function harness(){
  const pending=[],cells=[1,2].map(i=>({dataset:{p:'P1',case:'00'+i,k:'2'},focus(){document.activeElement=this;},getBoundingClientRect(){return {right:i===1?400:1100};}}));
  const document={activeElement:null,documentElement:{clientWidth:1414},querySelectorAll:()=>cells};
  let close,html='',renders=0;
  const classes=new Set();
  const panel={hidden:true,scrollTop:0,contains:e=>e===close,querySelectorAll:()=>[close],
    getBoundingClientRect:()=>({width:440}),classList:{toggle(name,on){if(on)classes.add(name);else classes.delete(name);}},
    set innerHTML(value){html=value;this.scrollTop=0;close={id:'close-detail',getAttribute(){return null;},focus(){document.activeElement=this;}};},get innerHTML(){return html;}};
  const context=vm.createContext({document,URLSearchParams,location:{pathname:'/',search:'?problem=P1'},window:{history:{replaceState(){}}},
    $:s=>s==='#detail'?panel:s==='#close-detail'?close:s==='#metric'?{value:'baseline_speedup'}:{},
    esc:String,metrics:()=>({}),render(){renders++;},
    fetch:()=>new Promise(resolve=>pending.push(resolve))});
  vm.runInContext('let selection=null,detailRequest=0,history=[],data={cells:[]};'+detail,context);
  return {panel,document,cells,pending,get html(){return html;},get renders(){return renders;},get close(){return close;},get dockLeft(){return classes.has('dock-left');},
    select:n=>vm.runInContext(`selection={problem:'P1',case_id:'00${n}',cores:2}`,context),
    request:update=>vm.runInContext(`detail(${update})`,context),
    resolve:n=>pending[n]({ok:true,json:async()=>({records:[],total:0})})};
}
test('out of order cell responses cannot replace the newest selection',async()=>{
  const h=harness();h.select(1);const a=h.request(true);h.select(2);const b=h.request(true);
  h.resolve(1);await b;h.resolve(0);await a;
  assert.match(h.html,/算例 002/);assert.doesNotMatch(h.html,/算例 001/);assert.equal(h.renders,1);
});
test('closing an inspector invalidates an in flight update and restores the cell focus',async()=>{
  const h=harness();h.select(1);const a=h.request(true);h.resolve(0);await a;
  const update=h.request(false);h.close.onclick();h.resolve(1);await update;
  assert.equal(h.panel.hidden,true);assert.equal(h.document.activeElement,h.cells[0]);
});
test('background detail refresh preserves its scroll and focused close button',async()=>{
  const h=harness();h.select(1);const a=h.request(true);h.resolve(0);await a;
  h.panel.scrollTop=317;h.close.focus();const update=h.request(false);h.resolve(1);await update;
  assert.equal(h.panel.scrollTop,317);assert.equal(h.document.activeElement,h.close);
});
test('inspector moves away from the selected cell without changing selection',async()=>{
  const h=harness();h.select(2);let request=h.request(true);h.resolve(0);await request;
  assert.equal(h.dockLeft,true);
  h.select(1);request=h.request(true);h.resolve(1);await request;
  assert.equal(h.dockLeft,false);
});
