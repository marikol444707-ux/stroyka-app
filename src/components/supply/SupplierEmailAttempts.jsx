import React, { useRef, useState } from 'react';

const outcomes = { accepted: 'Передано SMTP', rejected: 'Подтверждённый отказ', unconfirmed: 'Результат не подтверждён — повтор отключён' };
const reasons = { smtp_accepted: 'Сервер принял письмо', smtp_rejected: 'Сервер отклонил письмо', recipient_rejected: 'Получатель отклонён сервером', connection_or_auth_failed: 'Не удалось подключиться или войти на почтовый сервер', acknowledgement_unknown: 'Нет подтверждения результата передачи' };

export default function SupplierEmailAttempts({ row, API = '', onRefresh, canRetry = false }) {
  const busy = useRef(false);
  const [state, setState] = useState({ pending: false, error: '' });
  const attempts = Array.isArray(row.emailAttempts) ? row.emailAttempts : [];
  async function retry() {
    if (busy.current) return;
    busy.current = true;
    setState({ pending: true, error: '' });
    try {
      const response = await fetch(API + '/supply-requests/' + row.requestId + '/recipients/' + row.id + '/retry-email', {
        method: 'POST', headers: { 'Content-Type': 'application/json', 'X-Company-Id': String(row.companyId), 'X-Company-Mode': 'company' },
        body: JSON.stringify({ expectedAttemptId: row.emailRetryAttemptId }),
      });
      const data = await response.json().catch(() => null);
      if (!response.ok || data?.ok !== true) throw new Error(typeof data?.detail === 'string' ? data.detail : 'Результат повтора неизвестен. Обновите уведомления.');
      setState({ pending: false, error: '' });
      onRefresh?.();
    } catch (error) {
      setState({ pending: false, error: error.message || 'Результат неизвестен. Обновите уведомления.' });
    } finally { busy.current = false; }
  }
  return <div>
    {attempts.length > 0 && <details><summary>Попытки email ({attempts.length}{attempts.length === 20 ? ', последние' : ''})</summary>
      <ul>{attempts.map(attempt => <li key={attempt.id}>
        <time dateTime={attempt.startedAt}>{new Date(attempt.startedAt).toLocaleString('ru-RU')}</time>{' — '}
        {outcomes[attempt.outcome] || 'Неизвестный результат'}{'. '}{reasons[attempt.code] || 'Подробности недоступны'}
      </li>)}</ul>
    </details>}
    {canRetry && row.emailRetryAttemptId && <button type="button" onClick={retry} disabled={state.pending}>
      {state.pending ? 'Ставим в очередь…' : 'Повторить email после отказа'}
    </button>}
    {state.error && <p role="alert">{state.error}</p>}
  </div>;
}
