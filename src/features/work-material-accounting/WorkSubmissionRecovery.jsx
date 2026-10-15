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
    setPending(null);
    setError('');
    if (!workMaterialAccountingEnabled() || !companyId || !userId) return;
    const load = () => {
      try { setPending(pendingWorkBatch({ companyId, userId })); setError(''); }
      catch (_) { setPending(null); setError('Не удалось открыть сохранённую отправку. Проверьте журнал перед новой отправкой.'); }
    };
    load();
    window.addEventListener('work-material-batch-change', load);
    return () => window.removeEventListener('work-material-batch-change', load);
  }, [companyId, userId]);
  if (!pending && !error) return null;
  return <section aria-label="Сохранённая отправка" style={{padding:'12px',marginBottom:'12px',border:'1px solid '+C.warning,borderRadius:'8px',color:C.text,background:C.bg}}>
    <b>Нужно проверить результат отправки</b>
    <p>Данные сохранены. Нажмите «Завершить отправку», чтобы проверить результат и отправить оставшееся. Уже сохранённое повторно не добавится.</p>
    {pending && <p>Сохранено: {pending.next} из {pending.commands.length}.</p>}
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
    }} style={{minHeight:44,padding:'10px 14px'}}>{busy ? 'Проверяем отправку…' : 'Завершить отправку'}</button>}
    {pending?.rejected && <p>Сервер отклонил оставшиеся данные. Можно вернуться к их исправлению. Уже сохранённое останется в журнале.</p>}
    {pending?.rejected && <button type="button" disabled={busy} onClick={async () => {
      setBusy(true); setError('');
      try {
        await onRecovered?.(pending);
        abandonRejectedWorkTail(workBatchScope(companyContext, user));
      } catch (e) { setError(e.message); }
      finally { setBusy(false); }
    }} style={{minHeight:44,padding:'10px 14px',marginLeft:8}}>Вернуться к исправлению</button>}
  </section>;
}
