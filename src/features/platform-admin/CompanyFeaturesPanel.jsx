import React from 'react';

const JEV_PROVIDERS = [
  'B2B-Center', 'Росэлторг', 'Фабрикант', 'ЭТП ГПБ', 'Сбер А', 'ТЭК-Торг', 'Торги Федерации', 'Р-ТЕНДЕР',
];

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
    sourceProviders: Array.isArray(company.sourceProviders) && company.sourceProviders.length
      ? company.sourceProviders : JEV_PROVIDERS,
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
          sourceProviders: draft.sourceProviders,
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
          повторный импорт обновляет карточки и не сбрасывает решения. Каждый запуск распределяет находки отдельно
          по выбранным площадкам и фразам организации. Региональный поиск пока общий по Ставропольскому краю.
        </p>
        <p style={{ color: C.textSec || '#667085', margin: 0, fontSize: 13 }}>
          Включённых организаций: <b>{data?.enabledCompanies ?? 0}</b>
          {' · '}Сумма заданных тарифов в месяц: <b>{Number(data?.potentialMonthlyRevenue || 0).toLocaleString('ru-RU')} ₽</b>
        </p>
        <p style={{ color: C.textSec || '#667085', margin: '8px 0 0', fontSize: 12 }}>
          Цена здесь сохраняется как условие подключения. Автоматического списания нет: стоимость нужно закрепить в договоре и выставить счётом.
        </p>
        <div style={{ marginTop: 12, borderTop: '1px solid ' + (C.border || '#d0d5dd'), paddingTop: 10 }}>
          <b style={{ color: C.text || '#101828', fontSize: 13 }}>Источники поиска</b>
          <p style={{ color: C.textSec || '#667085', margin: '5px 0 0', lineHeight: 1.5 }}>
            Серверный сбор JEV настроен на: B2B-Center · Росэлторг · Фабрикант · ЭТП ГПБ · Сбер А · ТЭК-Торг · Торги Федерации · Р-ТЕНДЕР.
          </p>
          <p style={{ color: C.textSec || '#667085', margin: '5px 0 0', lineHeight: 1.5 }}>
            ЕИС пока не входит в текущую серверную команду JEV; госзакупки не будут показаны в этой выдаче, пока ЕИС не подключена к этому запуску.
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
              <fieldset style={{ ...card, display: 'flex', flexWrap: 'wrap', gap: '6px 12px', margin: 0, padding: 9, flex: '1 1 260px' }}>
                <legend style={{ color: C.textSec || '#667085', fontSize: 12 }}>Площадки для этой организации</legend>
                {/* Controlled checkbox inputs update from event.target.checked: https://react.dev/reference/react-dom/components/input#controlling-an-input-with-a-state-variable */}
                {JEV_PROVIDERS.map(provider => (
                  <label key={provider} style={{ display: 'inline-flex', alignItems: 'center', gap: 5, color: C.text || '#101828', fontSize: 13 }}>
                    <input
                      type="checkbox"
                      checked={draft.sourceProviders.includes(provider)}
                      disabled={savingId === company.companyId || (draft.sourceProviders.length === 1 && draft.sourceProviders.includes(provider))}
                      onChange={event => updateDraft(company, {
                        sourceProviders: event.target.checked
                          ? [...draft.sourceProviders, provider]
                          : draft.sourceProviders.filter(item => item !== provider),
                      })}
                    />
                    {provider}
                  </label>
                ))}
                <span style={{ flexBasis: '100%', color: C.textSec || '#667085', fontSize: 11 }}>
                  Выбор ограничивает карточки этой организации. Сам сбор пока выполняется общим запуском.
                </span>
              </fieldset>
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
