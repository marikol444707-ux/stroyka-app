import React from 'react';

export function createSupplyPlanningUi({
  C,
  btnB,
  btnG,
  projects,
  user,
  navigateTo,
  setExpandedProject,
  setActiveProjectTab,
  setActiveTabGroup,
  setWarehouseTab,
  supplyRequestOrigin,
  newSupplyReq,
  setNewSupplyReq,
  materialReconciliationRows,
  canonicalMaterialMeta,
  isSameSupplyMaterial,
  supplyUnitKey,
  toNum,
  fmtMeasure,
}) {
  const openProjectMaterialControl = (projectName) => {
    const project = (projects || []).find(p => p.name === projectName);
    if (project) {
      navigateTo('projects');
      setExpandedProject(project.id);
      setActiveProjectTab('Материалы');
      setActiveTabGroup(user?.role === 'прораб' ? 'object' : 'finance');
    } else {
      navigateTo('warehouse');
      setWarehouseTab('control');
    }
  };

  const renderSupplyRequestOrigin = (req, opts = {}) => {
    const origin = supplyRequestOrigin(req);
    if (!origin) return null;
    const color = origin.type === 'material-control' ? C.warning : C.info;
    const bg = origin.type === 'material-control' ? C.warningLight : C.infoLight;
    const borderColor = origin.type === 'material-control' ? C.warningBorder : C.infoBorder;
    const compact = !!opts.compact;
    return (
      <div style={{ marginTop: compact ? '6px' : '8px', padding: compact ? '7px 9px' : '9px 11px', border: '1.5px solid ' + borderColor, borderRadius: '8px', backgroundColor: bg }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: '8px', flexWrap: 'wrap' }}>
          <b style={{ color, fontSize: compact ? '11px' : '12px' }}>{origin.label}</b>
          {origin.projectName && (
            <button
              onClick={e => { e.stopPropagation(); openProjectMaterialControl(origin.projectName); }}
              style={{ ...btnG, padding: compact ? '3px 7px' : '4px 9px', fontSize: compact ? '10px' : '11px' }}
            >
              Открыть контроль
            </button>
          )}
        </div>
        {!compact && origin.facts.length > 0 && (
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit,minmax(130px,1fr))', gap: '5px 10px', marginTop: '7px' }}>
            {origin.facts.slice(0, 6).map(([k, v]) => (
              <div key={k} style={{ fontSize: '11px', color: C.textSec }}>
                <span style={{ color: C.textMuted }}>{k}: </span>
                <b style={{ color: C.text, fontWeight: '600' }}>{v}</b>
              </div>
            ))}
          </div>
        )}
        {compact && origin.facts.length > 0 && (
          <p style={{ color: C.textSec, margin: '4px 0 0', fontSize: '11px' }}>
            {origin.facts.slice(-2).map(([k, v]) => k + ': ' + v).join(' · ')}
          </p>
        )}
      </div>
    );
  };

  const supplyPlanningHint = (it, idx) => {
    const projectName = newSupplyReq.project;
    const materialName = (it?.materialName || '').trim();
    if (!projectName || !materialName) return null;
    const rows = materialReconciliationRows(projectName);
    const canonicalName = canonicalMaterialMeta(projectName, materialName).name;
    const row = rows.find(r => isSameSupplyMaterial(r.name, canonicalName) || isSameSupplyMaterial(r.name, materialName));
    const sameUnit = !row?.unit || !it?.unit || supplyUnitKey(row.unit) === supplyUnitKey(it.unit);
    const draftOther = (newSupplyReq.items || [])
      .filter((x, i) => i !== idx && isSameSupplyMaterial(x.materialName, materialName))
      .reduce((sum, x) => sum + toNum(x.quantity), 0);
    const planQty = toNum(row?.planQty);
    const supplied = toNum(row?.supplied);
    const stock = toNum(row?.stock);
    const ordered = toNum(row?.requested);
    const inTransit = toNum(row?.inTransit);
    const requested = toNum(it?.quantity);
    const unit = row?.unit || it?.unit || 'шт';
    const recommended = row && planQty > 0 && sameUnit ? Math.max(0, toNum(row.toBuy) - draftOther) : null;
    const outsideEstimate = !row || planQty <= 0;
    const tooMuch = recommended !== null && requested > 0 && requested > recommended + 0.0001;
    return { row, unit, sameUnit, planQty, supplied, stock, ordered, inTransit, draftOther, requested, recommended, outsideEstimate, tooMuch };
  };

  const applySupplyRecommendedQty = (idx, hint) => {
    if (!hint || hint.recommended === null) return;
    const qty = Number(hint.recommended.toFixed(3));
    const items = [...(newSupplyReq.items || [])];
    items[idx] = { ...items[idx], quantity: String(qty), unit: hint.unit || items[idx].unit || 'шт' };
    setNewSupplyReq({ ...newSupplyReq, items });
  };

  const renderSupplyPlanningHint = (it, idx) => {
    const hint = supplyPlanningHint(it, idx);
    if (!hint) return null;
    const pill = (label, value, color = C.text) => (
      <span style={{ padding: '4px 7px', borderRadius: '8px', backgroundColor: C.bgWhite, border: '1px solid ' + C.border, color, fontSize: '11px', whiteSpace: 'nowrap' }}>
        {label}: <b>{value}</b>
      </span>
    );
    return (
      <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap', alignItems: 'center', margin: '0 0 8px 2px', padding: '7px 8px', backgroundColor: hint.outsideEstimate ? C.warningLight : C.successLight, border: '1px solid ' + (hint.outsideEstimate ? C.warningBorder : C.successBorder), borderRadius: '8px' }}>
        {hint.outsideEstimate
          ? <span style={{ fontSize: '11px', color: C.warning, fontWeight: '700' }}>⚠️ Материала нет в активной смете</span>
          : pill('По смете', fmtMeasure(hint.planQty, hint.unit), C.text)}
        {pill('Поставлено', fmtMeasure(hint.supplied, hint.unit), hint.supplied > 0 ? C.success : C.textSec)}
        {pill('На объекте', fmtMeasure(hint.stock, hint.unit), hint.stock > 0 ? C.success : C.textSec)}
        {hint.ordered > 0 && pill('Уже в заявках', fmtMeasure(hint.ordered, hint.unit), C.info)}
        {hint.inTransit > 0 && pill('В пути', fmtMeasure(hint.inTransit, hint.unit), C.warning)}
        {hint.draftOther > 0 && pill('В этой заявке ещё', fmtMeasure(hint.draftOther, hint.unit), C.info)}
        {hint.recommended !== null && pill('Докупить', fmtMeasure(hint.recommended, hint.unit), hint.recommended > 0 ? C.warning : C.success)}
        {!hint.sameUnit && <span style={{ fontSize: '11px', color: C.danger, fontWeight: '700' }}>Ед. изм. отличается от сметы</span>}
        {hint.tooMuch && <span style={{ fontSize: '11px', color: C.danger, fontWeight: '700' }}>Заявка больше расчётной потребности</span>}
        {hint.recommended !== null && hint.recommended > 0 && (
          <button onClick={() => applySupplyRecommendedQty(idx, hint)} style={{ ...btnB, padding: '3px 7px', fontSize: '11px' }}>
            Подставить {fmtMeasure(hint.recommended, hint.unit)}
          </button>
        )}
      </div>
    );
  };

  return {
    renderSupplyPlanningHint,
    renderSupplyRequestOrigin,
  };
}
