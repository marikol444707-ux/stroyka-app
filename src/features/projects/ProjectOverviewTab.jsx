import React from 'react';

export default function ProjectOverviewTab({
  budgetSpent,
  cat = {},
  ctx,
  economy,
  project,
  total,
}) {
  const {
    API,
    Bot,
    C,
    EXPENSE_CATEGORIES,
    FileText,
    Plus,
    ProjectEconomyPanel,
    ProjectObjectLinksPanel,
    QrCode,
    ScrollText,
    X,
    _sectionsOfEst,
    activeEstimatesForProject,
    addTask,
    brigadeContracts,
    btnB,
    btnG,
    btnO,
    btnR,
    buildJPRContent,
    buildKS3Content,
    buildPassportContent,
    card,
    estimateImportedPlanMeasure,
    estimateItemTotal,
    estimateMaterialPlanIssue,
    estimatePackage,
    estimatesList,
    fmtMeasure,
    inp,
    isEstimateMaterialItem,
    isEstimateWorkItem,
    isFinanceRole,
    isLeadership,
    isMobile,
    materialTransfers,
    materials,
    mobileExpandedRenderLists,
    newTask,
    projectAiSummaries,
    projectObjectLinks,
    projectPlanDone,
    removeTask,
    setActiveProjectTab,
    setMobileExpandedRenderLists,
    setNewTask,
    setProjectAiSummaries,
    setShowQRModal,
    showKS2,
    showPreview,
    tbl,
    tblC,
    tblH,
    toNum,
    user,
    visibleEstimatesForCurrentUser,
    workExecutionTotal,
    workJournal,
  } = ctx;

  const p = project;
  const _bs = budgetSpent || {};
  const isFinanceUser = typeof isFinanceRole === 'function' ? isFinanceRole() : Boolean(isFinanceRole);
  const isLeadershipUser = typeof isLeadership === 'function' ? isLeadership() : Boolean(isLeadership);

  return (
    <div>
      {isFinanceUser && (
        <div style={{
          display: 'grid',
          gridTemplateColumns: isMobile ? 'repeat(2,minmax(0,1fr))' : '1fr 1fr 1fr',
          gap: isMobile ? '8px' : '12px',
          marginBottom: '16px',
        }}>
          {EXPENSE_CATEGORIES.map(c => (
            <div key={c.id} style={{ padding: '12px', backgroundColor: C.bg, borderRadius: '10px', border: '1.5px solid ' + C.border }}>
              <p style={{ margin: '0 0 4px', fontSize: '11px', color: C.textSec }}>{c.label}</p>
              <b style={{ fontSize: '14px', color: c.color }}>{(cat[c.id] || 0).toLocaleString() + ' ₽'}</b>
            </div>
          ))}
        </div>
      )}

      {isFinanceUser && (
        <ProjectEconomyPanel
          C={C}
          card={card}
          btnB={btnB}
          btnG={btnG}
          btnO={btnO}
          project={p}
          economy={economy}
          isMobile={isMobile}
          onOpenFinance={() => setActiveProjectTab('Финансы')}
          onOpenJournal={() => setActiveProjectTab('Производство работ')}
          onOpenMaterials={() => setActiveProjectTab('Материалы')}
          onOpenEstimate={() => setActiveProjectTab('Смета')}
          showPreview={showPreview}
        />
      )}

      {(() => {
        const linksKey = ['project-object-links', p.id || p.name].join(':');
        const showLinks = !isMobile || mobileExpandedRenderLists[linksKey];
        if (!showLinks) {
          return (
            <div style={{ ...card, padding: '14px', marginBottom: '12px', backgroundColor: C.bgWhite, border: '1.5px solid ' + C.border }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: '10px', flexWrap: 'wrap' }}>
                <div>
                  <b style={{ color: C.text, fontSize: '14px' }}>🧭 Связи объекта</b>
                  <p style={{ margin: '4px 0 0', color: C.textSec, fontSize: '12px', lineHeight: 1.4 }}>Сметы, журналы, материалы и документы загружаются по запросу.</p>
                </div>
                <button type="button" onClick={() => setMobileExpandedRenderLists(prev => ({ ...prev, [linksKey]: true }))} style={{ ...btnB, padding: '8px 12px', fontSize: '12px' }}>Показать</button>
              </div>
            </div>
          );
        }
        return (
          <ProjectObjectLinksPanel
            C={C}
            card={card}
            items={projectObjectLinks(p)}
            isMobile={isMobile}
            onOpen={(tab) => tab && setActiveProjectTab(tab)}
          />
        );
      })()}

      {(() => {
        const wj = (workJournal || []).filter(w => w.project === p.name);
        const pending = wj.filter(w => !w.status || w.status === 'На проверке' || w.status === 'Автоматически из сметы');
        const confirmed = wj.filter(w => w.status === 'Подтверждено');
        const rejected = wj.filter(w => w.status === 'Отклонено');
        const last7 = wj.filter(w => {
          if (!w.date) return false;
          const d = new Date(w.date);
          return (Date.now() - d.getTime()) < 7 * 24 * 3600 * 1000;
        });
        const sumConfirmed = confirmed.reduce((s, w) => s + workExecutionTotal(w), 0);
        return (
          <div style={{ ...card, padding: '14px', marginBottom: '12px', backgroundColor: pending.length > 0 ? C.warningLight : C.bg, border: '1.5px solid ' + (pending.length > 0 ? C.warningBorder : C.border) }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '10px', flexWrap: 'wrap', gap: '8px' }}>
              <b style={{ color: C.text, fontSize: '13px' }}>
                👷 Работы от мастеров {pending.length > 0 && <span style={{ padding: '2px 8px', borderRadius: '8px', backgroundColor: C.warning, color: 'white', fontSize: '11px', marginLeft: '4px' }}>{pending.length + ' на проверке'}</span>}
              </b>
              <button onClick={() => setActiveProjectTab('Производство работ')} style={{ ...btnG, padding: '4px 10px', fontSize: '11px' }}>📜 Открыть журнал</button>
            </div>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit,minmax(120px,1fr))', gap: '8px' }}>
              <div style={{ padding: '8px', borderRadius: '8px', backgroundColor: C.bgWhite, border: '1.5px solid ' + C.border }}><p style={{ color: C.textSec, fontSize: '10px', margin: '0 0 2px' }}>За 7 дней</p><b style={{ color: C.text, fontSize: '15px' }}>{last7.length}</b></div>
              <div style={{ padding: '8px', borderRadius: '8px', backgroundColor: C.bgWhite, border: '1.5px solid ' + C.border }}><p style={{ color: C.textSec, fontSize: '10px', margin: '0 0 2px' }}>Подтверждено</p><b style={{ color: C.success, fontSize: '15px' }}>{confirmed.length}</b></div>
              <div style={{ padding: '8px', borderRadius: '8px', backgroundColor: C.bgWhite, border: '1.5px solid ' + C.border }}><p style={{ color: C.textSec, fontSize: '10px', margin: '0 0 2px' }}>На проверке</p><b style={{ color: C.warning, fontSize: '15px' }}>{pending.length}</b></div>
              {rejected.length > 0 && <div style={{ padding: '8px', borderRadius: '8px', backgroundColor: C.bgWhite, border: '1.5px solid ' + C.border }}><p style={{ color: C.textSec, fontSize: '10px', margin: '0 0 2px' }}>Отклонено</p><b style={{ color: C.danger, fontSize: '15px' }}>{rejected.length}</b></div>}
              {isFinanceUser && <div style={{ padding: '8px', borderRadius: '8px', backgroundColor: C.bgWhite, border: '1.5px solid ' + C.border, gridColumn: 'span 2' }}><p style={{ color: C.textSec, fontSize: '10px', margin: '0 0 2px' }}>К оплате исполнителям</p><b style={{ color: C.accent, fontSize: '15px' }}>{Math.round(sumConfirmed).toLocaleString('ru-RU') + ' ₽'}</b></div>}
            </div>
          </div>
        );
      })()}

      <div style={{ ...card, padding: '16px', marginBottom: '12px', backgroundColor: C.accentLight, border: '1.5px solid ' + C.accentBorder }}>
        <b style={{ color: C.text, fontSize: '13px', display: 'block', marginBottom: '12px' }}>📊 Бригады и выполнение</b>
        <div style={{ display: 'grid', gridTemplateColumns: isMobile ? '1fr' : 'repeat(3,1fr)', gap: '10px', marginBottom: '12px' }}>
          <div style={{ textAlign: 'center' }}><p style={{ color: C.textSec, fontSize: '11px', margin: '0 0 4px' }}>Бригад</p><b style={{ color: C.text, fontSize: '18px' }}>{brigadeContracts.filter(bc => bc.projectName === p.name).length}</b></div>
          <div style={{ textAlign: 'center' }}><p style={{ color: C.textSec, fontSize: '11px', margin: '0 0 4px' }}>По договорам</p><b style={{ color: C.accent, fontSize: '16px' }}>{brigadeContracts.filter(bc => bc.projectName === p.name).reduce((s, bc) => s + Number(bc.totalAmount || 0), 0).toLocaleString() + ' ₽'}</b></div>
          <div style={{ textAlign: 'center' }}><p style={{ color: C.textSec, fontSize: '11px', margin: '0 0 4px' }}>Смет</p><b style={{ color: C.text, fontSize: '18px' }}>{visibleEstimatesForCurrentUser(estimatesList).filter(e => e.projectName === p.name || Number(e.projectId) === Number(p.id)).length}</b></div>
        </div>
        <div style={{ marginBottom: '12px' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '4px' }}>
            <b style={{ fontSize: '12px', color: C.text }}>Выполнение работ бригадами</b>
            <span style={{ fontSize: '12px', color: C.textSec }}>{(() => {
              const pBrigades = brigadeContracts.filter(bc => bc.projectName === p.name);
              if (!pBrigades.length) return '0%';
              const totalSmeta = pBrigades.reduce((s, bc) => s + Number(bc.totalAmount || 0), 0);
              const totalDone = pBrigades.reduce((s, bc) => s + Number(bc.doneAmount || 0), 0);
              return totalSmeta > 0 ? Math.min(100, Math.round(totalDone / totalSmeta * 100)) + '%' : '0%';
            })()}</span>
          </div>
          <div style={{ backgroundColor: C.bgGray, borderRadius: '6px', height: '10px' }}>
            <div style={{ backgroundColor: C.success, width: (() => {
              const pBrigades = brigadeContracts.filter(bc => bc.projectName === p.name);
              const totalSmeta = pBrigades.reduce((s, bc) => s + Number(bc.totalAmount || 0), 0);
              const totalDone = pBrigades.reduce((s, bc) => s + Number(bc.doneAmount || 0), 0);
              return Math.min(100, totalSmeta > 0 ? Math.round(totalDone / totalSmeta * 100) : 0) + '%';
            })(), height: '100%', borderRadius: '6px' }} />
          </div>
        </div>
        <div style={{ display: 'grid', gridTemplateColumns: isMobile ? '1fr' : 'repeat(2,1fr)', gap: '10px' }}>
          <div style={{ backgroundColor: C.successLight, padding: '10px', borderRadius: '8px', border: '1px solid ' + C.successBorder }}><p style={{ color: C.textSec, fontSize: '11px', margin: '0 0 4px' }}>Смета заказчика</p><b style={{ color: C.success, fontSize: '14px' }}>{Math.round(projectPlanDone(p).plan).toLocaleString('ru-RU') + ' ₽'}</b></div>
          <div style={{ backgroundColor: C.warningLight, padding: '10px', borderRadius: '8px', border: '1px solid ' + C.warningBorder }}><p style={{ color: C.textSec, fontSize: '11px', margin: '0 0 4px' }}>Подрядчикам</p><b style={{ color: C.warning, fontSize: '14px' }}>{brigadeContracts.filter(bc => bc.projectName === p.name).reduce((s, bc) => s + Number(bc.totalAmount || 0), 0).toLocaleString() + ' ₽'}</b></div>
        </div>
      </div>

      <div style={{ backgroundColor: C.bg, borderRadius: '10px', padding: '14px', border: '1.5px solid ' + C.border, marginBottom: '12px' }}>
        {isFinanceUser && (
          <>
            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '8px' }}><b style={{ color: C.text, fontSize: '13px' }}>Прогресс бюджета</b><span style={{ fontSize: '13px', color: total > p.budget ? C.danger : C.success }}>{Math.round(total).toLocaleString('ru-RU') + ' из ' + p.budget.toLocaleString() + ' ₽'}</span></div>
            <div style={{ backgroundColor: C.bgGray, borderRadius: '6px', height: '10px' }}><div style={{ backgroundColor: total > p.budget ? C.danger : total > p.budget * 0.8 ? C.warning : C.success, width: Math.min(100, p.budget > 0 ? total / p.budget * 100 : 0) + '%', height: '100%', borderRadius: '6px', transition: 'width 0.3s' }} /></div>
            <div style={{ display: 'flex', gap: '12px', flexWrap: 'wrap', marginTop: '8px', fontSize: '11px', color: C.textSec }}>
              <span>🔨 Работы/Бригады: <b style={{ color: C.text }}>{Math.round(_bs.works || 0).toLocaleString('ru-RU') + ' ₽'}</b></span>
              <span>📦 Материалы: <b style={{ color: C.text }}>{Math.round(_bs.materials || 0).toLocaleString('ru-RU') + ' ₽'}</b></span>
              {(_bs.unexpected || 0) > 0 && <span>🆕 Изменения к смете: <b style={{ color: C.warning }}>{Math.round(_bs.unexpected).toLocaleString('ru-RU') + ' ₽'}</b></span>}
              {(_bs.other || 0) > 0 && <span>⚙️ Прочие затраты: <b style={{ color: C.text }}>{Math.round(_bs.other).toLocaleString('ru-RU') + ' ₽'}</b></span>}
            </div>
            <p style={{ margin: '6px 0 0', fontSize: '10px', color: C.textMuted, fontStyle: 'italic' }}>Себестоимость = всё что мы потратили (наши затраты), а не бюджет заказчика</p>
          </>
        )}
      </div>

      <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap', marginBottom: '16px' }}>
        <button onClick={() => showPreview(buildPassportContent(p), 'Паспорт объекта — ' + p.name)} style={btnB}><FileText size={14} />Паспорт</button>
        <button onClick={() => showKS2(p)} style={btnG}><FileText size={14} />КС-2</button>
        <button onClick={() => showPreview(buildKS3Content(p), 'КС-3 — ' + p.name)} style={btnG}><FileText size={14} />КС-3</button>
        <button onClick={() => showPreview(buildJPRContent(p.name), 'ЖПР — ' + p.name)} style={btnG}><ScrollText size={14} />ЖПР</button>
        <button onClick={() => setShowQRModal({ title: 'QR — ' + p.name, data: window.location.origin + '/?project=' + encodeURIComponent(p.name) })} style={btnG}><QrCode size={14} />QR</button>
      </div>

      <div>
        <b style={{ color: C.text, fontSize: '13px' }}>Задачи:</b>
        {isLeadershipUser && (
          <div style={{ display: 'flex', gap: '8px', marginTop: '8px', marginBottom: '10px' }}>
            <input placeholder="Новая задача..." value={newTask} onChange={e => setNewTask(e.target.value)} onKeyDown={e => e.key === 'Enter' && addTask(p)} style={{ ...inp, marginBottom: 0, flex: 1, fontSize: '13px' }} />
            <button onClick={() => addTask(p)} style={btnO}><Plus size={14} /></button>
          </div>
        )}
        {(p.tasks || []).map((t, i) => (
          <div key={i} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '8px 10px', backgroundColor: C.bg, borderRadius: '8px', marginBottom: '6px', border: '1.5px solid ' + C.border }}>
            <span style={{ fontSize: '13px', color: C.text }}>{'• ' + t}</span>
            {isLeadershipUser && <button onClick={() => removeTask(p, i)} style={{ ...btnR, padding: '3px 7px', fontSize: '10px' }}><X size={10} /></button>}
          </div>
        ))}
      </div>

      {user && ['директор', 'зам_директора', 'бухгалтер', 'прораб'].includes(user.role) && (() => {
        const smetaItems = activeEstimatesForProject(p, 'Заказчик').flatMap(est => (_sectionsOfEst(est) || []).flatMap(s => (s.items || []).map(i => ({ ...i, section: s.name, workPackage: estimatePackage(est) }))));
        const norm = (s) => (s || '').toLowerCase().replace(/[.,;:()«»"'-]/g, ' ').replace(/\s+/g, ' ').trim();
        const matchScore = (a, b) => {
          const aw = norm(a).split(' ').filter(w => w.length >= 3);
          const bw = new Set(norm(b).split(' ').filter(w => w.length >= 3));
          if (!aw.length || !bw.size) return 0;
          const common = aw.filter(w => bw.has(w)).length;
          return common / Math.max(aw.length, 1);
        };
        const projMaterials = materials.filter(m => m.project === p.name);
        const projTransfers = materialTransfers.filter(t => t.projectName === p.name);
        const workProgress = smetaItems.filter(it => isEstimateWorkItem(it, it.section)).map(it => {
          const plan = Number(it.quantity || 0);
          const done = Number(it.doneQuantity || 0);
          const left = Math.max(0, plan - done);
          const pct = plan > 0 ? Math.min(100, Math.round(done / plan * 100)) : 0;
          return { name: it.name, section: it.section, unit: it.unit, plan, done, left, pct };
        });
        const matPlan = smetaItems.filter(i => isEstimateMaterialItem(i, i.section) && !estimateMaterialPlanIssue(i, i.section) && toNum(estimateImportedPlanMeasure(i).qty) > 0).map(it => {
          const planMeasure = estimateImportedPlanMeasure(it);
          const plan = toNum(planMeasure.qty);
          const bought = projMaterials.filter(m => matchScore(m.name, it.name) >= 0.4).reduce((s, m) => s + Number(m.quantity || 0), 0);
          return { name: it.name, unit: planMeasure.unit || it.unit, plan, bought, need: Math.max(0, plan - bought) };
        });
        const fmt = (n) => Number(n || 0).toLocaleString('ru-RU');
        const payload = {
          project: p.name,
          total: smetaItems.reduce((s, i) => s + estimateItemTotal(i), 0),
          workProgress: workProgress.filter(w => w.plan > 0),
          materials: matPlan,
          stock: projMaterials.map(m => ({ name: m.name, qty: Number(m.quantity || 0), unit: m.unit })),
          transfers: projTransfers.slice(0, 20).map(t => ({ name: t.materialName, qty: Number(t.quantity || 0), unit: t.unit, to: t.toPerson, date: t.transferDate })),
        };
        const payloadStr = JSON.stringify(payload);
        let _h = 0;
        for (let i = 0; i < payloadStr.length; i++) _h = ((_h * 31) + payloadStr.charCodeAt(i)) | 0;
        const currentHash = (_h >>> 0).toString(16);
        const cached = projectAiSummaries[p.name];
        const isFresh = cached && cached.payloadHash === currentHash;
        const fmtAgo = (iso) => {
          if (!iso) return '';
          const d = new Date(iso);
          const m = Math.floor((Date.now() - d.getTime()) / 60000);
          if (m < 1) return 'только что';
          if (m < 60) return m + ' мин назад';
          const h = Math.floor(m / 60);
          if (h < 24) return h + ' ч назад';
          return Math.floor(h / 24) + ' дн назад';
        };
        const runAiSummary = async () => {
          const prompt = 'Объект "' + p.name + '". Проанализируй прогресс и материальный учёт. Данные ниже.\n\n' + JSON.stringify(payload, null, 1) + '\n\nОТВЕТЬ СТРОГО JSON (без markdown):\n{\n  "summary":"одна-две фразы общего впечатления",\n  "progress":[{"what":"что","status":"в норме|отставание|опережение","note":"что заметил"}],\n  "materials":[{"what":"материал","problem":"нехватка|избыток|пропажа|норма","action":"что сделать","amount":число_или_0}],\n  "alerts":[{"type":"критично|внимание|совет","text":"что"}]\n}\nИспользуй только данные из payload. Если данных мало — пиши "недостаточно данных".';
          setProjectAiSummaries(prev => ({ ...prev, [p.name]: { ...(prev[p.name] || {}), loading: true } }));
          try {
            const res = await fetch(API + '/ai-chat', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ messages: [{ role: 'user', content: prompt }], jsonOnly: true }) });
            const data = await res.json();
            const raw = (data.response || data.error || '').trim();
            let parsed = null;
            try {
              const clean = raw.replace(/^```(?:json)?/i, '').replace(/```$/,'').trim();
              const s = clean.indexOf('{');
              const e = clean.lastIndexOf('}');
              if (s >= 0 && e > s) parsed = JSON.parse(clean.slice(s, e + 1));
            } catch {}
            let out;
            if (parsed) {
              const ln = [];
              if (parsed.summary) ln.push('📋 ' + parsed.summary, '');
              if (Array.isArray(parsed.alerts) && parsed.alerts.length) {
                ln.push('🚨 ВНИМАНИЕ');
                parsed.alerts.forEach((a, n) => ln.push((n + 1) + '. [' + (a.type || '') + '] ' + (a.text || '')));
                ln.push('');
              }
              if (Array.isArray(parsed.progress) && parsed.progress.length) {
                ln.push('🔨 РАБОТЫ');
                parsed.progress.forEach((q, n) => ln.push((n + 1) + '. ' + (q.what || '?') + ' — ' + (q.status || '?') + (q.note ? ': ' + q.note : '')));
                ln.push('');
              }
              if (Array.isArray(parsed.materials) && parsed.materials.length) {
                ln.push('📦 МАТЕРИАЛЫ');
                parsed.materials.forEach((m, n) => ln.push((n + 1) + '. ' + (m.what || '?') + ' — ' + (m.problem || '?') + (m.action ? ' → ' + m.action : '') + (m.amount ? ' (' + fmt(m.amount) + ')' : '')));
              }
              out = ln.join('\n');
            } else {
              out = raw || 'Ошибка ответа ИИ';
            }
            try {
              await fetch(API + '/project-ai-summary', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ projectName: p.name, payloadHash: currentHash, summary: out }) });
            } catch {}
            setProjectAiSummaries(prev => ({ ...prev, [p.name]: { exists: true, payloadHash: currentHash, summary: out, updatedAt: new Date().toISOString(), loading: false } }));
          } catch {
            setProjectAiSummaries(prev => ({ ...prev, [p.name]: { ...(prev[p.name] || {}), loading: false, error: 'Ошибка соединения с AI' } }));
          }
        };

        return (
          <div style={{ ...card, padding: '16px', marginBottom: '12px', backgroundColor: C.bgWhite, border: '1.5px solid ' + C.accentBorder }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '14px' }}>
              <b style={{ color: C.text, fontSize: '14px' }}>📊 Контроль объекта</b>
              <button onClick={runAiSummary} disabled={cached && cached.loading} style={{ ...btnB, backgroundColor: '#10b981', color: 'white', borderColor: '#059669', fontSize: '12px', opacity: (cached && cached.loading) ? 0.6 : 1 }}><Bot size={13} />{cached && cached.loading ? 'AI думает...' : cached && cached.summary ? 'Обновить ИИ' : 'AI-сводка'}</button>
            </div>
            {cached && cached.loading && (
              <div style={{ ...card, padding: '14px', marginBottom: '14px', backgroundColor: C.infoLight, border: '1.5px solid ' + C.infoBorder, textAlign: 'center' }}>
                <p style={{ margin: 0, fontSize: '13px', color: C.info }}>⏳ AI анализирует объект... (15-40 сек)</p>
              </div>
            )}
            {cached && cached.error && (
              <div style={{ ...card, padding: '12px', marginBottom: '14px', backgroundColor: C.dangerLight, border: '1.5px solid ' + C.dangerBorder }}>
                <p style={{ margin: 0, fontSize: '13px', color: C.danger }}>❌ {cached.error}</p>
              </div>
            )}
            {cached && cached.summary && !cached.loading && (
              <div style={{ ...card, padding: '12px', marginBottom: '14px', backgroundColor: isFresh ? C.successLight : C.warningLight, border: '1.5px solid ' + (isFresh ? C.successBorder : C.warningBorder) }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
                  <b style={{ fontSize: '12px', color: isFresh ? C.success : C.warning }}>🤖 {isFresh ? 'AI-сводка актуальна' : '⚠️ Данные изменились — нужно обновить'}</b>
                  <span style={{ fontSize: '11px', color: C.textSec }}>{fmtAgo(cached.updatedAt)}</span>
                </div>
                <div style={{ fontSize: '12px', color: C.text, whiteSpace: 'pre-wrap', lineHeight: '1.5' }}>{cached.summary}</div>
              </div>
            )}
            {(!cached || (!cached.summary && !cached.loading && !cached.error)) && <p style={{ fontSize: '12px', color: C.textMuted, marginBottom: '12px', padding: '8px', backgroundColor: C.bg, borderRadius: '8px' }}>💡 AI-сводка ещё не делалась. Нажмите «AI-сводка» — анализ сохранится в системе.</p>}
            {smetaItems.length === 0 && <p style={{ color: C.textMuted, fontSize: '12px', padding: '10px', textAlign: 'center' }}>У объекта нет сметы — нечего сравнивать. Добавьте смету в разделе «Сметы».</p>}
            {smetaItems.length > 0 && (
              <>
                <div style={{ marginBottom: '14px' }}>
                  <b style={{ color: C.text, fontSize: '12px', display: 'block', marginBottom: '6px' }}>📋 Прогресс по смете (работы)</b>
                  <table style={{ ...tbl, fontSize: '11px' }}>
                    <thead><tr><th style={tblH}>Позиция</th><th style={tblH}>План</th><th style={tblH}>Выполнено</th><th style={tblH}>Осталось</th><th style={tblH}>%</th></tr></thead>
                    <tbody>
                      {workProgress.filter(w => w.plan > 0).slice(0, 15).map((w, i) => (
                        <tr key={i}><td style={{ ...tblC, fontSize: '11px' }}>{w.name}</td><td style={{ ...tblC, fontSize: '11px' }}>{fmtMeasure(w.plan, w.unit)}</td><td style={{ ...tblC, fontSize: '11px', color: w.done > 0 ? C.success : C.textMuted }}>{fmtMeasure(w.done, w.unit)}</td><td style={{ ...tblC, fontSize: '11px', color: w.left > 0 ? C.warning : C.success }}>{fmtMeasure(w.left, w.unit)}</td><td style={{ ...tblC, fontSize: '11px', fontWeight: '600', color: w.pct >= 100 ? C.success : w.pct >= 50 ? C.info : C.warning }}>{w.pct}%</td></tr>
                      ))}
                    </tbody>
                  </table>
                  {!workProgress.filter(w => w.plan > 0).length && <p style={{ color: C.textMuted, fontSize: '11px', padding: '8px' }}>В смете нет позиций работ</p>}
                </div>
                <div style={{ marginBottom: '14px' }}>
                  <b style={{ color: C.text, fontSize: '12px', display: 'block', marginBottom: '6px' }}>📥 Материалы — план vs закуплено</b>
                  <table style={{ ...tbl, fontSize: '11px' }}>
                    <thead><tr><th style={tblH}>Материал</th><th style={tblH}>По смете</th><th style={tblH}>Закуплено</th><th style={tblH}>Не хватает</th></tr></thead>
                    <tbody>
                      {matPlan.slice(0, 15).map((m, i) => (
                        <tr key={i}><td style={{ ...tblC, fontSize: '11px' }}>{m.name}</td><td style={{ ...tblC, fontSize: '11px' }}>{m.plan} {m.unit}</td><td style={{ ...tblC, fontSize: '11px', color: m.bought >= m.plan ? C.success : C.info }}>{m.bought} {m.unit}</td><td style={{ ...tblC, fontSize: '11px', color: m.need > 0 ? C.danger : C.success }}>{m.need > 0 ? m.need + ' ' + m.unit : '✅'}</td></tr>
                      ))}
                    </tbody>
                  </table>
                  {!matPlan.length && <p style={{ color: C.textMuted, fontSize: '11px', padding: '8px' }}>В смете нет материалов</p>}
                </div>
              </>
            )}
            <div style={{ marginBottom: '14px' }}>
              <b style={{ color: C.text, fontSize: '12px', display: 'block', marginBottom: '6px' }}>📤 Выдачи мастерам ({projTransfers.length})</b>
              <table style={{ ...tbl, fontSize: '11px' }}>
                <thead><tr><th style={tblH}>Материал</th><th style={tblH}>Кол-во</th><th style={tblH}>Кому</th><th style={tblH}>Дата</th></tr></thead>
                <tbody>
                  {projTransfers.slice(0, 10).map((t, i) => (
                    <tr key={i}><td style={{ ...tblC, fontSize: '11px' }}>{t.materialName}</td><td style={{ ...tblC, fontSize: '11px' }}>{t.quantity} {t.unit}</td><td style={{ ...tblC, fontSize: '11px' }}>{t.toPerson}</td><td style={{ ...tblC, fontSize: '11px' }}>{t.transferDate}</td></tr>
                  ))}
                </tbody>
              </table>
              {!projTransfers.length && <p style={{ color: C.textMuted, fontSize: '11px', padding: '8px' }}>Передач ещё не было</p>}
            </div>
            <div>
              <b style={{ color: C.text, fontSize: '12px', display: 'block', marginBottom: '6px' }}>🏬 Остатки на складе объекта ({projMaterials.filter(m => Number(m.quantity || 0) > 0).length})</b>
              <table style={{ ...tbl, fontSize: '11px' }}>
                <thead><tr><th style={tblH}>Материал</th><th style={tblH}>Остаток</th><th style={tblH}>Категория</th></tr></thead>
                <tbody>
                  {projMaterials.filter(m => Number(m.quantity || 0) > 0).slice(0, 15).map((m, i) => (
                    <tr key={i}><td style={{ ...tblC, fontSize: '11px' }}>{m.name}</td><td style={{ ...tblC, fontSize: '11px', fontWeight: '600', color: C.success }}>{m.quantity} {m.unit}</td><td style={{ ...tblC, fontSize: '11px', color: C.textSec }}>{m.category || ''}</td></tr>
                  ))}
                </tbody>
              </table>
              {!projMaterials.filter(m => Number(m.quantity || 0) > 0).length && <p style={{ color: C.textMuted, fontSize: '11px', padding: '8px' }}>Склад объекта пуст</p>}
            </div>
          </div>
        );
      })()}
    </div>
  );
}
