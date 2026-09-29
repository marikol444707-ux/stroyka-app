import React, { useEffect, useState } from 'react';
import { abandonRejectedWorkTail, clearWorkBatch, pendingWorkBatch, resumeWorkBatch, workBatchScope } from './workCommands';
import { workMaterialAccountingEnabled } from './materialSources';

export default function WorkSubmissionRecovery({ API, companyContext, user, C, onRecovered }) {
  const [pending, setPending] = useState(null);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const companyId = companyContext?.selectedCompanyId;
  const userId = user?.id;
  useEffect(() => {
    if (!workMaterialAccountingEnabled() || !companyId || !userId) return;
    const load = () => {
      try { setPending(pendingWorkBatch({ companyId, userId })); setError(''); }
      catch (_) { setError('Не удалось прочитать сохранённую отправку. Требуется сверка журнала.'); }
    };
    load();
    window.addEventListener('work-material-batch-change', load);
    return () => window.removeEventListener('work-material-batch-change', load);
  }, [companyId, userId]);
  if (!pending && !error) return null;
  return <section aria-label="Сохранённая отправка" style={{padding:'12px',marginBottom:'12px',border:'1px solid '+C.warning,borderRadius:'8px',color:C.text,background:C.bg}}>
    <b>Есть сохранённая отправка</b>
    <p>Повтор использует исходные данные. Уже сохранённые работы, расход и денежные операции повторно не проводятся.</p>
    {pending && <p>Подтверждено отправок: {pending.next} из {pending.commands.length}.</p>}
    {error && <p role="alert" style={{color:C.danger}}>{error}</p>}
    {pending && <button type="button" disabled={busy} onClick={async () => {
      setBusy(true); setError('');
      const scope = workBatchScope(companyContext, user);
      try {
        const completed = await resumeWorkBatch({ API, scope });
        await onRecovered?.(completed);
        clearWorkBatch(scope);
      } catch (e) { setError(e.message || 'Не удалось подтвердить отправку.'); }
      finally { setBusy(false); }
    }}>{busy ? 'Проверяем отправку…' : 'Повторить сохранённую отправку'}</button>}
    {pending?.rejected && <button type="button" disabled={busy} onClick={async () => {
      setBusy(true); setError('');
      try {
        await onRecovered?.(pending);
        abandonRejectedWorkTail(workBatchScope(companyContext, user));
      } catch (e) { setError(e.message); }
      finally { setBusy(false); }
    }}>Снять отклонённые строки с отправки</button>}
  </section>;
}
