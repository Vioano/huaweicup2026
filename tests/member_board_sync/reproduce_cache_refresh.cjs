// Unit-level exercise of the exact refresh function; no real DOM/network/data writes.
const fs=require('node:fs'), vm=require('node:vm'), crypto=require('node:crypto'), path=require('node:path');
if(!process.argv[2])throw Error('Pass the reviewed app.js path');
const source=fs.readFileSync(process.argv[2],'utf8');
if(crypto.createHash('sha256').update(source).digest('hex')!=='723f2f980eb3c1131072343fc1d85f89b5c169d65dab40d78c6f7673637a05c9')throw Error('Pinned source changed');
const begin=source.indexOf('async function refresh('), end=source.indexOf('function visibleCase(',begin);
if(begin<0||end<begin)throw Error('Function boundaries differ');
const refresh=source.slice(begin,end);
const setup=`
let data={cursor:1}, lastKey='', selection=null, busy=false;
let mainRenderedCursor=1, cacheRenderedCursor=1;
const dialog={open:true,dataset:{mode:'cache_gain'}};
const connection={textContent:'',style:{}};
const document={querySelector:s=>s==='#cache-dialog'?dialog:null};
const $=s=>s==='#cache-dialog'?dialog:connection;
const state=()=>'';
function options(){}
function render(){mainRenderedCursor=data.cursor;}
function openCache(){cacheRenderedCursor=data.cursor;}
function sources(){}
function restoreView(){}
async function fetch(){return {ok:true,json:async()=>({cursor:2,runtime:{snapshot_id:'new'},algorithms:[],runs:[]})};}
`;
vm.runInNewContext(setup+refresh+`\nrefresh().then(()=>({
  received_cursor:data.cursor,main_rendered_cursor:mainRenderedCursor,
  open_cache_rendered_cursor:cacheRenderedCursor,cache_dialog_open:dialog.open
}))`).then(result=>{
  console.log(JSON.stringify({source_sha256:crypto.createHash('sha256').update(source).digest('hex'),
    scope:'Unit function with mocked HTTP/DOM; not measured browser/network latency',...result},null,2));
  if(result.received_cursor!==2||result.main_rendered_cursor!==2||result.open_cache_rendered_cursor!==1)
    throw Error('Pinned stale Cache-panel counterexample no longer reproduces');
});
