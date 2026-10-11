import React, { useEffect, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import './ProjectBrigadeWorkEntryPanel.css';
import { Plus } from 'lucide-react';
import { API } from '../api';

const emptyBrigadeItem = (workPackage = 'Основная') => ({
  name: '',
  unit: 'м',
  quantity: '',
  priceSmeta: '',
  priceBrigade: '',
  estimateSection: '',
  workPackage,
  estimateItemKey: '',
});

export default function ProjectBrigadeWorkEntryPanel({
  selectedBrigadeContract,
  newBrigadeItem,
  setNewBrigadeItem,
  setBrigadeContractItems,
  UNITS = [],
  C,
  card,
  inp,
  btnO,
  showLeadership = false,
}) {
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const sending = useRef(false);
  const dialog = useRef(null);
  const currentContract = useRef(selectedBrigadeContract?.id);
  currentContract.current = selectedBrigadeContract?.id;
  useEffect(() => { setOpen(false); setError(''); }, [selectedBrigadeContract?.id]);
  useEffect(() => {
    if (!open) return undefined;
    const previous = document.activeElement;
    const overflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    dialog.current?.querySelector('input')?.focus();
    return () => { document.body.style.overflow = overflow; previous?.focus(); };
  }, [open]);
  if (!showLeadership) return null;
  const itemWorkPackage = selectedBrigadeContract?.workPackage || selectedBrigadeContract?.work_package || newBrigadeItem.workPackage || 'Основная';
  const addManualItem = async () => {
    if (sending.current || !newBrigadeItem.name.trim() || !selectedBrigadeContract) return;
    sending.current = true; setBusy(true); setError('');
    const item = {...newBrigadeItem, workPackage: itemWorkPackage, contractId: selectedBrigadeContract.id, doneQuantity: 0, status: 'Не начато'};
    try {
      const res = await fetch(API + '/brigade-contract-items', {
        method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(item),
      });
      const saved = await res.json();
      if (!res.ok || !saved.id) throw new Error(typeof saved.detail === 'string' ? saved.detail : 'Не удалось сохранить работу.');
      if (currentContract.current !== item.contractId) return;
      setBrigadeContractItems(prev => [...prev, {...item, id: saved.id}]);
      setNewBrigadeItem(emptyBrigadeItem(itemWorkPackage));
      setOpen(false);
    } catch (failure) {
      if (currentContract.current === item.contractId) setError(failure.message || 'Не удалось сохранить работу.');
    }
    finally { sending.current = false; setBusy(false); }
  };
  const keyDown = event => {
    if (event.key === 'Escape' && !sending.current) setOpen(false);
    if (event.key !== 'Tab') return;
    const nodes = [...dialog.current.querySelectorAll('button,input,select')].filter(node => !node.disabled);
    const first = nodes[0], last = nodes[nodes.length - 1];
    if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last?.focus(); }
    else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first?.focus(); }
  };
  return <>
    <button type="button" style={{...btnO, minHeight: 44, marginBottom: 16}} onClick={() => { setError(''); setOpen(true); }}>
      <Plus size={16}/>Добавить работу вручную
    </button>
    {open && createPortal(<div className="brigade-work-entry-backdrop">
      <form className="brigade-work-entry-dialog" role="dialog" aria-modal="true" aria-labelledby="manual-work-title"
        ref={dialog} onKeyDown={keyDown} onSubmit={event => { event.preventDefault(); addManualItem(); }}
        style={{...card, color: C.text, background: C.bgWhite || 'var(--c-bg-white, #fff)'}}>
        <header><h2 id="manual-work-title">Новая работа</h2><button type="button" disabled={busy} onClick={() => setOpen(false)} style={btnO}>Закрыть</button></header>
        <fieldset disabled={busy}>
          <label>Наименование работы<input required value={newBrigadeItem.name} onChange={e => setNewBrigadeItem({...newBrigadeItem, name: e.target.value})} style={inp}/></label>
          <div className="brigade-work-entry-fields">
            <label>Единица измерения<select value={newBrigadeItem.unit} onChange={e => setNewBrigadeItem({...newBrigadeItem, unit: e.target.value})} style={inp}>{UNITS.map(unit => <option key={unit}>{unit}</option>)}</select></label>
            <label>Объём<input required type="number" min="0.000001" step="any" inputMode="decimal" value={newBrigadeItem.quantity} onChange={e => setNewBrigadeItem({...newBrigadeItem, quantity: e.target.value})} style={inp}/></label>
            <label>Цена по смете, ₽/ед.<input type="number" min="0" step="any" inputMode="decimal" value={newBrigadeItem.priceSmeta} onChange={e => setNewBrigadeItem({...newBrigadeItem, priceSmeta: e.target.value})} style={inp}/></label>
            <label>Цена исполнителю, ₽/ед.<input type="number" min="0" step="any" inputMode="decimal" value={newBrigadeItem.priceBrigade} onChange={e => setNewBrigadeItem({...newBrigadeItem, priceBrigade: e.target.value})} style={inp}/></label>
          </div>
          <p>Раздел работ: {itemWorkPackage}</p>
          {error && <p role="alert">{error}</p>}
        </fieldset>
        <footer><button type="submit" disabled={busy || !selectedBrigadeContract} style={btnO}>{busy ? 'Сохраняем…' : 'Добавить работу'}</button></footer>
      </form>
    </div>, document.body)}
  </>;
}
