'use strict';
// Callers pass the current problem, algorithm/run and visible-case subset.
function summarizeCells(cells, metric, cores) {
  const column = cells.filter(cell => cell.cores === cores);
  const values = column.map(cell => cell.best).filter(record =>
    record?.eligible &&
    (metric !== 'baseline_speedup' || record.baseline_verified) &&
    (metric !== 'cache_gain' || record.cache_pair_verified)
  ).map(record => record.metrics[metric]).filter(value =>
    typeof value === 'number' && Number.isFinite(value)
  );
  return {count: values.length, total: column.length,
    mean: values.length ? values.reduce((sum, value) => sum + value, 0) / values.length : null};
}
const $=s=>document.querySelector(s), esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
let data=null,lastKey='',selection=null,history=[],busy=false,mainMetric='baseline_speedup';
const restoreKey='benchmark-board-ui-state';
let pendingRestore=null,versionBusy=false,reloading=false;
const loadedAssets=document.querySelector('meta[name="board-assets"]')?.content;
try{
  const saved=JSON.parse(sessionStorage.getItem(restoreKey)||'null');
  if(saved?.version===1&&typeof saved.savedAt==='number'&&Date.now()-saved.savedAt<3600000){
    pendingRestore=saved;
    if([...$('#metric').options].some(o=>o.value===saved.metric)&&!['cache_gain','cache_hit_rate'].includes(saved.metric)){
      mainMetric=saved.metric;$('#metric').value=mainMetric;
    }
    $('#search').value=typeof saved.search==='string'?saved.search.slice(0,100):'';
    $('#reported').checked=saved.reported===true;
  }
}catch(_){pendingRestore=null;}
function restoreView(){
  if(!pendingRestore)return;
  const saved=pendingRestore;pendingRestore=null;sessionStorage.removeItem(restoreKey);
  if(Number.isFinite(saved.detailScroll))$('#detail').scrollTop=Math.max(0,saved.detailScroll);
  if(['cache_gain','cache_hit_rate'].includes(saved.cacheMode)){
    openCache(saved.cacheMode);
    const table=$('#cache-dialog .cache-table-scroll');if(table&&Number.isFinite(saved.cacheScroll))table.scrollTop=Math.max(0,saved.cacheScroll);
  }
  if(Number.isFinite(saved.windowScroll))window.scrollTo(0,Math.max(0,saved.windowScroll));
}
async function checkVersion(){
  if(versionBusy||reloading||!data)return;versionBusy=true;
  try{
    const response=await fetch('/api/v1/runtime');if(!response.ok)return;
    const runtime=await response.json();
    if(!/^[a-f0-9]{64}$/.test(runtime.ui_asset_id||'')||runtime.ui_asset_id===loadedAssets)return;
    const dialog=$('#cache-dialog');
    sessionStorage.setItem(restoreKey,JSON.stringify({version:1,savedAt:Date.now(),metric:mainMetric,
      algorithm:$('#algorithm').value,run:$('#run').value,search:$('#search').value,reported:$('#reported').checked,
      scrolls:[...document.querySelectorAll('.board-scroll')].map(x=>x.scrollTop),detailScroll:$('#detail').scrollTop,
      windowScroll:window.scrollY,cacheMode:dialog.open?dialog.dataset.mode:null,
      cacheScroll:$('#cache-dialog .cache-table-scroll')?.scrollTop||0}));
    reloading=true;location.reload();
  }catch(_){/* A failed version request never discards the current usable page. */}
  finally{versionBusy=false;}
}

const names={P1:'情况 A · 等待与调度',P2:'情况 B · 搬运计算重叠',P3:'情况 C · 只读 Cache'};
const statuses={ok:'成功',reported:'仅报告',failed:'失败',timeout:'超时',running:'报告运行中',not_run:'未接收',unsupported:'不支持',withdrawn:'已撤回'};
const fmt=(x,metric='makespan_cycles')=>x===null||x===undefined?'NA':metric==='cache_hit_rate'?(x*100).toFixed(1)+'%':metric.includes('speedup')||metric==='cache_gain'?x.toFixed(3):metric.includes('seconds')?x.toFixed(3):Number.isInteger(x)?x.toLocaleString('en-US'):String(x);
function metrics(){return data?.metrics||{}}
function options(id,values){const el=$(id),value=pendingRestore?(pendingRestore[id==='#algorithm'?'algorithm':'run']||''):el.value;el.innerHTML='<option value="">'+(id==='#algorithm'?'历史最优组合':'所有已接收批次')+'</option>'+values.map(v=>`<option value="${esc(v)}">${esc(v)}</option>`).join('');el.value=values.includes(value)?value:'';}
function state(){return new URLSearchParams({algorithm:pendingRestore?.algorithm||$('#algorithm').value,run:pendingRestore?.run||$('#run').value,include_reported:$('#reported').checked});}
async function refresh(force=false){if(busy)return;busy=true;try{const response=await fetch('/api/v1/cells?'+state());if(!response.ok)throw Error(response.status);const next=await response.json();data=next;$('#connection').textContent='● 本地服务在线';$('#connection').style.color='';const key=next.cursor+'|'+(next.runtime?.snapshot_id||'')+'|'+state();if(force||key!==lastKey){lastKey=key;options('#algorithm',next.algorithms);options('#run',next.runs);render();if(selection)await detail(false);}sources();restoreView();}catch(e){$('#connection').textContent='连接中断 · 保留上次数据';$('#connection').style.color='var(--fail)';}finally{busy=false;}}
function visibleCase(c){const s=$('#search').value.trim();if(!s)return true;const range=s.match(/^(\d+)\s*[-–~]\s*(\d+)$/);return range?+c>=+range[1]&&+c<=+range[2]:c.includes(s.padStart(3,'0'));}
// Stable absolute scales for ratios; relative positions never change the colors.
function mixColor(a,b,t){return a.map((v,i)=>Math.round(v+(b[i]-v)*t));}
function inkFor(rgb){const lum=rgb.map(v=>{v/=255;return v<=.04045?v/12.92:((v+.055)/1.055)**2.4;}).reduce((s,v,i)=>s+v*[.2126,.7152,.0722][i],0);return lum>.179?'#000000':'#ffffff';}
function absoluteColor(value,metric,low,high){
  const palette=[[45,54,77],[47,87,144],[29,145,147],[119,199,137],[239,226,132]];
  let t;
  if(metric==='baseline_speedup'||metric==='cache_gain'){
    if(value<1)return mixColor([192,87,39],palette[0],Math.max(0,Math.min(1,1+Math.log2(Math.max(value,.000001)))));
    t=Math.log2(value)/3;
  }else if(metric==='cache_hit_rate'){t=value;}
  else {t=high===low?.5:(Math.log1p(value)-Math.log1p(low))/(Math.log1p(high)-Math.log1p(low));if(!metrics()[metric]?.[2])t=1-t;}
  t=Math.max(0,Math.min(1,t));const x=t*(palette.length-1),i=Math.min(palette.length-2,Math.floor(x));return mixColor(palette[i],palette[i+1],x-i);
}
function relativePosition(value,values){if(values.length<2)return null;const less=values.filter(x=>x<value).length,equal=values.filter(x=>x===value).length;return (less+(equal-1)/2)/(values.length-1);}
function render(){if(!data)return;const metric=$('#metric').value;const values=data.cells.filter(c=>c.best&&c.best.eligible).map(c=>c.best.metrics[metric]).filter(x=>x!==null&&x!==undefined);const low=values.length?Math.min(...values):null,high=values.length?Math.max(...values):null;
const ratio=metric==='baseline_speedup'||metric==='cache_gain';
$('#metric-label').textContent=(metrics()[metric]?.[0]||metric)+' / '+(metrics()[metric]?.[1]||'');
const ticks=ratio?[.5,1,2,4,8]:metric==='cache_hit_rate'?[0,.25,.5,.75,1]:[low,low===null?null:Math.expm1((Math.log1p(low)+Math.log1p(high))/2),high];
$('#scale-ticks').innerHTML=ticks.filter(x=>x!==null).map((v,i)=>{const rgb=absoluteColor(v,metric,low,high);return `<span class="scale-tick"><i style="background:rgb(${rgb});border-color:${inkFor(rgb)}33"></i>${esc(ratio?(i===0?'≤0.5×':i===4?'≥8×':v+'×'):fmt(Number(v.toFixed(3)),metric))}</span>`;}).join('');
$('#scale-note').textContent=ratio?'固定对数色阶 · 1× 为基准，暖色低于基准；等色距表示倍数变化':metric==='cache_hit_rate'?'固定 0–100% 色阶':'当前全表范围的对数色阶 · 跨图规模不同，颜色不表示算法优劣';
const groups=new Map();for(const c of data.cells){const v=c.best?.metrics[metric];if(c.best?.eligible&&Number.isFinite(v)&&visibleCase(c.case_id)){const key=c.problem+'-'+c.cores;if(!groups.has(key))groups.set(key,[]);groups.get(key).push(v);}}
const cellStyle=v=>{const rgb=absoluteColor(v,metric,low,high);return `background:rgb(${rgb});color:${inkFor(rgb)}`;};
const scrolls=Array.isArray(pendingRestore?.scrolls)?pendingRestore.scrolls:[...document.querySelectorAll('.board-scroll')].map(x=>x.scrollTop);
$('#boards').innerHTML=['P1','P2','P3'].map((p,index)=>{const cells=data.cells.filter(c=>c.problem===p),map=new Map(cells.map(c=>[c.case_id+'-'+c.cores,c]));const valid=cells.filter(c=>c.best?.eligible).length;return `<section class="board"><div class="board-title"><div><strong>${p}</strong><small>${names[p]} · ${valid}/500 已入榜</small></div>${p==='P3'?`<button id="cache-view">Cache 对照 · ${cells.filter(c=>visibleCase(c.case_id)&&c.best?.eligible&&c.best.cache_pair_verified).length} 已配对</button>`:''}</div><div class="board-scroll"><table><thead><tr><th>算例</th>${[1,2,3,4,5].map(k=>`<th>${k} 核</th>`).join('')}</tr><tr class="averages"><th scope="row">均值</th>${[1,2,3,4,5].map(k=>{const a=summarizeCells(cells.filter(c=>visibleCase(c.case_id)),metric,k);return `<th title="${esc(metrics()[metric][0])}：当前筛选的逐例算术平均；${a.count}/${a.total} 个有效样本"><b>${esc(fmt(a.mean===null?null:Number(a.mean.toFixed(3)),metric))}</b><small>${a.count}/${a.total}</small></th>`;}).join('')}</tr></thead><tbody>${Array.from({length:100},(_,i)=>String(i+1).padStart(3,'0')).filter(visibleCase).map(c=>`<tr><th>${c}</th>${[1,2,3,4,5].map(k=>{const cell=map.get(c+'-'+k),r=cell.best,v=r?.metrics[metric],distribution=groups.get(p+'-'+k)||[],rank=r?.eligible&&Number.isFinite(v)?relativePosition(v,distribution):null,selected=selection&&selection.problem===p&&selection.case_id===c&&selection.cores===k;let text=r?fmt(v,metric):cell.status==='failed'?'失败 !':cell.status==='timeout'?'超时 !':cell.status==='running'?'运行中':cell.status==='reported'?(cell.missing_artifacts?.length?'缺原件':'待核验'):cell.attempts?'待核验':'—';const tip=r?`${p} / ${c} / ${k}核\n${r.algorithm_name}\n${metrics()[metric][0]}: ${fmt(v,metric)}\n${r.eligible?'原件一致':'仅报告 · 不入正式榜'}${rank===null?'':`\n同题同核数值分位: ${Math.round(rank*100)}%（${distribution.length} 个样本；细条越长数值越大，不表示绝对差值）`}\n点击查看 ${cell.attempts} 次尝试及历史`:`${p} / ${c} / ${k}核：${statuses[cell.status]||cell.status}，${cell.attempts} 次尝试${cell.missing_artifacts?.length?'；缺少 '+cell.missing_artifacts.join('/')+' 原件':''}`;return `<td><button class="cell ${r?'measured ':''}${r&&!r.eligible?'reported ':''}${cell.status} ${selected?'selected':''}" style="${r?.eligible&&Number.isFinite(v)?cellStyle(v):''}" data-p="${p}" data-case="${c}" data-k="${k}" title="${esc(tip)}" aria-label="${esc(tip)}">${esc(text)}${rank===null?'':`<i class="relative-bar" aria-hidden="true" style="width:${(rank*92).toFixed(2)}%"></i>`}</button></td>`;}).join('')}</tr>`).join('')}</tbody></table></div></section>`;}).join('');
[...document.querySelectorAll('.board-scroll')].forEach((e,i)=>e.scrollTop=Number.isFinite(scrolls[i])?Math.max(0,scrolls[i]):0);
$('#cache-view')?.addEventListener('click',()=>openCache('cache_gain'));
const valid=data.cells.filter(c=>c.best?.eligible).length,attempts=data.cells.filter(c=>c.attempts).length;$('#counts').innerHTML=`<div><b>${valid}<small> / 1500</small></b><span>${data.runtime?.mode==='central_mirror'?'中央已核的有效格':'有原件的有效格'}</span></div><div><b>${attempts}</b><span>已有记录的格</span></div><div><b>${data.record_count}</b><span>历史记录</span></div>`;
}
function openCache(mode='cache_gain'){
  if(!data)return;
  const cells=data.cells.filter(c=>c.problem==='P3'&&visibleCase(c.case_id));
  const valid=cells.filter(c=>c.best?.eligible),paired=valid.filter(c=>c.best.cache_pair_verified&&Number.isFinite(c.best.metrics.cache_gain));
  const hits=mode==='cache_hit_rate',rows=hits?valid.filter(c=>Number.isFinite(c.best.metrics.cache_hit_rate)):paired;
  const dialog=$('#cache-dialog');dialog.dataset.mode=mode;
  dialog.innerHTML=`<div class="cache-heading"><div><h2 id="cache-title">P3 · ${hits?'Cache 字节命中率':'同方案 Cache 对照'}</h2><p>当前算法、批次及算例筛选 · ${rows.length}/${cells.length} 格可展示</p></div><button id="cache-close" autofocus>返回成绩表 ×</button></div><div class="cache-tabs"><button id="cache-pairs" aria-pressed="${!hits}">同方案加速对照 · ${paired.length}</button><button id="cache-hits" aria-pressed="${hits}">字节命中率</button><button id="cache-refresh">刷新对照</button></div><p class="cache-explanation">${hits?'命中率来自P3官方结果，按字节计算；它不等于开启Cache后的加速比。':`加速比 = 同计划、同核数的无 Cache 周期 ÷ 有 Cache 周期。当前 ${valid.length-paired.length} 个已核方案尚缺这组配对；P3 成绩有效，但不能据此计算 Cache 收益。这里只列已核配对，主表指标保持不变。`}</p>${rows.length?`<div class="cache-table-scroll"><table><thead><tr><th>算例</th><th>核数</th>${hits?'':'<th>无 Cache 周期</th>'}<th>有 Cache 周期</th>${hits?'':'<th>加速比</th>'}<th>字节命中率</th><th>来源</th></tr></thead><tbody>${rows.map(c=>{const r=c.best,m=r.metrics;return `<tr><th>${c.case_id}</th><td>${c.cores}</td>${hits?'':`<td>${fmt(Number((m.makespan_cycles*m.cache_gain).toFixed(6)))}</td>`}<td>${fmt(m.makespan_cycles)}</td>${hits?'':`<td>${fmt(m.cache_gain,'cache_gain')}×</td>`}<td>${fmt(m.cache_hit_rate,'cache_hit_rate')}</td><td><a href="/api/v1/records/${esc(r.id)}" target="_blank">原件 ↗</a></td></tr>`;}).join('')}</tbody></table></div>`:'<div class="cache-empty">当前筛选没有可展示的配对数据。可以查看字节命中率，或返回成绩表；已有官方成绩不会因此失效。</div>'}`;
  $('#cache-close').onclick=()=>dialog.close();$('#cache-pairs').onclick=()=>openCache('cache_gain');$('#cache-hits').onclick=()=>openCache('cache_hit_rate');$('#cache-refresh').onclick=()=>openCache(mode);
  if(!dialog.open)dialog.showModal();
}
function mirrorNotice(){
  const runtime=data.runtime,banner=$('#mode-banner');
  const mirrored=runtime?.mode==='central_mirror';
  if(!mirrored&&!runtime?.sync){banner.hidden=true;return;}
  const sync=runtime.sync,error=runtime.error||sync?.error?.message;
  const names={starting:'正在启动',syncing:'同步中',online:'同步在线',offline:'连接中断',error:'同步异常'};
  const upload=sync?.upload;
  banner.hidden=false;banner.classList.toggle('warning',Boolean(error));
  banner.textContent=(mirrored?'中央已核成绩 · 本机只读镜像。原件已由中央核对，本机未重新核验。快照 '+new Date(runtime.generated_at).toLocaleString('zh-CN')+'（本地时间）':'中央成绩库 · 自动同步')+
    (sync?' · '+(names[sync.state]||'同步状态待确认')+(sync.last_success_at?' · 最近同步成功 '+new Date(sync.last_success_at).toLocaleString('zh-CN'):''):'')+
    (upload?' · 本机提交：待上传 '+(upload.queued??0)+'，待回执 '+(upload.awaiting_receipt??0)+'，已接收 '+(upload.accepted??0)+'，被拒 '+(upload.rejected??0):'')+
    (error?' · 更新失败，保留上次已核快照：'+error:'');
  if(mirrored)$('#polling-note').textContent='页面每 5 秒读取本机已接收的中央快照；独立同步程序负责传输。快照保留全部历史、筛选和来源；原件通过固定 Git 链接按需读取。中央已核不代表本机逐原件复核，也不代表重新运行评估器。';
}
function originalLinks(r){
  const mirrored=data.runtime?.mode==='central_mirror',source=r.source||{};
  return Object.entries(r.artifacts||{}).map(([name,a])=>{
    if(!mirrored)return `<a href="/api/v1/blobs/${esc(a.sha256)}" download>${esc(name)} ↓</a>`;
    const repo=source.repo,commit=source.commit,path=a.path;
    if(!/^[A-Za-z0-9_.-]+\/[A-Za-z0-9_.-]+$/.test(repo||'')||!/^([a-f0-9]{40})$/.test(commit||'')||typeof path!=='string'||path.split('/').includes('..'))return '';
    return `<a target="_blank" rel="noreferrer" href="https://github.com/${esc(repo)}/blob/${commit}/${path.split('/').map(encodeURIComponent).join('/')}">${esc(name)} 原件 ↗</a>`;
  }).join('');
}
function sources(){mirrorNotice();const rows=Object.entries(data.sources);$('#sources').innerHTML=rows.map(([id,s])=>`<div><b>${esc(id)}</b> · ${esc(s.status)}<br>${esc(s.message||'')}<br>检查 ${esc(s.checked_at)}<br><code>${esc((s.commit||'').slice(0,12))}</code></div>`).join('');$('#source-summary').textContent=rows.map(([n,s])=>n+': '+(s.status==='waiting_feed'?'待数据包':s.status==='ok'?'已同步':'接收异常')).join(' · ');$('#freshness').textContent='网页同步 '+new Date().toLocaleTimeString('zh-CN')+'\n最近接收 '+(data.latest_imported_at||'未知')+' · 原运行时间 '+(data.latest_observed_at||'未记录');}
async function detail(updateURL=true){if(!selection)return;const s=selection,q=new URLSearchParams(s);const response=await fetch('/api/v1/records?'+q+'&limit=500');const result=await response.json();history=result.records.slice().reverse();const cell=data.cells.find(c=>c.problem===s.problem&&c.case_id===s.case_id&&c.cores===s.cores),r=cell?.best;const metric=$('#metric').value;$('#detail').hidden=false;
const link=(url,label)=>typeof url==='string'&&/^https:\/\/github\.com\//.test(url)?`<a href="${esc(url)}" target="_blank" rel="noreferrer">${label} ↗</a>`:esc(label);
const info=r?`<div class="hero">${esc(fmt(r.metrics[metric],metric))}</div><p>${esc(metrics()[metric][0])} · ${esc(metrics()[metric][1])}</p><span class="badge">${r.eligible?(data.runtime?.mode==='central_mirror'?'中央原件已核 · 本机只读镜像':'固定原件一致 · 未新增复跑'):'仅报告 · 暂不进入正式最优榜'}</span><dl class="info"><dt>算法</dt><dd>${esc(r.algorithm_name)}<br><code>${esc(r.algorithm_id)}</code></dd><dt>策略</dt><dd>${esc(r.variant||'未登记')}</dd><dt>版本</dt><dd>${link(`https://github.com/huaweibei123/huaweicup2026/commit/${r.solver_commit}`,(r.solver_commit||'未知').slice(0,12))}</dd><dt>批次</dt><dd>${esc(r.run_id)}</dd><dt>求解时间</dt><dd>${fmt(r.metrics.solver_wall_seconds,'solver_wall_seconds')} 秒</dd><dt>评价源</dt><dd>${esc(r.evaluator?.route)} · ${esc(r.evaluator?.entrypoint)}</dd><dt>来源接收</dt><dd>${esc(r.imported_at)}</dd><dt>运行时间</dt><dd>${esc(r.observed_at||'未知；不以接收时间代替')}</dd></dl><ul>${r.admission_notes.map(x=>`<li>${esc(x)}</li>`).join('')}</ul>${pair(r)}<div class="download"><a target="_blank" href="/api/v1/records/${r.id}">完整来源 JSON ↗</a>${link(r.source.url,'Git 固定原件')}${originalLinks(r)}</div><details><summary>参数与运行环境</summary><pre>${esc(JSON.stringify({parameters:r.parameters,runtime:r.runtime_id,timing:r.timing,identity:r.identity,provenance:r.provenance},null,2))}</pre></details>`:`<p class="hero">暂无入榜方案</p><p>已有 ${history.length} 条记录。失败或证据不足不会补成有效成绩。</p>${cell?.missing_artifacts?.length?`<p>已收到报告，缺少原件：${cell.missing_artifacts.map(x=>({plan:"方案 plan",result:"评估结果 result",run:"运行收据 run"}[x])).join("、")}。可勾选“预览仅报告数据”查看报告值。</p>`:""}`;
$('#detail').innerHTML=`<button class="close" id="close-detail" aria-label="关闭详情">×</button><h3>${s.problem} · 算例 ${s.case_id}</h3><p>${s.cores} 核 · 当前 Makespan 最优</p>${info}<h4>全部历史 · ${result.total} 条${result.total>500?'（当前显示 500 条，完整记录见 API 分页）':''}</h4>${history.map(h=>`<div class="history"><b>${esc(fmt(h.metrics.makespan_cycles))}</b> 周期 <span class="badge">${esc(statuses[h.status])} / ${h.eligible?(data.runtime?.mode==='central_mirror'?'中央已核':'原件一致'):'不入榜'}</span><p>${esc(h.algorithm_name)} · ${esc(h.variant||'')} · r${h.revision}</p><p>${esc(h.run_id)}<br>${esc(h.imported_at)}</p><p>${esc(h.admission_notes.join('；'))}</p><a target="_blank" href="/api/v1/records/${h.id}">来源与完整记录 ↗</a></div>`).join('')}`;
$('#close-detail').onclick=()=>{selection=null;$('#detail').hidden=true;window.history.replaceState(null,'',location.pathname+location.search);render();};if(updateURL)window.history.replaceState(null,'','#'+q.toString());render();
}
function pair(r){if(r.problem!=='P3')return '';if(!r.cache_pair_verified)return '<h4>Cache 收益</h4><p>缺少同计划、同核数配对原件，暂不计算收益。</p>';let withCache=r.metrics.makespan_cycles,noCache=withCache*r.metrics.cache_gain,max=Math.max(withCache,noCache);return `<h4>同计划 Cache 对照 · ${fmt(r.metrics.cache_gain,'cache_gain')}×</h4><div class="pair"><span>无 Cache</span><i style="width:${130*noCache/max}px"></i><em>${fmt(noCache)}</em></div><div class="pair"><span>有 Cache</span><i style="width:${130*withCache/max}px"></i><em>${fmt(withCache)}</em></div>`;}
$('#boards').addEventListener('click',e=>{const b=e.target.closest('[data-case]');if(b){selection={problem:b.dataset.p,case_id:b.dataset.case,cores:+b.dataset.k};detail();}});
for(const id of ['#algorithm','#run','#reported'])$(id).addEventListener('change',()=>refresh(true));$('#metric').onchange=()=>{const chosen=$('#metric').value;if(chosen==='cache_gain'||chosen==='cache_hit_rate'){$('#metric').value=mainMetric;openCache(chosen);return;}mainMetric=chosen;render();if(selection)detail(false);};$('#search').oninput=render;$('#refresh').onclick=()=>refresh(true);$('#theme').onclick=()=>{document.body.classList.toggle('light');localStorage.setItem('board-theme',document.body.classList.contains('light')?'light':'dark');};if(localStorage.getItem('board-theme')==='light')document.body.classList.add('light');
document.addEventListener('keydown',e=>{if(e.key==='Escape'&&selection&&!$('#cache-dialog').open)$('#close-detail')?.click();});
const hash=new URLSearchParams(location.hash.slice(1));if(['P1','P2','P3'].includes(hash.get('problem'))&&/^\d{3}$/.test(hash.get('case_id')||'')&&+hash.get('cores')>=1&&+hash.get('cores')<=5)selection={problem:hash.get('problem'),case_id:hash.get('case_id'),cores:+hash.get('cores')};
refresh(true);setInterval(()=>{refresh();checkVersion();},5000);
