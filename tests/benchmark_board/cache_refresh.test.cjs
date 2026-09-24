// Real production functions with an in-memory HTTP/DOM harness; no ledger writes.
const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const vm=require('node:vm');
const source=fs.readFileSync(process.env.BOARD_APP_JS||path.join(__dirname,'../../src/benchmark_board/web/app.js'),'utf8');
const between=(start,end)=>source.slice(source.indexOf(start),source.indexOf(end,source.indexOf(start)));
const functions=between('async function refresh(','function visibleCase(')+between('function openCache(','function mirrorNotice(');

function harness(mode='cache_gain'){
  let next,fail=false,requests=0,mainCursor,html='',renders=0,table=null,controls=[];
  const document={activeElement:null};
  const connection={style:{}};
  const dialog={open:false,dataset:{},scrollTop:0,
    showModal(){this.open=true;},close(){this.open=false;},
    contains(el){return controls.includes(el);},
    querySelector(){return table;},querySelectorAll(){return controls;},
    get innerHTML(){return html;},
    set innerHTML(value){
      html=value;renders++;this.scrollTop=0;
      table=value.includes('cache-table-scroll')?{scrollTop:0,scrollLeft:0}:null;
      controls=[...value.matchAll(/<button id="([^"]+)"/g)].map(match=>({
        id:match[1],getAttribute(){return null;},focus(){document.activeElement=this;}
      }));
      document.activeElement=null;
    }
  };
  const context=vm.createContext({document,
    $:selector=>selector==='#cache-dialog'?dialog:selector==='#connection'?connection:controls.find(c=>'#'+c.id===selector),
    state:()=>'',options(){},sources(){},restoreView(){},visibleCase:()=>true,
    esc:String,fmt:String,render(){mainCursor=vm.runInContext('data.cursor',context);},
    fetch:async()=>{requests++;if(fail)throw Error('offline');return {ok:true,json:async()=>next};},
  });
  vm.runInContext('let data=null,lastKey="",selection=null,busy=false,refreshQueued=false;'+functions,context);
  const snapshot=(cursor,makespan=100,id='s'+cursor)=>({cursor,runtime:{snapshot_id:id},algorithms:[],runs:[],cells:[{
    problem:'P3',case_id:'001',cores:2,best:{id:'r'+cursor,eligible:true,cache_pair_verified:true,
      metrics:{makespan_cycles:makespan,cache_gain:2,cache_hit_rate:0.5}}
  }]});
  return {dialog,document,connection,snapshot,
    get table(){return table;},get html(){return html;},get renders(){return renders;},
    get requests(){return requests;},get mainCursor(){return mainCursor;},
    button:id=>controls.find(c=>c.id===id),
    next(value){next=value;},fail(){fail=true;},
    refresh:force=>vm.runInContext(`refresh(${Boolean(force)})`,context),
    open:()=>{context.requestedMode=mode;vm.runInContext('openCache(requestedMode)',context);}
  };
}

for(const mode of ['cache_gain','cache_hit_rate'])test('new snapshot updates open '+mode+' without losing position or focus',async()=>{
  const h=harness(mode);h.next(h.snapshot(1));await h.refresh();h.open();
  h.table.scrollTop=180;h.table.scrollLeft=24;h.dialog.scrollTop=12;
  h.button('cache-refresh').focus();
  h.next(h.snapshot(2,77));await h.refresh();
  assert.equal(h.mainCursor,2);assert.match(h.html,/>77<\/td>/);assert.match(h.html,/records\/r2/);
  assert.equal(h.dialog.open,true);assert.equal(h.dialog.dataset.mode,mode);
  assert.equal(h.table.scrollTop,180);assert.equal(h.table.scrollLeft,24);assert.equal(h.dialog.scrollTop,12);
  assert.equal(h.document.activeElement.id,'cache-refresh');
});

test('snapshot identity change refreshes Cache even when cursor is unchanged',async()=>{
  const h=harness();h.next(h.snapshot(1));await h.refresh();h.open();
  h.next(h.snapshot(1,66,'replacement'));await h.refresh();assert.match(h.html,/>66<\/td>/);
});

test('unchanged polling leaves the open panel untouched',async()=>{
  const h=harness();h.next(h.snapshot(1));await h.refresh();h.open();
  const before=h.renders;await h.refresh();assert.equal(h.renders,before);
});

test('background refresh does not open a closed Cache panel',async()=>{
  const h=harness();h.next(h.snapshot(1));await h.refresh();assert.equal(h.dialog.open,false);
  h.next(h.snapshot(2));await h.refresh();assert.equal(h.renders,0);
});

test('manual refresh fetches current data and retains the selected tab',async()=>{
  const h=harness('cache_hit_rate');h.next(h.snapshot(1));await h.refresh();h.open();
  h.next(h.snapshot(2,55));await h.button('cache-refresh').onclick();
  assert.equal(h.requests,2);assert.match(h.html,/>55<\/td>/);assert.equal(h.dialog.dataset.mode,'cache_hit_rate');
});

test('offline refresh retains the last visible Cache results',async()=>{
  const h=harness();h.next(h.snapshot(1));await h.refresh();h.open();
  const before=h.html;h.fail();await h.refresh();assert.equal(h.html,before);
  assert.equal(h.dialog.open,true);assert.match(h.connection.textContent,/连接中断/);
});

test('a batch picked during an older request is fetched and old results are never rendered',async()=>{
  let filter='old',resolveOld;
  const requests=[],rendered=[];
  const response=cursor=>({ok:true,json:async()=>({cursor,algorithms:[],runs:[]})});
  const context=vm.createContext({
    state:()=>filter,$:s=>s==='#connection'?{style:{}}:s==='#cache-dialog'?{open:false}:null,
    options(){},sources(){},restoreView(){},
    render(){rendered.push(vm.runInContext('data.cursor',context));},
    fetch:url=>{requests.push(url);return requests.length===1?new Promise(resolve=>{resolveOld=resolve;}):Promise.resolve(response(2));}
  });
  vm.runInContext('let data=null,lastKey="",selection=null,busy=false,refreshQueued=false;'+between('async function refresh(','function visibleCase('),context);
  const old=vm.runInContext('refresh()',context);
  filter='new';await vm.runInContext('refresh(true)',context);
  resolveOld(response(1));await old;await new Promise(resolve=>setImmediate(resolve));
  assert.deepEqual(requests,['/api/v1/cells?old','/api/v1/cells?new']);
  assert.deepEqual(rendered,[2]);
});
