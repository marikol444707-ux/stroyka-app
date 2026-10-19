import React, {useRef, useState} from 'react';
export default function MovementRecoveryNotice({recovery, onResume}) {
  const [busy, setBusy] = useState(false);
  const latest = useRef(recovery.key);
  latest.current = recovery.key;
  const run = async action => {
    if (busy) return;
    const key = recovery.key;
    setBusy(true);
    try { await action(); } finally { if (latest.current === key) setBusy(false); }
  };
  if (!recovery.blocked) return null;
  return <section aria-label="Восстановление перемещения" role="status">
    <p>{recovery.loading ? 'Проверяем незавершённые перемещения…' : recovery.error || 'Есть незавершённое перемещение. Сначала проверьте его результат.'}</p>
    {!recovery.loading && <button type="button" disabled={busy} onClick={() => run(recovery.refresh)}>Проверить результат</button>}
    {recovery.drafts.map(draft => <div key={draft.draftId}>
      <p>{draft.restricted ? 'Доступ к исходным данным изменился. Можно безопасно закрыть неисполненные позиции.' : 'Подтверждённые позиции повторно не перемещаются.'}</p>
      {!draft.restricted && <button type="button" disabled={busy || recovery.loading} onClick={() => run(() => onResume(draft))}>Продолжить перемещение</button>}
      <button type="button" disabled={busy || recovery.loading} onClick={() => run(() => recovery.cancel(draft))}>Отменить неисполненные позиции</button>
    </div>)}
  </section>;
}
