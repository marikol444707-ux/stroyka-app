import React from 'react';
import { MAX_IMPORT_BYTES, prepareCatalogImport, catalogItemKey, catalogResponse } from './supplierCatalogImportUtils';

export default function SupplierCatalogImport({ API, supplierId, supplierName, priceUrl, catalog, onSaved, buttonStyle, mutationLock }) {
  const [preview, setPreview] = React.useState(null);
  const [busy, setBusy] = React.useState(false);
  const [message, setMessage] = React.useState('');
  const running = React.useRef(false);
  const fallbackLock = React.useRef(false);
  const lock = mutationLock || fallbackLock;
  const active = React.useRef(true);
  React.useEffect(() => { active.current = true; return () => { active.current = false; }; }, []);

  async function readFile(file) {
    if (!file || running.current) return;
    running.current = true; setBusy(true); setPreview(null); setMessage('');
    try {
      if (!supplierId) throw new Error('Сначала свяжите учётную запись с карточкой поставщика');
      if (file.size > MAX_IMPORT_BYTES) throw new Error('Размер файла — не более 5 МБ');
      const bytes = await new Promise((resolve, reject) => {
        const reader = new FileReader();
        reader.onload = () => resolve(reader.result);
        reader.onerror = () => reject(new Error('Не удалось прочитать файл'));
        reader.onabort = () => reject(new Error('Чтение файла прервано'));
        reader.readAsArrayBuffer(file);
      });
      const XLSX = await import('xlsx');
      const workbook = XLSX.read(bytes, { type: 'array', sheetRows: 503, raw: true, codepage: 65001 });
      const sheet = workbook.Sheets[workbook.SheetNames[0]];
      if (!sheet) throw new Error('В файле нет листов');
      if (sheet['!fullref'] && XLSX.utils.decode_range(sheet['!fullref']).e.r > 500) throw new Error('Не более 500 позиций в одном файле');
      const rows = XLSX.utils.sheet_to_json(sheet, { header: 1, defval: '' });
      const plan = prepareCatalogImport(rows, catalog, supplierId);
      if (active.current) setPreview({ ...plan, rows, name: file.name });
    } catch (error) { if (active.current) setMessage(error.message); }
    finally { running.current = false; if (active.current) setBusy(false); }
  }

  async function readLink() {
    if (running.current) return;
    running.current = true; setBusy(true); setPreview(null); setMessage('');
    let file;
    try {
      const url = new URL(priceUrl);
      if (!['http:', 'https:'].includes(url.protocol)) throw new Error('Для прайса нужна ссылка http или https');
      const response = await fetch('https://corsproxy.io/?' + encodeURIComponent(url.href));
      if (!response.ok) throw new Error(`Не удалось загрузить прайс (${response.status})`);
      const blob = await response.blob();
      file = new File([blob], 'Прайс по ссылке');
    } catch (error) { if (active.current) setMessage(error.message); }
    finally { running.current = false; if (active.current) setBusy(false); }
    if (file && active.current) await readFile(file);
  }

  async function save() {
    if (running.current || !preview || preview.errors.length || !preview.items.length) return;
    if (lock.current) { setMessage('Дождитесь завершения другой операции с каталогом.'); return; }
    lock.current = true;
    running.current = true; setBusy(true); setMessage('');
    let count = 0, row = null;
    try {
      const existing = await catalogResponse(await fetch(API + '/supplier-catalog', { cache: 'no-store' }));
      if (!Array.isArray(existing)) throw new Error('Не удалось проверить текущий каталог');
      const plan = prepareCatalogImport(preview.rows, existing, supplierId);
      if (plan.errors.length) throw new Error(plan.errors[0]);
      for (const entry of plan.items) {
        if (!active.current) return;
        row = entry.row;
        const item = { ...entry.item, supplierId, supplierName };
        const saved = await catalogResponse(await fetch(API + '/supplier-catalog', {
          method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(item),
        }), true);
        count++;
        if (active.current) onSaved(previous => previous.some(value => value.id === saved.id) ? previous : [...previous, { ...item, id: saved.id }]);
      }
      if (active.current) { setMessage(`Импортировано: ${count}. Пропущено совпадений: ${plan.skipped}.`); setPreview(null); }
    } catch (error) {
      if (active.current) {
        setMessage(`Подтверждено сохранений: ${count}. ${row ? `Строка ${row}: ` : ''}${error.message}. Импорт остановлен. Перед повторной загрузкой обновите страницу и проверьте каталог: последняя строка могла сохраниться.`);
        // Never automatically retry a POST whose outcome may be unknown.
        setPreview(null);
      }
    } finally { lock.current = false; running.current = false; if (active.current) setBusy(false); }
  }

  return <div style={{ marginBottom: 12, overflowWrap: 'anywhere' }}>
    <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8, alignItems: 'center' }}>
      <label style={{ ...buttonStyle, display: 'flex', flexDirection: 'column', alignItems: 'flex-start', minWidth: 0, maxWidth: '100%', boxSizing: 'border-box' }}>📥 Excel / CSV
        <input aria-label="Файл каталога" type="file" accept=".xlsx,.xls,.csv" disabled={busy || !supplierId}
          onChange={event => { const file = event.target.files[0]; event.target.value = ''; readFile(file); }}
          style={{ display: 'block', width: '100%', minWidth: 0, maxWidth: '100%', marginTop: 4 }} />
      </label>
      {priceUrl && <button style={buttonStyle} disabled={busy || !supplierId} onClick={readLink}>По ссылке</button>}
      {busy && <span role="status">Обработка каталога…</span>}
    </div>
    <p style={{ fontSize: 12 }}>Первый лист, первая строка — заголовки: Наименование; Ед.; Цена; Мин. партия; Поставка; Примечание. До 500 позиций, 5 МБ. CSV — в UTF-8.</p>
    {!supplierId && <p role="alert">Сначала свяжите учётную запись с карточкой поставщика.</p>}
    {message && <p role="status">{message}</p>}
    {preview && <div style={{ padding: 12, border: '1px solid #94a3b8', borderRadius: 8 }}>
      <b>{preview.name}</b>
      <p>К добавлению: {preview.items.length}. Пропущено совпадений: {preview.skipped}.</p>
      <p style={{ fontSize: 12 }}>Совпадения по названию и единице измерения пропускаются. Цены существующих позиций не меняются.</p>
      {preview.errors.length > 0 ? <div role="alert"><b>Исправьте ошибки в файле:</b><ul>
        {preview.errors.slice(0, 20).map(error => <li key={error}>{error}</li>)}
        {preview.errors.length > 20 && <li>Ещё ошибок: {preview.errors.length - 20}</li>}
      </ul></div> : <ul>{preview.items.slice(0, 5).map(({ row, item }) => <li key={catalogItemKey(item)}>Строка {row}: {item.materialName}, {item.price.toLocaleString('ru-RU')} ₽ / {item.unit}</li>)}</ul>}
      <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
        <button style={buttonStyle} disabled={busy || !!preview.errors.length || !preview.items.length} onClick={save}>Импортировать {preview.items.length} позиций</button>
        <button style={buttonStyle} disabled={busy} onClick={() => setPreview(null)}>Отмена</button>
      </div>
    </div>}
  </div>;
}
