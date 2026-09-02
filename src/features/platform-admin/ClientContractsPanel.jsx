import { useCallback, useEffect, useState } from 'react';


const statusLabels = {
  draft: 'Черновик',
  issued: 'Выдан',
  active: 'Действует',
  expired: 'Истёк',
  terminated: 'Расторгнут',
  cancelled: 'Аннулирован',
};

const today = () => new Date().toISOString().slice(0, 10);

const newRequest = companyId => ({
  companyId,
  idempotencyKey: `client-contract-${companyId}-${Date.now()}-${Math.random().toString(36).slice(2, 10)}`,
  contractDate: today(),
  startsOn: today(),
  status: 'draft',
});

const money = value => `${Number(value || 0).toLocaleString('ru-RU').replace(/\u00a0/g, ' ')} ₽/мес`;

const limits = contract => (
  `${contract.maxProjects ?? 'без лимита'} объектов · ${contract.maxUsers ?? 'без лимита'} пользователей`
);

const responseMessage = data => {
  if (typeof data?.detail === 'string') return data.detail;
  const blockers = data?.detail?.blockers || data?.blockers;
  if (Array.isArray(blockers) && blockers.length) {
    return blockers.map(item => item.message || item.code).join(' ');
  }
  return 'Не удалось выполнить запрос. Обновите страницу и повторите.';
};

function ClientContractsPanel({company, API, canManage, C, btnO, btnG, badge}) {
  const [contracts, setContracts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [working, setWorking] = useState(false);
  const [preview, setPreview] = useState(null);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [draftRequest, setDraftRequest] = useState(null);

  const request = useCallback(async (path, options = {}) => {
    const response = await fetch(API + path, {
      credentials: 'include',
      ...options,
      headers: {
        ...(options.body ? {'Content-Type': 'application/json'} : {}),
        ...(options.headers || {}),
      },
    });
    const data = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(responseMessage(data));
    return data;
  }, [API]);

  const loadContracts = useCallback(async () => {
    setError('');
    try {
      const data = await request(`/system/client-contracts?companyId=${company.id}`);
      setContracts(Array.isArray(data.items) ? data.items : []);
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setLoading(false);
    }
  }, [company.id, request]);

  useEffect(() => {
    loadContracts();
  }, [loadContracts]);

  const prepare = async () => {
    setWorking(true);
    setError('');
    setNotice('');
    try {
      const nextRequest = newRequest(company.id);
      setDraftRequest(nextRequest);
      setPreview(await request('/system/client-contracts/preview', {
        method: 'POST',
        body: JSON.stringify(nextRequest),
      }));
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setWorking(false);
    }
  };

  const create = async () => {
    if (!draftRequest) return;
    setWorking(true);
    setError('');
    try {
      const result = await request('/system/client-contracts', {
        method: 'POST',
        body: JSON.stringify(draftRequest),
      });
      const number = result.contract?.number || 'без номера';
      setNotice(result.created
        ? `Черновик ${number} создан. Оплаты и доступы не изменены.`
        : `Черновик ${number} уже существовал — повторно не создан.`);
      setPreview(null);
      await loadContracts();
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setWorking(false);
    }
  };

  const prepared = preview?.contract;
  const blockers = Array.isArray(preview?.blockers) ? preview.blockers : [];

  return (
    <section
      aria-label={`Договор с ${company.name}`}
      style={{marginTop: '10px', padding: '12px', border: `1px solid ${C.border}`, borderRadius: '10px', background: C.bg}}
    >
      <div style={{display: 'flex', justifyContent: 'space-between', gap: '10px', flexWrap: 'wrap', alignItems: 'center'}}>
        <div>
          <b style={{display: 'block', color: C.text, fontSize: '13px'}}>📃 Договор с клиентом</b>
          <span style={{color: C.textMuted, fontSize: '11px'}}>Реквизиты, тариф и лимиты берутся из карточек платформы.</span>
        </div>
        {canManage && !preview && (
          <button disabled={working || loading} onClick={prepare} style={{...btnO, padding: '6px 11px', fontSize: '11px'}}>
            {working ? 'Подготавливаем…' : (contracts.length ? 'Новый черновик' : 'Подготовить договор')}
          </button>
        )}
      </div>

      {loading && <p role="status" style={{color: C.textSec, fontSize: '12px', margin: '10px 0 0'}}>Загружаем договоры…</p>}
      {!loading && !error && contracts.length === 0 && (
        <p style={{color: C.textMuted, fontSize: '12px', margin: '10px 0 0'}}>Договоров пока нет</p>
      )}
      {contracts.length > 0 && (
        <div style={{display: 'grid', gap: '7px', marginTop: '10px'}}>
          {contracts.slice(0, 5).map(contract => (
            <div key={contract.id} style={{display: 'flex', justifyContent: 'space-between', gap: '8px', alignItems: 'center', padding: '8px 10px', border: `1px solid ${C.border}`, borderRadius: '8px'}}>
              <div>
                <b style={{color: C.text, fontSize: '12px'}}>{contract.number}</b>
                <span style={{color: C.textMuted, fontSize: '11px', marginLeft: '8px'}}>{contract.contractDate} · {money(contract.monthlyFee)}</span>
              </div>
              <span style={badge(C.info, C.infoLight, C.infoBorder)}>{statusLabels[contract.status] || contract.status}</span>
            </div>
          ))}
        </div>
      )}

      {prepared && (
        <div style={{marginTop: '10px', padding: '11px', border: `1.5px solid ${blockers.length ? C.warningBorder : C.successBorder}`, background: blockers.length ? C.warningLight : C.successLight, borderRadius: '9px'}}>
          <b style={{display: 'block', color: blockers.length ? C.warning : C.success, fontSize: '12px'}}>
            {blockers.length ? 'Нужно дополнить данные' : 'Реквизиты и условия заполнены автоматически'}
          </b>
          <div style={{display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(190px, 1fr))', gap: '7px', marginTop: '9px', color: C.text, fontSize: '12px'}}>
            <span><small style={{color: C.textMuted}}>Правообладатель</small><br />{prepared.licensorSnapshot?.legalName || '—'}</span>
            <span><small style={{color: C.textMuted}}>Клиент</small><br />{prepared.clientSnapshot?.legalName || '—'}</span>
            <span><small style={{color: C.textMuted}}>Тариф</small><br />{prepared.plan} · {money(prepared.monthlyFee)}</span>
            <span><small style={{color: C.textMuted}}>Лимиты</small><br />{limits(prepared)}</span>
          </div>
          {blockers.length > 0 && (
            <ul style={{margin: '9px 0 0', paddingLeft: '18px', color: C.warning, fontSize: '11px'}}>
              {blockers.map(item => <li key={`${item.code}-${item.field}`}>{item.message || item.code}</li>)}
            </ul>
          )}
          <div style={{display: 'flex', gap: '7px', marginTop: '10px', flexWrap: 'wrap'}}>
            {canManage && preview.readyForDraft && (
              <button disabled={working} onClick={create} style={{...btnO, padding: '7px 12px', fontSize: '12px'}}>
                {working ? 'Создаём…' : 'Создать черновик договора'}
              </button>
            )}
            <button disabled={working} onClick={() => setPreview(null)} style={{...btnG, padding: '7px 12px', fontSize: '12px'}}>Закрыть предпросмотр</button>
          </div>
        </div>
      )}

      {notice && <p role="status" style={{margin: '10px 0 0', color: C.success, fontSize: '12px', fontWeight: 700}}>{notice}</p>}
      {error && <p role="alert" style={{margin: '10px 0 0', color: C.danger, fontSize: '12px', fontWeight: 700}}>{error}</p>}
    </section>
  );
}

export default ClientContractsPanel;
