import { useEffect, useRef, useState } from 'react';
import { catalogItemKey, catalogResponse, normalizeCatalogItem } from './supplierCatalogImportUtils';

export default function useSupplierCatalogActions({ API, actorId, supplierId, supplierName, setCatalog, onCreated, mutationLock }) {
  const fallbackLock = useRef(false);
  const lock = mutationLock || fallbackLock;
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const scope = `${actorId}:${supplierId}`;
  const state = useRef({ scope, generation: 0, busy: false, mounted: true });
  if (state.current.scope !== scope) {
    state.current = { ...state.current, scope, generation: state.current.generation + 1, busy: false };
  }
  useEffect(() => { setBusy(false); setError(''); }, [scope]);
  useEffect(() => {
    state.current.mounted = true;
    return () => { state.current.mounted = false; state.current.generation++; };
  }, []);

  async function run(action) {
    if (state.current.busy) return;
    if (lock.current) { setError('Дождитесь завершения другой операции с каталогом.'); return; }
    lock.current = true;
    state.current.busy = true; setBusy(true); setError('');
    const generation = state.current.generation;
    const current = () => state.current.mounted && state.current.generation === generation;
    try {
      if (!supplierId) throw new Error('Сначала свяжите учётную запись с карточкой поставщика');
      await action(current);
    } catch (failure) {
      if (current()) setError(failure.message);
    } finally {
      lock.current = false;
      if (current()) { state.current.busy = false; setBusy(false); }
    }
  }

  const create = draft => run(async current => {
    const item = { ...normalizeCatalogItem(draft), supplierId, supplierName };
    const existing = await catalogResponse(await fetch(API + '/supplier-catalog', { cache: 'no-store' }));
    if (!current()) return;
    if (!Array.isArray(existing)) throw new Error('Не удалось проверить текущий каталог');
    if (existing.some(row => String(row.supplierId) === String(supplierId) && catalogItemKey(row) === catalogItemKey(item))) {
      throw new Error('Позиция с таким названием и единицей уже есть в каталоге. Обновите страницу, чтобы увидеть её.');
    }
    let saved;
    try {
      saved = await catalogResponse(await fetch(API + '/supplier-catalog', {
        method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(item),
      }), true);
    } catch (failure) {
      throw new Error(`${failure.message}. Сохранение не подтверждено. Проверьте каталог перед повторной попыткой.`);
    }
    if (!current()) return;
    setCatalog(previous => [...previous, { ...item, id: saved.id }]);
    onCreated();
  });
  const remove = id => run(async current => {
    const result = await catalogResponse(await fetch(API + '/supplier-catalog/' + id, { method: 'DELETE' }));
    if (result?.ok !== true) throw new Error('Сервер не подтвердил удаление. Обновите каталог.');
    if (current()) setCatalog(previous => previous.filter(item => item.id !== id));
  });
  return { busy, error, create, remove };
}
