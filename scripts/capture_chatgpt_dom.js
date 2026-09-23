// Run on the intended logged-in chat page. Does not access cookies, tokens or private APIs.
(async function captureChatGPT(options = {}) {
  if (location.hostname !== 'chatgpt.com' || !/\/c\/[\w-]+/.test(location.pathname)) throw new Error('Open the intended ChatGPT conversation first.');
  const started = Date.now(), id = location.pathname.match(/\/c\/([\w-]+)/)[1];
  const root = [...document.querySelectorAll('div')].find(e => e.classList.contains('group/scroll-root'));
  if (!root) throw new Error('Unknown chat scroll container; no export produced.');
  const originalTop = root.scrollTop, records = new Map(), turns = new Map();
  const pause = ms => new Promise(resolve => setTimeout(resolve, ms));
  const active = () => !!document.querySelector('button[aria-label="Stop streaming"],button[aria-label="Stop generating"],button[aria-label="Stop answering"],[data-is-streaming="true"]');
  if (active()) throw new Error('Answer still running; export refused.');
  function collect() {
    const order = [...new Set([...document.querySelectorAll('[data-turn-id-container]')].map(e => e.getAttribute('data-turn-id-container')))];
    for (const [index, key] of order.entries()) turns.set(key, index);
    for (const el of document.querySelectorAll('[data-message-id][data-message-author-role]')) {
      const role = el.getAttribute('data-message-author-role');
      if (!['user','assistant'].includes(role)) continue;
      const section = el.closest('section[data-turn]');
      const key = el.getAttribute('data-message-id');
      const clone = el.cloneNode(true);
      clone.querySelectorAll('script,style,svg,[aria-hidden="true"],button[aria-label="Copy table"],button[aria-label="Copy"]').forEach(e => { if (!e.closest('.katex')) e.remove(); });
      const item = {id:key, role, turn_id:section?.getAttribute('data-turn-id'), html:clone.innerHTML, text:clone.textContent, attachments:[...new Set([...section?.querySelectorAll('button[aria-label]') || []].map(b=>b.getAttribute('aria-label')).filter(t=>/\.(zip|md|pdf|txt|json|png|jpg|csv|xlsx|py|tar|xz)$/i.test(t)))]};
      const old = records.get(key);
      if (!old || item.text.length >= old.text.length) records.set(key,item);
    }
  }
  let stableTop = 0, previous = '', passes = 0, timedOut = false;
  try {
    // Explicitly reach the pagination sentinel. Stable DOM alone is never proof of completeness.
    while (stableTop < 3 && Date.now()-started < 12000) {
      root.scrollTop = 0; await pause(450); collect();
      const signature = [...turns.keys()].join('|');
      stableTop = signature === previous ? stableTop+1 : 0; previous = signature;
    }
    let priorSignature = '';
    for (passes = 1; passes <= 3; passes++) {
      root.scrollTop = 0; await pause(200); collect();
      for (let y=0; y < root.scrollHeight; y += Math.max(250,root.clientHeight*0.75)) {
        root.scrollTop = y; await pause(options.stepMs || 100); collect();
        if (active()) throw new Error('Generation started during capture; retry later.');
        if (Date.now()-started > (options.maxMs || 48000)) { timedOut=true; break; }
      }
      collect();
      const signature = [...records.values()].map(x=>x.id+':'+x.text.length).sort().join('|');
      if (signature === priorSignature || timedOut) break;
      priorSignature = signature;
    }
    const messages = [...records.values()].sort((a,b)=>(turns.get(a.turn_id)??1e9)-(turns.get(b.turn_id)??1e9));
    const actualIds = new Set(messages.map(m=>m.id));
    const missing = (options.expectedIds || []).filter(x=>!actualIds.has(x));
    const data = {schema:'chatgpt-dom-capture-v1',conversation_id:id,url:location.href,title:document.title,exported_at:new Date().toISOString(),scope:'Currently selected conversation branch; user/assistant DOM content only, no hidden reasoning or attachment bytes.',verification:{status:'unverified_until_independent_inventory_comparison',timed_out:timedOut,passes,stable_top_samples:stableTop,expected_ids:options.expectedIds || [],missing_ids:missing,message_count:messages.length,streaming:active()},turn_order:[...turns.keys()],messages};
    const save = (name,text,type) => {const a=document.createElement('a');a.href=URL.createObjectURL(new Blob([text],{type}));a.download=name;a.click();setTimeout(()=>URL.revokeObjectURL(a.href),30000);};
    const stem = 'chatgpt-'+id+'-'+new Date().toISOString().replace(/[:.]/g,'-');
    save(stem+'.json',JSON.stringify(data,null,2),'application/json');
    if (options.saveScript) save('capture_chatgpt_dom.js','// Run on the intended logged-in chat page. Does not access cookies, tokens or private APIs.\n('+captureChatGPT.toString()+')({});\n','text/javascript');
    return {filename:stem+'.json',...data.verification,ids:messages.map(m=>m.id)};
  } finally {root.scrollTop=originalTop;}
})({});
