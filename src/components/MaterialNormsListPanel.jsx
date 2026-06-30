import React from 'react';
import { Edit2, Search, Trash2 } from 'lucide-react';
import { WORK_MATERIAL_NORM_RULES } from '../utils/materialNormUtils';
import { C, badge, btnB, btnG, btnR, btnState, card, inp } from '../constants/uiTheme';

export default function MaterialNormsListPanel({
  materialNormSearch,
  setMaterialNormSearch,
  materialNorms,
  materialNormsPage,
  loadMaterialNormsPage,
  materialNormRuleForCalc,
  materialTitleForNormRule,
  canEditMaterialNorms,
  editMaterialNorm,
  disableMaterialNorm,
  isMobile,
}) {
  const term = materialNormSearch.trim().toLowerCase();
  const loadedNorms = materialNorms || [];
  const filteredNorms = term
    ? loadedNorms.filter(n => [
      n.ruleKey,
      n.id,
      n.name,
      n.label,
      ...(Array.isArray(n.work) ? n.work : []),
      ...(Array.isArray(n.material) ? n.material : []),
      ...(Array.isArray(n.blockWork) ? n.blockWork : []),
    ].some(v => String(v || '').toLowerCase().includes(term)))
    : loadedNorms;
  const normsToShow = filteredNorms.length || term
    ? filteredNorms
    : WORK_MATERIAL_NORM_RULES.map(r => ({...r, ruleKey: r.id, name: materialTitleForNormRule(r), active: true}));
  const normQueryMatches = (materialNormsPage.search || '') === materialNormSearch.trim();
  const canLoadMoreNorms = normQueryMatches && materialNormsPage.hasMore;
  const canEdit = canEditMaterialNorms();

  return (
    <div style={{display: 'grid', gap: '10px'}}>
      <div style={{...card, padding: '12px', display: 'grid', gridTemplateColumns: isMobile ? '1fr' : 'minmax(260px,1fr) auto', gap: '10px', alignItems: 'center'}}>
        <div style={{position: 'relative'}}>
          <Search size={14} style={{position: 'absolute', left: 12, top: '50%', transform: 'translateY(-50%)', color: C.textMuted}} />
          <input
            placeholder="Поиск нормы на сервере: работа, материал, код"
            value={materialNormSearch}
            onChange={e => setMaterialNormSearch(e.target.value)}
            style={{...inp, marginBottom: 0, paddingLeft: 34, width: '100%', boxSizing: 'border-box'}}
          />
          {(materialNormsPage.loading || materialNormsPage.error) && normQueryMatches && (
            <div style={{color: materialNormsPage.error ? C.danger : C.textMuted, fontSize: '11px', marginTop: '5px'}}>
              {materialNormsPage.error || 'Ищу нормы...'}
            </div>
          )}
        </div>
        <button
          type="button"
          onClick={() => loadMaterialNormsPage({search: materialNormSearch.trim(), offset: filteredNorms.length})}
          disabled={!canLoadMoreNorms || materialNormsPage.loading}
          style={btnState(btnB, !canLoadMoreNorms || materialNormsPage.loading, {justifyContent: 'center'})}
        >
          {materialNormsPage.loading ? 'Загружаю...' : canLoadMoreNorms ? 'Загрузить ещё нормы' : 'Нормы загружены'}
        </button>
        <p style={{gridColumn: isMobile ? 'auto' : '1 / -1', color: C.textMuted, fontSize: '11px', margin: 0}}>
          Показано {normsToShow.length} норм. Поиск обращается к backend и добавляет найденные правила в локальный набор расчёта.
        </p>
      </div>

      {normsToShow.map(n => {
        const rule = materialNormRuleForCalc(n);
        return (
          <div key={rule.id || rule.ruleKey} style={{...card, padding: '12px 14px', display: 'grid', gridTemplateColumns: isMobile ? '1fr' : 'minmax(220px,1.3fr) minmax(260px,2fr) auto', gap: '12px', alignItems: 'center'}}>
            <div style={{minWidth: 0}}>
              <div style={{display: 'flex', gap: '6px', alignItems: 'center', flexWrap: 'wrap'}}>
                <b style={{color: C.text, fontSize: '13px', display: 'block'}}>{rule.name || materialTitleForNormRule(rule)}</b>
                <span style={badge(C.success, C.successLight, C.successBorder)}>Глобальная</span>
              </div>
              <p style={{color: C.textMuted, margin: '3px 0 0', fontSize: '11px'}}>{rule.ruleKey || rule.id}</p>
            </div>
            <div style={{display: 'grid', gridTemplateColumns: isMobile ? '1fr' : '1fr 1fr', gap: '8px', minWidth: 0}}>
              <div><span style={{color: C.textMuted, fontSize: '10px', textTransform: 'uppercase'}}>Работа</span><p style={{color: C.textSec, margin: '2px 0 0', fontSize: '12px'}}>{(rule.work || []).join(', ') || '—'}</p></div>
              <div><span style={{color: C.textMuted, fontSize: '10px', textTransform: 'uppercase'}}>Материал</span><p style={{color: C.textSec, margin: '2px 0 0', fontSize: '12px'}}>{(rule.material || []).join(', ') || '—'}</p></div>
              <div><span style={{color: C.textMuted, fontSize: '10px', textTransform: 'uppercase'}}>Норма</span><p style={{color: C.success, margin: '2px 0 0', fontSize: '12px', fontWeight: '700'}}>{Number(rule.qtyPerUnit || 0).toLocaleString('ru-RU') + ' ' + (rule.materialUnit || '') + ' / ' + (rule.workUnit || '')}</p></div>
              <div><span style={{color: C.textMuted, fontSize: '10px', textTransform: 'uppercase'}}>Слой</span><p style={{color: C.textSec, margin: '2px 0 0', fontSize: '12px'}}>{rule.thicknessBaseMm ? ('база ' + rule.thicknessBaseMm + ' мм' + (rule.defaultThicknessMm ? ' · типовой ' + rule.defaultThicknessMm + ' мм' : '')) : 'не учитывается'}</p></div>
            </div>
            <div style={{display: 'flex', gap: '6px', justifyContent: isMobile ? 'flex-start' : 'flex-end'}}>
              <button disabled={!n.id || !canEdit} onClick={() => editMaterialNorm(n)} style={btnState(btnG, !n.id || !canEdit, {padding: '5px 9px'})} title={n.id ? 'Редактировать' : 'После деплоя справочника можно будет редактировать'}><Edit2 size={12} /></button>
              {canEdit && n.id && <button onClick={() => disableMaterialNorm(n.id)} style={{...btnR, padding: '5px 9px'}} title="Отключить норму"><Trash2 size={12} /></button>}
            </div>
          </div>
        );
      })}
    </div>
  );
}
