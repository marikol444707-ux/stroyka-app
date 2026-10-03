"""Owner-facing, token-protected data viewer shell for Jev QA runs."""

VIEWER_HTML = r"""<!doctype html>
<html lang="ru">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Jev Live · Stroyka Dev Control</title>
<style>
:root{color-scheme:dark;font-family:Inter,ui-sans-serif,system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;background:#0b0d10;color:#f4f6f8}*{box-sizing:border-box}body{margin:0;min-height:100vh;background:radial-gradient(circle at 20% 0,#19202a 0,#0b0d10 38%);color:#f4f6f8}button,input{font:inherit}.shell{max-width:1500px;margin:auto;padding:24px}.top{display:flex;gap:16px;align-items:center;justify-content:space-between;margin-bottom:20px}.brand h1{margin:0;font-size:24px}.brand p{margin:5px 0 0;color:#8e99a8;font-size:13px}.auth{display:flex;gap:8px}.auth input{width:260px;background:#11161c;border:1px solid #2b3440;color:#fff;border-radius:10px;padding:10px 12px}.btn{border:1px solid #344150;background:#18212b;color:#f6f8fa;border-radius:10px;padding:10px 14px;cursor:pointer}.btn:hover{background:#202b37}.btn.danger{border-color:#63343c;background:#2a171b;color:#ffb9c3}.btn:disabled{opacity:.45;cursor:not-allowed}.grid{display:grid;grid-template-columns:300px minmax(0,1fr);gap:18px}.panel{background:rgba(17,21,27,.94);border:1px solid #242c36;border-radius:16px;overflow:hidden;box-shadow:0 18px 60px rgba(0,0,0,.25)}.panel-head{padding:14px 16px;border-bottom:1px solid #242c36;display:flex;align-items:center;justify-content:space-between}.muted{color:#8e99a8}.jobs{max-height:calc(100vh - 160px);overflow:auto}.job{padding:13px 16px;border-bottom:1px solid #20262e;cursor:pointer}.job:hover,.job.active{background:#18202a}.job-title{font-weight:650;font-size:14px}.job-meta{font-size:12px;color:#8793a2;margin-top:5px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.status{display:inline-flex;align-items:center;gap:7px;font-size:12px;border-radius:999px;padding:6px 10px;background:#202833}.dot{width:8px;height:8px;border-radius:50%;background:#8a94a1}.status.running .dot,.status.queued .dot{background:#67d98b;box-shadow:0 0 0 5px rgba(103,217,139,.08)}.status.failed .dot{background:#ff6b7a}.status.passed .dot{background:#69d8ff}.status.cancelled .dot,.status.cancelling .dot{background:#f5c76a}.main{min-width:0}.summary{padding:16px;display:flex;gap:12px;align-items:center;flex-wrap:wrap}.summary .spacer{flex:1}.fresh{font-size:12px;color:#91a0b1}.fresh.stale{color:#f5c76a}.screen-wrap{margin:0 16px 16px;background:#07090b;border:1px solid #242c36;border-radius:14px;min-height:360px;display:flex;align-items:center;justify-content:center;overflow:hidden;position:relative}.screen-wrap img{width:100%;height:auto;display:block}.screen-empty{color:#748091;text-align:center;padding:50px}.screen-label{position:absolute;top:10px;left:10px;background:rgba(0,0,0,.72);border:1px solid #343b45;border-radius:8px;padding:6px 9px;font-size:11px}.timeline{margin:0 16px 18px;border-top:1px solid #242c36}.event{display:grid;grid-template-columns:115px 1fr;gap:12px;padding:11px 0;border-bottom:1px solid #20262e}.event-kind{font-size:11px;text-transform:uppercase;letter-spacing:.06em;color:#7f8b99}.event-text{font-size:13px;line-height:1.45;overflow-wrap:anywhere}.ok{color:#77e09a}.bad{color:#ff8190}.notice{padding:11px 14px;margin:0 16px 16px;border:1px solid #3a3324;background:#211d14;border-radius:10px;color:#e8c96f;font-size:12px}.hidden{display:none}@media(max-width:900px){.shell{padding:12px}.top{align-items:flex-start;flex-direction:column}.auth{width:100%}.auth input{min-width:0;flex:1;width:auto}.grid{grid-template-columns:1fr}.jobs{max-height:260px}.screen-wrap{min-height:220px}.event{grid-template-columns:92px 1fr}}
</style>
</head>
<body>
<div class="shell">
  <div class="top">
    <div class="brand"><h1>Jev Live</h1><p>Реальные кадры браузера, решения модели и независимая проверка результата.</p></div>
    <div class="auth"><input id="token" type="password" autocomplete="off" placeholder="Ключ доступа"><button class="btn" id="connect">Подключиться</button></div>
  </div>
  <div id="authNotice" class="notice">Ключ хранится только в этой вкладке браузера и не добавляется в адрес страницы.</div>
  <div class="grid">
    <section class="panel"><div class="panel-head"><strong>Запуски</strong><button class="btn" id="refresh">↻</button></div><div id="jobs" class="jobs"><div class="screen-empty">Подключитесь, чтобы увидеть запуски.</div></div></section>
    <section class="panel main">
      <div class="summary"><span id="status" class="status"><span class="dot"></span><span>не выбран</span></span><span id="runName" class="muted">Выберите запуск</span><span class="spacer"></span><span id="fresh" class="fresh"></span><button id="stop" class="btn danger" disabled>Остановить</button></div>
      <div class="screen-wrap"><div id="frameLabel" class="screen-label hidden"></div><img id="frame" class="hidden" alt="Кадр браузера Jev"><div id="empty" class="screen-empty">Здесь появится реальный кадр серверного браузера.</div></div>
      <div id="meta" class="notice hidden"></div>
      <div id="timeline" class="timeline"></div>
    </section>
  </div>
</div>
<script>
(() => {
  const q=(s)=>document.querySelector(s); const tokenInput=q('#token'), jobsEl=q('#jobs'), statusEl=q('#status'), runName=q('#runName'), freshEl=q('#fresh'), frame=q('#frame'), empty=q('#empty'), frameLabel=q('#frameLabel'), timeline=q('#timeline'), stop=q('#stop'), meta=q('#meta');
  let token=sessionStorage.getItem('jevViewerToken')||'', selected=null, framePath=null, frameObject=null, loading=false;
  tokenInput.value=token;
  const terminal=new Set(['passed','failed','cancelled']);
  const headers=()=>({'Authorization':'Bearer '+token});
  async function api(path, options={}){ if(!token) throw new Error('Нужен ключ доступа'); const h={...(options.headers||{}),...headers()}; const r=await fetch(path,{...options,headers:h,cache:'no-store'}); if(!r.ok){let msg='HTTP '+r.status; try{const x=await r.json(); if(x.detail) msg=x.detail;}catch(_){ } throw new Error(msg);} return r; }
  function text(el,value){el.textContent=value==null?'':String(value)}
  function setStatus(value){statusEl.className='status '+(value||''); statusEl.querySelector('span:last-child').textContent=value||'неизвестно'; stop.disabled=!selected||terminal.has(value);}
  function clearNode(el){while(el.firstChild)el.removeChild(el.firstChild)}
  function event(kind,message,cls=''){const row=document.createElement('div');row.className='event';const k=document.createElement('div');k.className='event-kind';k.textContent=kind;const v=document.createElement('div');v.className='event-text '+cls;v.textContent=message;row.append(k,v);timeline.append(row)}
  function jobTitle(j){const m=j.metadata||{};return m.display_name||('Run '+j.job_id.slice(0,8))}
  function renderJobs(rows){clearNode(jobsEl); if(!rows.length){const e=document.createElement('div');e.className='screen-empty';e.textContent='Запусков пока нет.';jobsEl.append(e);return;} rows.forEach(j=>{const d=document.createElement('div');d.className='job'+(j.job_id===selected?' active':'');const a=document.createElement('div');a.className='job-title';a.textContent=jobTitle(j);const b=document.createElement('div');b.className='job-meta';const m=j.metadata||{};b.textContent=[j.status,m.issue_number?'#'+m.issue_number:null,m.pr_number?'PR #'+m.pr_number:null,m.commit_sha?m.commit_sha.slice(0,9):null].filter(Boolean).join(' · ');d.append(a,b);d.onclick=()=>{selected=j.job_id;loadSelected(true);loadJobs();};jobsEl.append(d);});}
  async function loadJobs(){try{const r=await api('/jobs');const data=await r.json();renderJobs(data.jobs||[]);if(!selected&&data.jobs&&data.jobs.length){selected=data.jobs[0].job_id;await loadSelected(true);}}catch(e){jobsEl.textContent='Ошибка доступа: '+e.message;}}
  function renderTimeline(job){clearNode(timeline);const p=job.progress||{};const decisions=p.decisions||((job.result||{}).decisions)||[];const history=p.history||((job.result||{}).history)||[];const count=Math.max(decisions.length,history.length);for(let i=0;i<count;i++){if(decisions[i])event('Модель','Выбрала: '+(decisions[i].operation||'?')+(decisions[i].target?' · '+decisions[i].target:''));if(history[i])event('Браузер','Выполнил: '+(history[i].action||history[i].kind||'?')+(history[i].page_changed===false?' · страница не изменилась':''));}const result=job.result||{};(result.checks||p.checks||[]).forEach(v=>event('Проверка','✓ '+v,'ok'));(result.failures||p.failures||[]).forEach(v=>event('Проверка','✕ '+v,'bad'));if(!count&&!(result.checks||[]).length&&!(result.failures||[]).length)event('Статус',p.phase||job.status||'ожидание');}
  function renderMeta(job){const m=job.metadata||{};const parts=[m.issue_number?'Issue #'+m.issue_number:null,m.pr_number?'PR #'+m.pr_number:null,m.commit_sha?'SHA '+m.commit_sha:null,'Run '+job.job_id].filter(Boolean);meta.classList.toggle('hidden',!parts.length);meta.textContent=parts.join(' · ');}
  function renderFresh(job){const p=job.progress||{};const ts=p.updated_at_ms||job.updated_at_ms; if(!ts){freshEl.textContent='';freshEl.className='fresh';return;}const age=Math.max(0,Math.floor((Date.now()-ts)/1000));freshEl.textContent=terminal.has(job.status)?'завершён':'обновлено '+age+' сек назад';freshEl.className='fresh'+(!terminal.has(job.status)&&age>5?' stale':'');}
  async function loadFrame(job,force=false){const pics=(job.evidence_files||[]).filter(x=>x.endsWith('.jpg')).sort();const latest=pics[pics.length-1];if(!latest)return;if(latest===framePath&&!force)return;const r=await api(latest);const blob=await r.blob();if(frameObject)URL.revokeObjectURL(frameObject);frameObject=URL.createObjectURL(blob);frame.src=frameObject;frame.classList.remove('hidden');empty.classList.add('hidden');frameLabel.textContent='Кадр '+pics.length+' · '+latest.split('/').pop();frameLabel.classList.remove('hidden');framePath=latest;}
  async function loadSelected(force=false){if(!selected||loading)return;loading=true;try{const r=await api('/jobs/'+encodeURIComponent(selected));const job=await r.json();setStatus(job.status);runName.textContent=jobTitle(job);renderFresh(job);renderMeta(job);renderTimeline(job);await loadFrame(job,force);}catch(e){freshEl.textContent='Ошибка: '+e.message;freshEl.className='fresh stale';}finally{loading=false;}}
  async function cancelSelected(){if(!selected||!confirm('Остановить именно этот запуск Jev?'))return;stop.disabled=true;try{const r=await api('/jobs/'+encodeURIComponent(selected)+'/cancel',{method:'POST'});const x=await r.json();freshEl.textContent='Команда остановки: '+x.status;await loadSelected(true);}catch(e){freshEl.textContent='Не удалось остановить: '+e.message;freshEl.className='fresh stale';}}
  q('#connect').onclick=async()=>{token=tokenInput.value.trim();if(!token)return;sessionStorage.setItem('jevViewerToken',token);await loadJobs();};q('#refresh').onclick=()=>loadJobs();stop.onclick=cancelSelected;
  setInterval(()=>{if(token){loadJobs();if(selected)loadSelected(false);}},1500); if(token)loadJobs();
})();
</script>
</body></html>"""


def viewer_headers() -> dict[str, str]:
    return {
        "Cache-Control": "no-store, max-age=0",
        "Pragma": "no-cache",
        "Referrer-Policy": "no-referrer",
        "X-Content-Type-Options": "nosniff",
        "X-Frame-Options": "DENY",
        "Content-Security-Policy": (
            "default-src 'none'; img-src 'self' blob:; connect-src 'self'; "
            "style-src 'unsafe-inline'; script-src 'unsafe-inline'; "
            "base-uri 'none'; form-action 'none'; frame-ancestors 'none'"
        ),
    }
