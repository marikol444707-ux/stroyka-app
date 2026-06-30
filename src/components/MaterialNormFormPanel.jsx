import React from 'react';
import { Check, X } from 'lucide-react';
import { UNITS } from '../constants/catalogs';
import { C, btnG, btnO, card, inp } from '../constants/uiTheme';

export default function MaterialNormFormPanel({
  editingMaterialNormId,
  newMaterialNorm,
  setNewMaterialNorm,
  saveMaterialNorm,
  resetMaterialNormForm,
  isMobile,
}) {
  return (
    <div style={{...card, padding: '16px', marginBottom: '16px'}}>
      <b style={{color: C.text, fontSize: '13px', display: 'block', marginBottom: '10px'}}>
        {editingMaterialNormId ? 'Редактировать норму' : 'Новая норма'}
      </b>
      <div style={{display: 'grid', gridTemplateColumns: isMobile ? '1fr' : '1fr 1fr 1fr', gap: '10px'}}>
        <input placeholder="Код нормы (например plaster_mix)" value={newMaterialNorm.ruleKey} onChange={e => setNewMaterialNorm({...newMaterialNorm, ruleKey: e.target.value})} style={{...inp, marginBottom: 0}} />
        <input placeholder="Название материала" value={newMaterialNorm.name} onChange={e => setNewMaterialNorm({...newMaterialNorm, name: e.target.value})} style={{...inp, marginBottom: 0}} />
        <input placeholder="Расход на единицу" type="number" step="any" inputMode="decimal" value={newMaterialNorm.qtyPerUnit} onChange={e => setNewMaterialNorm({...newMaterialNorm, qtyPerUnit: e.target.value})} style={{...inp, marginBottom: 0}} />
        <select value={newMaterialNorm.workUnit} onChange={e => setNewMaterialNorm({...newMaterialNorm, workUnit: e.target.value})} style={{...inp, marginBottom: 0}}>{UNITS.map(u => <option key={u}>{u}</option>)}</select>
        <select value={newMaterialNorm.materialUnit} onChange={e => setNewMaterialNorm({...newMaterialNorm, materialUnit: e.target.value})} style={{...inp, marginBottom: 0}}>{UNITS.map(u => <option key={u}>{u}</option>)}</select>
        <input placeholder="База слоя, мм" type="number" step="any" inputMode="decimal" value={newMaterialNorm.thicknessBaseMm} onChange={e => setNewMaterialNorm({...newMaterialNorm, thicknessBaseMm: e.target.value})} style={{...inp, marginBottom: 0}} />
        <textarea placeholder="Ключевые слова работы: штукатур, стяжк..." value={newMaterialNorm.workText} onChange={e => setNewMaterialNorm({...newMaterialNorm, workText: e.target.value})} style={{...inp, marginBottom: 0, minHeight: '72px', resize: 'vertical'}} />
        <textarea placeholder="Ключевые слова материала: ротбанд, гипсов..." value={newMaterialNorm.materialText} onChange={e => setNewMaterialNorm({...newMaterialNorm, materialText: e.target.value})} style={{...inp, marginBottom: 0, minHeight: '72px', resize: 'vertical'}} />
        <textarea placeholder="Исключить работы: демонтаж, разбор..." value={newMaterialNorm.blockWorkText} onChange={e => setNewMaterialNorm({...newMaterialNorm, blockWorkText: e.target.value})} style={{...inp, marginBottom: 0, minHeight: '72px', resize: 'vertical'}} />
        <input placeholder="Типовой слой, мм" type="number" step="any" inputMode="decimal" value={newMaterialNorm.defaultThicknessMm} onChange={e => setNewMaterialNorm({...newMaterialNorm, defaultThicknessMm: e.target.value})} style={{...inp, marginBottom: 0}} />
        <input placeholder="Подпись нормы" value={newMaterialNorm.label} onChange={e => setNewMaterialNorm({...newMaterialNorm, label: e.target.value})} style={{...inp, marginBottom: 0, gridColumn: isMobile ? 'auto' : 'span 2'}} />
      </div>
      <div style={{display: 'flex', gap: '8px', marginTop: '12px', flexWrap: 'wrap'}}>
        <button onClick={saveMaterialNorm} style={btnO}><Check size={14} />{editingMaterialNormId ? 'Сохранить' : 'Добавить'}</button>
        {editingMaterialNormId && <button onClick={resetMaterialNormForm} style={btnG}><X size={14} />Отмена</button>}
      </div>
    </div>
  );
}
