const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const vm=require('node:vm');

const source=fs.readFileSync(path.join(__dirname,'../../src/benchmark_board/web/app.js'),'utf8');
const start=source.indexOf('function selectMetric(chosen){');
const end=source.indexOf("$('#metric').onchange",start);
const selectMetric=source.slice(start,end);

function page(problem){
  let renders=0,navigation=null;
  const metric={value:'baseline_speedup'};
  const location={href:'http://127.0.0.1/?'+(problem?'problem='+problem:'')};
  location.assign=url=>{navigation=url;};
  const window={history:{replaceState(_state,_title,url){location.href=String(url);}}};
  const context=vm.createContext({focusProblem:problem,location,window,URL,history:[],
    mainMetric:metric.value,selection:null,$:()=>metric,render(){renders++;}});
  vm.runInContext(selectMetric,context);
  return {context,metric,location,get renders(){return renders;},get navigation(){return navigation;},
    choose:value=>vm.runInContext(`selectMetric(${JSON.stringify(value)})`,context)};
}

test('P3 Cache metric renders inline despite the detail-history variable',()=>{
  const view=page('P3');
  view.choose('cache_gain');
  assert.equal(view.metric.value,'cache_gain');
  assert.equal(view.renders,1);
  assert.equal(new URL(view.location.href).searchParams.get('metric'),'cache_gain');
  view.choose('baseline_speedup');
  assert.equal(view.renders,2);
  assert.equal(new URL(view.location.href).searchParams.get('metric'),null);
});

test('overview Cache choice opens the focused P3 table',()=>{
  const view=page(null);
  view.choose('cache_gain');
  assert.equal(view.navigation,'/?problem=P3&metric=cache_gain');
  assert.equal(view.renders,0);
});
