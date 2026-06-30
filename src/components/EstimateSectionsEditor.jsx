import React from 'react';
import { Plus, Trash2 } from 'lucide-react';
import { C, btnB, btnG, btnO, btnR, card, inp, tbl, tblC, tblH } from '../constants/uiTheme';
import { denormalizeMeasure, fmtMeasure, normalizeMeasure, toNum } from '../utils/measureUtils';
import {
  estimateImportLineMeta,
  estimateItemLooksResourceAdjustment,
  estimateItemTotal,
  estimateItemTypeMeta,
  estimateIssueDomId,
  estimateMeasurementBasisMeta,
  estimateMeasurementBasisOf,
  isEstimateWorkItem,
  normalizeEstimateItemType,
  normalizeEstimateWorkingItem,
} from '../utils/estimateUtils';
import EstimateSectionHeader from './EstimateSectionHeader';
import EstimateItemGroupHeader from './EstimateItemGroupHeader';
import EstimateItemGroupEmpty from './EstimateItemGroupEmpty';

export default function EstimateSectionsEditor({
  selectedEstimate,
  showEstimateIssuesOnly,
  mobileExpandedRenderLists,
  setMobileExpandedRenderLists,
  isMobile,
  estimateQualityRows,
  brigadeContracts,
  userRole,
  setSelectedEstimate,
  setEstimatesList,
  persistEstimate,
  newEstimateItem,
  setNewEstimateItem,
  estimateIssueFocusKey,
}) {
  const allSections = (selectedEstimate.sections || []).map((section, si) => ({section, si}));
  const sectionListKey = ['estimate-sections', selectedEstimate.id, 'all'].join(':');
  const sectionLimit = isMobile ? 5 : 8;
  const limitSections = !showEstimateIssuesOnly && !mobileExpandedRenderLists[sectionListKey];
  const visibleSections = limitSections ? allSections.slice(0, sectionLimit) : allSections;
  const hiddenSections = allSections.length - visibleSections.length;

  return (
    <>
      {visibleSections.map(({section, si}) => {
        const itemKind = it => normalizeEstimateItemType(it, section.name);
        const sumOf = it => estimateItemTotal(it);
        const allItems = section.items || [];
        const issueKeySet = showEstimateIssuesOnly ? new Set(estimateQualityRows(selectedEstimate).map(r => String(r.sectionIdx) + '|' + String(r.itemIdx))) : null;
        const typedItems = allItems
          .map((i, idx) => {
            const normalized = normalizeEstimateWorkingItem(i, section.name);
            return {...normalized, _idx: idx, _type: itemKind(normalized)};
          })
          .filter(i => !showEstimateIssuesOnly || issueKeySet.has(String(si) + '|' + String(i._idx)));
        if (showEstimateIssuesOnly && typedItems.length === 0) return null;

        const works = typedItems.filter(i => i._type === 'work');
        const mats = typedItems.filter(i => i._type === 'material' && !estimateItemLooksResourceAdjustment(i, section.name));
        const adjustments = typedItems.filter(i => i._type === 'adjustment' || estimateItemLooksResourceAdjustment(i, section.name));
        const others = typedItems.filter(i => !['work', 'material', 'adjustment'].includes(i._type));
        const total = allItems.reduce((s, i) => s + sumOf(i), 0);
        const totalW = works.reduce((s, i) => s + sumOf(i), 0);
        const totalM = mats.reduce((s, i) => s + sumOf(i), 0);
        const totalAdjustment = adjustments.reduce((s, i) => s + sumOf(i), 0);
        const totalOther = others.reduce((s, i) => s + sumOf(i), 0);

        const removeAt = idx => {
          const sections = (selectedEstimate.sections || []).map((s, sidx) => sidx === si ? {...s, items: (s.items || []).filter((_, i) => i !== idx)} : s);
          const updated = {...selectedEstimate, sections};
          setSelectedEstimate(updated);
          setEstimatesList(prev => prev.map(e => e.id === updated.id ? updated : e));
          persistEstimate(updated);
        };

        const updateItemPatch = (idx, patch, saveNow = false) => {
          const fields = Object.keys(patch || {});
          const changesAmount = fields.some(f => ['quantity', 'priceWork', 'priceMaterial'].includes(f));
          const sections = (selectedEstimate.sections || []).map((s, sidx) => sidx === si ? {
            ...s,
            items: (s.items || []).map((it, i) => {
              if (i !== idx) return it;
              const keepImported = it.isImported && changesAmount;
              const next = {...it, ...patch, isImported: keepImported ? true : it.isImported};
              if (next.isImported && changesAmount) {
                const kind = normalizeEstimateItemType(next, s.name);
                const qty = toNum(next.quantity);
                if (kind === 'work' && (fields.includes('quantity') || fields.includes('priceWork'))) {
                  const total = qty * toNum(next.priceWork);
                  next.totalWork = total;
                  next.totalMaterial = 0;
                  next.total = total;
                  next.lineTotal = total;
                  next.currentTotal = total;
                  next.lineTotalSource = 'manual_unit_price';
                } else if (['material', 'equipment', 'transport'].includes(kind) && (fields.includes('quantity') || fields.includes('priceMaterial'))) {
                  const total = qty * toNum(next.priceMaterial);
                  next.totalMaterial = total;
                  next.totalWork = 0;
                  next.total = total;
                  next.lineTotal = total;
                  next.currentTotal = total;
                  next.lineTotalSource = 'manual_unit_price';
                }
              }
              return next;
            })
          } : s);
          const updated = {...selectedEstimate, sections};
          setSelectedEstimate(updated);
          setEstimatesList(prev => prev.map(e => e.id === updated.id ? updated : e));
          if (saveNow) persistEstimate(updated);
          return updated;
        };

        const updateItem = (idx, field, val, saveNow = false) => updateItemPatch(idx, {[field]: val}, saveNow);
        const persist = () => persistEstimate(selectedEstimate);
        const inpCell = {padding: '3px 5px', border: '1px solid ' + C.border, borderRadius: '5px', fontSize: '11px', width: '100%', minWidth: 0, minHeight: '26px', backgroundColor: C.bgWhite, color: C.text, outline: 'none'};
        const estimateTbl = {...tbl, minWidth: isMobile ? '1040px' : '1088px', tableLayout: 'fixed'};
        const estimateTblH = {...tblH, padding: '4px 5px', fontSize: '10px', lineHeight: 1.1, whiteSpace: 'nowrap'};
        const estimateTblC = {...tblC, padding: '3px 5px', fontSize: '11px', lineHeight: 1.15, verticalAlign: 'middle'};
        const stickySumStyle = {position: 'sticky', right: '38px', zIndex: 2, boxShadow: '-8px 0 10px -10px ' + C.textMuted};
        const stickyDeleteStyle = {position: 'sticky', right: 0, zIndex: 2};
        const projBrigades = brigadeContracts.filter(bc => bc.projectName === selectedEstimate.projectName).map(bc => bc.brigadeName).filter(Boolean);
        const canEditExecutionPrice = ['директор', 'зам_директора'].includes(userRole);
        const markSectionBasis = () => {
          const sections = (selectedEstimate.sections || []).map((s, sidx) => sidx === si ? {...s, items: (s.items || []).map(it => isEstimateWorkItem(it, s.name) ? {...it, measurementBasis: estimateMeasurementBasisOf(it, s.name)} : it)} : s);
          const updated = {...selectedEstimate, sections};
          setSelectedEstimate(updated);
          setEstimatesList(prev => prev.map(e => e.id === updated.id ? updated : e));
          persistEstimate(updated);
        };

        const renderGroup = (title, emoji, list, groupTotal, accent) => {
          const mobileGroupLimit = showEstimateIssuesOnly ? (isMobile ? 80 : 180) : (isMobile ? 35 : 90);
          const listKey = ['estimate', selectedEstimate.id, si, title].join(':');
          const mobileListState = mobileExpandedRenderLists[listKey];
          const mobileVisibleLimit = mobileListState === true ? list.length : Number(mobileListState || mobileGroupLimit);
          const groupRows = list.slice(0, mobileVisibleLimit);
          const hiddenRows = list.length - groupRows.length;
          return (
            <div style={{marginBottom: '10px'}}>
              <EstimateItemGroupHeader title={title} emoji={emoji} count={list.length} total={groupTotal} accent={accent} />
              {list.length > 0 ? (
                <div style={{overflowX: 'auto', paddingBottom: '2px'}}>
                  <table style={estimateTbl}>
                    <thead>
                      <tr>
                        <th style={{...estimateTblH, width: '300px'}}>Наименование</th>
                        <th style={{...estimateTblH, width: '78px'}}>Тип</th>
                        <th style={{...estimateTblH, width: '90px'}}>Обмер</th>
                        <th style={{...estimateTblH, width: '44px'}}>Ед.</th>
                        <th style={{...estimateTblH, width: '68px'}}>План</th>
                        <th style={{...estimateTblH, width: '78px'}}>Кому</th>
                        <th style={{...estimateTblH, width: '68px'}}>Сделано</th>
                        <th style={{...estimateTblH, width: '68px'}}>Ост.</th>
                        <th style={{...estimateTblH, width: '86px'}}>Цена</th>
                        <th style={{...estimateTblH, width: '82px'}}>Внутр.</th>
                        <th style={{...estimateTblH, width: '96px', ...stickySumStyle, top: 0, zIndex: 3, backgroundColor: C.bg}}>Сумма</th>
                        <th style={{...estimateTblH, width: '30px', ...stickyDeleteStyle, top: 0, zIndex: 4, backgroundColor: C.bg}}></th>
                      </tr>
                    </thead>
                    <tbody>
                      {groupRows.map(item => {
                        const kind = item._type || itemKind(item);
                        const meta = estimateItemTypeMeta(kind);
                        const isWork = kind === 'work';
                        const basis = estimateMeasurementBasisOf(item, section.name);
                        const basisMeta = estimateMeasurementBasisMeta(isWork ? basis : 'manual');
                        const priceField = isWork ? 'priceWork' : 'priceMaterial';
                        const qty = Number(item.quantity) || 0;
                        const done = isWork ? Number(item.doneQuantity) || 0 : 0;
                        const remain = Math.max(0, qty - done);
                        const qtyNorm = normalizeMeasure(qty, item.unit);
                        const doneNorm = normalizeMeasure(done, item.unit);
                        const rowDomId = estimateIssueDomId(selectedEstimate.id, si, item._idx);
                        const isIssueFocused = estimateIssueFocusKey === rowDomId;
                        const rowStickyBg = isIssueFocused ? C.warningLight : C.bgWhite;
                        const executionPrice = Number(item.executionPricePerUnit || item.internalPricePerUnit || item.masterPricePerUnit || 0);
                        const importedLineTotal = estimateItemTotal(item);
                        const importedUnitPrice = qty > 0 ? importedLineTotal / qty : 0;
                        const importMeta = estimateImportLineMeta(item, qtyNorm);
                        const autoPill = (icon, label, muted = false) => (
                          <div style={{...inpCell, display: 'flex', alignItems: 'center', gap: '4px', fontWeight: '700', color: muted ? C.textMuted : C.text, backgroundColor: C.bg}}>
                            {icon && <span>{icon}</span>}
                            <span style={{overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap'}}>{label}</span>
                          </div>
                        );
                        return (
                          <tr key={item.id || item._idx} id={rowDomId} data-estitem={item.id || item.name || item._idx} style={isIssueFocused ? {outline: '2px solid ' + C.warning, backgroundColor: C.warningLight} : undefined}>
                            <td style={estimateTblC}>
                              <div style={{display: 'flex', alignItems: 'center', gap: '3px'}}>
                                {isWork ? (
                                  <button onClick={() => updateItem(item._idx, 'hiddenWork', !item.hiddenWork, true)} title={item.hiddenWork ? 'По этой работе будет подготовлен АОСР' : 'АОСР не требуется'} style={{border: 'none', background: 'none', cursor: 'pointer', padding: '0 1px', fontSize: '12px', opacity: item.hiddenWork ? 1 : 0.3}}>{item.hiddenWork ? '🔒' : '🔓'}</button>
                                ) : (
                                  <span title={meta.label} style={{fontSize: '12px', width: '16px', textAlign: 'center'}}>{meta.icon}</span>
                                )}
                                <input value={item.name || ''} onChange={e => updateItem(item._idx, 'name', e.target.value)} onBlur={persist} style={inpCell} />
                              </div>
                            </td>
                            <td style={estimateTblC}>{autoPill(meta.icon, meta.label)}</td>
                            <td style={estimateTblC}>{autoPill(basisMeta.icon, isWork ? basisMeta.label : '—', !isWork)}</td>
                            <td style={estimateTblC}>{autoPill('', qtyNorm.unit || item.unit || 'шт')}</td>
                            <td style={estimateTblC}><input type="number" step="any" inputMode="decimal" value={qtyNorm.qty || ''} onChange={e => updateItem(item._idx, 'quantity', denormalizeMeasure(e.target.value, item.unit))} onBlur={persist} style={inpCell} /></td>
                            <td style={estimateTblC}><select disabled={!isWork} value={isWork ? (item.brigadeName || '') : ''} onChange={e => updateItem(item._idx, 'brigadeName', e.target.value, true)} style={{...inpCell, opacity: isWork ? 1 : 0.55}}><option value="">—</option>{projBrigades.map(b => <option key={b} value={b}>{b}</option>)}</select></td>
                            <td style={estimateTblC}><input disabled={!isWork} type="number" step="any" inputMode="decimal" value={isWork ? (doneNorm.qty || '') : ''} onChange={e => {const raw = denormalizeMeasure(e.target.value, item.unit); if (qty > 0 && raw > qty) {alert('Сделано не может быть больше плана (' + fmtMeasure(qty, item.unit) + ')'); return;} updateItem(item._idx, 'doneQuantity', raw);}} onBlur={persist} style={{...inpCell, color: done > 0 ? C.success : C.text, opacity: isWork ? 1 : 0.55}} /></td>
                            <td style={{...estimateTblC, color: isWork ? (qty > 0 && remain === 0 ? C.success : remain > 0 ? C.warning : C.textMuted) : C.textMuted, fontWeight: '600'}}>{isWork && qty > 0 ? fmtMeasure(remain, item.unit) : '—'}</td>
                            <td style={estimateTblC}>{item.isImported ? <div title={importMeta || ''} style={{...inpCell, backgroundColor: C.bg, whiteSpace: 'normal', lineHeight: 1.15}}><b style={{color: C.success}}>{Math.round(importedLineTotal).toLocaleString('ru-RU')} ₽</b><div style={{color: C.textMuted, fontSize: '9px', marginTop: '1px'}}>≈ {importedUnitPrice ? importedUnitPrice.toLocaleString('ru-RU', {maximumFractionDigits: 2}) : 0} ₽/{qtyNorm.unit || item.unit || 'ед.'}</div></div> : <input type="number" step="any" inputMode="decimal" title="Цена за единицу" value={item[priceField] || ''} onChange={e => updateItem(item._idx, priceField, e.target.value)} onBlur={persist} style={inpCell} />}</td>
                            <td style={estimateTblC}>{isWork ? <input disabled={!canEditExecutionPrice} type="number" step="any" inputMode="decimal" title="Внутренняя цена исполнителю за единицу. Если пусто — используется fallback по цене заказчика до настройки пакета." value={item.executionPricePerUnit || ''} onChange={e => updateItemPatch(item._idx, {executionPricePerUnit: e.target.value, executionPriceMode: e.target.value ? 'fixed' : '', executionPricePercent: ''})} onBlur={persist} placeholder="авто" style={{...inpCell, color: executionPrice > 0 ? C.success : C.textMuted, opacity: canEditExecutionPrice ? 1 : 0.65}} /> : <span style={{color: C.textMuted}}>—</span>}</td>
                            <td style={{...estimateTblC, ...stickySumStyle, backgroundColor: rowStickyBg, fontWeight: '700', color: C.success, whiteSpace: 'nowrap', fontSize: '12px'}}>{sumOf(item).toLocaleString('ru-RU') + ' ₽'}</td>
                            <td style={{...estimateTblC, ...stickyDeleteStyle, backgroundColor: rowStickyBg}}><button onClick={() => removeAt(item._idx)} style={{...btnR, padding: '3px 6px'}}><Trash2 size={11} /></button></td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              ) : (
                <EstimateItemGroupEmpty C={C} />
              )}
              {hiddenRows > 0 && <button type="button" onClick={() => setMobileExpandedRenderLists(prev => ({...prev, [listKey]: Math.min(list.length, mobileVisibleLimit + mobileGroupLimit)}))} style={{...btnB, width: '100%', justifyContent: 'center', marginTop: '8px', fontSize: '12px'}}>Показать ещё {Math.min(hiddenRows, mobileGroupLimit)} строк</button>}
            </div>
          );
        };

        return (
          <div key={section.id} style={{...card, marginBottom: '12px'}}>
            <EstimateSectionHeader C={C} btnG={btnG} sectionName={section.name} total={total} onMarkSectionBasis={markSectionBasis} />
            <div style={{padding: '12px 16px'}}>
              {renderGroup('Работы', '🔨', works, totalW, C.accent)}
              {renderGroup('Материалы', '📦', mats, totalM, C.info)}
              {adjustments.length > 0 && renderGroup('Корректировки / исключения', '↕️', adjustments, totalAdjustment, C.warning)}
              {renderGroup('Оборудование / доставка / прочее', '⚙️', others, totalOther, C.textSec)}
              <div style={{display: 'grid', gridTemplateColumns: isMobile ? '1fr 1fr' : 'minmax(240px,2fr) 92px 108px 108px 42px', gap: '6px', marginTop: '10px', alignItems: 'center'}}>
                <input placeholder="Добавить строку вручную: название *" value={newEstimateItem.sectionId === section.id ? newEstimateItem.name : ''} onChange={e => setNewEstimateItem({...newEstimateItem, sectionId: section.id, name: e.target.value})} style={{...inp, marginBottom: 0, fontSize: '12px'}} />
                <input placeholder="Кол-во" type="number" step="any" inputMode="decimal" value={newEstimateItem.sectionId === section.id ? newEstimateItem.quantity : ''} onChange={e => setNewEstimateItem({...newEstimateItem, sectionId: section.id, quantity: e.target.value})} style={{...inp, marginBottom: 0, fontSize: '12px'}} />
                <input placeholder="Цена работ" type="number" step="any" inputMode="decimal" value={newEstimateItem.sectionId === section.id ? newEstimateItem.priceWork : ''} onChange={e => setNewEstimateItem({...newEstimateItem, sectionId: section.id, priceWork: e.target.value})} style={{...inp, marginBottom: 0, fontSize: '12px'}} />
                <input placeholder="Цена мат." type="number" step="any" inputMode="decimal" value={newEstimateItem.sectionId === section.id ? newEstimateItem.priceMaterial : ''} onChange={e => setNewEstimateItem({...newEstimateItem, sectionId: section.id, priceMaterial: e.target.value})} style={{...inp, marginBottom: 0, fontSize: '12px'}} />
                <button onClick={() => {if (!newEstimateItem.name || newEstimateItem.sectionId !== section.id) return; const draft = {id: Date.now(), name: newEstimateItem.name, quantity: newEstimateItem.quantity, priceWork: newEstimateItem.priceWork, priceMaterial: newEstimateItem.priceMaterial}; const item = normalizeEstimateWorkingItem(draft, section.name); const sections = (selectedEstimate.sections || []).map((s, idx) => idx === si ? {...s, items: [...(s.items || []), item]} : s); const updated = {...selectedEstimate, sections}; setSelectedEstimate(updated); setEstimatesList(prev => prev.map(e => e.id === updated.id ? updated : e)); persistEstimate(updated); setNewEstimateItem({sectionId: '', itemType: 'work', name: '', unit: 'м2', quantity: '', priceWork: '', priceMaterial: '', measurementBasis: ''});}} style={{...btnO, padding: '7px 12px'}}><Plus size={13} /></button>
              </div>
            </div>
          </div>
        );
      })}
      {hiddenSections > 0 && <button type="button" onClick={() => setMobileExpandedRenderLists(prev => ({...prev, [sectionListKey]: true}))} style={{...btnB, width: '100%', justifyContent: 'center', marginBottom: '12px', fontSize: '12px'}}>Показать ещё {hiddenSections} разделов сметы</button>}
    </>
  );
}
