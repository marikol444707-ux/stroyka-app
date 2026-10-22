import React from 'react';

export default function CompanyFeaturesPanel({ data, API = '', C = {}, sendJson, onReload }) {
  const [search, setSearch] = React.useState('');
  const [drafts, setDrafts] = React.useState({});
  const [savingId, setSavingId] = React.useState(null);
  const [error, setError] = React.useState('');
  const companies = Array.isArray(data?.companies) ? data.companies : [];
  const visibleCompanies = companies.filter(company =>
    (String(company.companyName || '') + ' ' + String(company.inn || '') + ' ' + String(company.platformAccountName || ''))
      .toLowerCase().includes(search.trim().toLowerCase())
  );
  const card = {
    background: C.card || C.surface || '#fff',
    border: '1px solid ' + (C.border || '#d0d5dd'),
    borderRadius: 12,
    padding: 14,
  };
  const input = {
    border: '1px solid ' + (C.border || '#d0d5dd'),
    borderRadius: 8,
    padding: '8px 10px',
    color: C.text || '#101828',
    background: C.bg || '#fff',
    font: 'inherit',
  };
  const getDraft = company => drafts[company.companyId] || {
    enabled: company.enabled,
    monthlyFee: company.monthlyFee || '0.00',
    searchTerms: Array.isArray(company.searchTerms) ? company.searchTerms.join(', ') : '',
  };
  const updateDraft = (company, patch) => setDrafts(current => ({
    ...current,
    [company.companyId]: { ...getDraft(company), ...patch },
  }));

  const save = async company => {
    const draft = getDraft(company);
    setSavingId(company.companyId);
    setError('');
    try {
      const response = await sendJson(API + '/system/companies/' + company.companyId + '/features/jev', {
        method: 'PUT',
        body: JSON.stringify({
          enabled: draft.enabled,
          monthlyFee: draft.monthlyFee,
          searchTerms: String(draft.searchTerms || '').split(/[,;\n]+/).map(term => term.trim()).filter(Boolean),
        }),
      });
      const result = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(result.detail || 'Не удалось сохранить подключение');
      setDrafts(current => {
        const next = { ...current };
        delete next[company.companyId];
        return next;
      });
      await onReload?.();
    } catch (saveError) {
      setError(saveError.message || 'Не удалось сохранить подключение');
    } finally {
      setSavingId(null);
    }
  };

  return (
    <section aria-label="Платная функция JEV" style={{ display: 'grid', gap: 12 }}>
      <div style={card}>
        <h2 style={{ color: C.text || '#101828', fontSize: 18, margin: '0 0 6px' }}>Поиск коммерческих заказов JEV</h2>
        <p style={{ color: C.textSec || '#667085', margin: '0 0 10px', lineHeight: 1.5 }}>
          Подключайте функцию нужным организациям по отдельности. Каждая получает свой список находок;
          повторный импорт обновляет карточки и не сбрасывает решения. Поиск пока общий по Ставропольскому краю,
          а фразы ниже отбирают результаты отдельно для каждой компании.
        </p>
        <p style={{ color: C.textSec || '#667085', margin: 0, fontSize: 13 }}>
          Включённых организаций: <b>{data?.enabledCompanies ?? 0}</b>
          {' · '}Потенциально в месяц: <b>{Number(data?.potentialMonthlyRevenue || 0).toLocaleString('ru-RU')} ₽</b>
        </p>
        <p style={{ color: C.textSec || '#667085', margin: '8px 0 0', fontSize: 12 }}>
          Цена здесь сохраняется как условие подключения. Автоматического списания нет: стоимость нужно закрепить в договоре и выставить счётом.
        </p>
        <div style={{ marginTop: 12, borderTop: '1px solid ' + (C.border || '#d0d5dd'), paddingTop: 10 }}>
          <b style={{ color: C.text || '#101828', fontSize: 13 }}>Источники поиска</b>
          <p style={{ color: C.textSec || '#667085', margin: '5px 0 0', lineHeight: 1.5 }}>
            Работают сейчас: B2B-Center · Росэлторг · Фабрикант.
          </p>
          <p style={{ color: C.textSec || '#667085', margin: '5px 0 0', lineHeight: 1.5 }}>
            ЕИС: подключён пилот открытого поиска по 44-ФЗ, 223-ФЗ и 615-ПП. Проверяется первая страница выдачи; госзакупки попадают в отдельную очередь и требуют ручной проверки. Остальные площадки не считаются работающими, пока их адаптер не проверен.
          </p>
        </div>
      </div>
      <div style={card}>
        <label style={{ display: 'grid', gap: 5, maxWidth: 500, color: C.textSec || '#667085', fontSize: 12 }}>
          Найти организацию
          <input value={search} onChange={event => setSearch(event.target.value)} placeholder="Название, ИНН или аккаунт" style={input} />
        </label>
      </div>
      {error && <p role="alert" style={{ color: C.danger || '#b42318', margin: 0 }}>{error}</p>}
      {visibleCompanies.length === 0 && (
        <div style={{ ...card, color: C.textSec || '#667085' }}>Клиентских организаций пока нет.</div>
      )}
      {visibleCompanies.map(company => {
        const draft = getDraft(company);
        return (
          <article key={company.companyId} style={{ ...card, display: 'grid', gap: 10, opacity: company.companyActive ? 1 : 0.65 }}>
            <div>
              <b style={{ color: C.text || '#101828' }}>{company.companyName}</b>
              <div style={{ color: C.textSec || '#667085', fontSize: 12, marginTop: 3 }}>
                {company.platformAccountName || 'Без аккаунта'} · ИНН {company.inn || 'не указан'} · ID {company.companyId}
                {company.isPlatformOwner && ' · внутренняя организация'}
                {!company.companyActive && ' · неактивна'}
              </div>
            </div>
            <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap', alignItems: 'end' }}>
              <label style={{ display: 'flex', gap: 8, alignItems: 'center', minHeight: 38, color: C.text || '#101828' }}>
                <input
                  type="checkbox"
                  checked={Boolean(draft.enabled)}
                  disabled={!company.companyActive || savingId === company.companyId}
                  onChange={event => updateDraft(company, { enabled: event.target.checked })}
                />
                Подключить JEV
              </label>
              <label style={{ display: 'grid', gap: 4, color: C.textSec || '#667085', fontSize: 12 }}>
                Цена в месяц, ₽
                <input
                  type="number"
                  min="0"
                  max="10000000"
                  step="0.01"
                  value={draft.monthlyFee}
                  disabled={company.isPlatformOwner || savingId === company.companyId}
                  onChange={event => updateDraft(company, { monthlyFee: event.target.value })}
                  style={{ ...input, width: 180, boxSizing: 'border-box' }}
                />
              </label>
              <label style={{ display: 'grid', gap: 4, flex: '1 1 260px', color: C.textSec || '#667085', fontSize: 12 }}>
                Фразы для отбора находок этой компании
                <input
                  type="text"
                  value={draft.searchTerms}
                  placeholder="Например: школа, кровля, благоустройство"
                  disabled={savingId === company.companyId}
                  onChange={event => updateDraft(company, { searchTerms: event.target.value })}
                  style={{ ...input, width: '100%', boxSizing: 'border-box' }}
                />
                <span>Разделяйте запятыми. Пустое поле — показывать все находки по региону.</span>
              </label>
              <button
                type="button"
                disabled={savingId === company.companyId}
                onClick={() => save(company)}
                style={{
                  border: 0, borderRadius: 8, padding: '9px 14px', minHeight: 38,
                  background: C.accent || '#f97316', color: '#fff', cursor: 'pointer',
                }}
              >
                {savingId === company.companyId ? 'Сохраняю…' : 'Сохранить'}
              </button>
            </div>
          </article>
        );
      })}
    </section>
  );
}
