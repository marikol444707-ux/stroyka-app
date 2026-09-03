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
    const multipart = typeof FormData !== 'undefined' && options.body instanceof FormData;
    const response = await fetch(API + path, {
      credentials: 'include',
      ...options,
      headers: {
        ...(options.body && !multipart ? {'Content-Type': 'application/json'} : {}),
        ...(options.headers || {}),
      },
    });
    const data = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(responseMessage(data));
    return data;
  }, [API]);

  const replaceContract = updated => {
    setContracts(current => current.map(contract => (
      contract.id === updated.id ? updated : contract
    )));
  };

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

  const generatePdf = async contract => {
    setWorking(true);
    setError('');
    setNotice('');
    try {
      const result = await request(`/system/client-contracts/${contract.id}/generate-pdf`, {
        method: 'POST',
      });
      replaceContract(result.contract);
      setNotice(result.generated
        ? `PDF ${contract.number} сформирован и сохранён в защищённом хранилище.`
        : `PDF ${contract.number} уже был сформирован.`);
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setWorking(false);
    }
  };

  const uploadSignedPdf = async (contract, event) => {
    const file = event.target.files?.[0];
    if (!file) return;
    const form = new FormData();
    form.append('file', file);
    setWorking(true);
    setError('');
    setNotice('');
    try {
      const result = await request(`/system/client-contracts/${contract.id}/signed-file`, {
        method: 'POST',
        body: form,
      });
      replaceContract(result.contract);
      setNotice(`Подписанный PDF ${contract.number} сохранён. Оплата и доступ не изменены.`);
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      event.target.value = '';
      setWorking(false);
    }
  };

  const changeStatus = async (contract, status) => {
    setWorking(true);
    setError('');
    setNotice('');
    try {
      const result = await request(`/system/client-contracts/${contract.id}`, {
        method: 'PUT',
        body: JSON.stringify({status}),
      });
      replaceContract(result.contract);
      setNotice(
        `${contract.number}: статус изменён на «${statusLabels[status] || status}». ` +
        'Оплата и доступ клиента не менялись.',
      );
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
            <div key={contract.id} style={{display: 'grid', gap: '7px', padding: '8px 10px', border: `1px solid ${C.border}`, borderRadius: '8px'}}>
              <div style={{display: 'flex', justifyContent: 'space-between', gap: '8px', alignItems: 'center', flexWrap: 'wrap'}}>
                <div>
                  <b style={{color: C.text, fontSize: '12px'}}>{contract.number}</b>
                  <span style={{color: C.textMuted, fontSize: '11px', marginLeft: '8px'}}>{contract.contractDate} · {money(contract.monthlyFee)}</span>
                </div>
                <span style={badge(C.info, C.infoLight, C.infoBorder)}>{statusLabels[contract.status] || contract.status}</span>
              </div>
              <div style={{display: 'flex', gap: '6px', alignItems: 'center', flexWrap: 'wrap'}}>
                {!contract.generatedFileUrl && canManage && (
                  <button
                    aria-label={`Сформировать PDF ${contract.number}`}
                    disabled={working}
                    onClick={() => generatePdf(contract)}
                    style={{...btnO, padding: '5px 9px', fontSize: '11px'}}
                  >
                    Сформировать PDF
                  </button>
                )}
                {contract.generatedFileUrl && (
                  <a
                    aria-label={`Открыть PDF ${contract.number}`}
                    href={contract.generatedFileUrl}
                    target="_blank"
                    rel="noreferrer"
                    style={{...btnG, display: 'inline-block', padding: '5px 9px', fontSize: '11px', textDecoration: 'none'}}
                  >
                    Открыть PDF
                  </a>
                )}
                {contract.generatedFileUrl && !contract.signedFileUrl && canManage && (
                  <label style={{...btnG, display: 'inline-block', padding: '5px 9px', fontSize: '11px', cursor: working ? 'default' : 'pointer'}}>
                    Загрузить подписанный PDF
                    <input
                      aria-label={`Загрузить подписанный PDF для ${contract.number}`}
                      accept="application/pdf,.pdf"
                      disabled={working}
                      onChange={event => uploadSignedPdf(contract, event)}
                      style={{position: 'absolute', width: '1px', height: '1px', overflow: 'hidden', clip: 'rect(0 0 0 0)'}}
                      type="file"
                    />
                  </label>
                )}
                {contract.signedFileUrl && (
                  <a
                    aria-label={`Открыть подписанный PDF ${contract.number}`}
                    href={contract.signedFileUrl}
                    target="_blank"
                    rel="noreferrer"
                    style={{...btnG, display: 'inline-block', padding: '5px 9px', fontSize: '11px', textDecoration: 'none'}}
                  >
                    Подписанный PDF
                  </a>
                )}
                {canManage && contract.status === 'draft' && contract.generatedFileUrl && (
                  <button
                    aria-label={`Выдать договор ${contract.number}`}
                    disabled={working}
                    onClick={() => changeStatus(contract, 'issued')}
                    style={{...btnO, padding: '5px 9px', fontSize: '11px'}}
                  >
                    Выдать
                  </button>
                )}
                {canManage && contract.status === 'issued' && contract.signedFileUrl && (
                  <button
                    aria-label={`Активировать договор ${contract.number}`}
                    disabled={working}
                    onClick={() => changeStatus(contract, 'active')}
                    style={{...btnO, padding: '5px 9px', fontSize: '11px'}}
                  >
                    Активировать
                  </button>
                )}
                {canManage && contract.status === 'active' && (
                  <button
                    aria-label={`Прекратить договор ${contract.number}`}
                    disabled={working}
                    onClick={() => changeStatus(contract, 'terminated')}
                    style={{...btnG, padding: '5px 9px', fontSize: '11px'}}
                  >
                    Прекратить
                  </button>
                )}
                {canManage && ['draft', 'issued'].includes(contract.status) && (
                  <button
                    aria-label={`Аннулировать договор ${contract.number}`}
                    disabled={working}
                    onClick={() => changeStatus(contract, 'cancelled')}
                    style={{...btnG, padding: '5px 9px', fontSize: '11px'}}
                  >
                    Аннулировать
                  </button>
                )}
              </div>
            </div>
          ))}
          <small style={{color: C.textMuted}}>PDF и подписанный файл не выполняют оплату и не меняют доступ клиента.</small>
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
