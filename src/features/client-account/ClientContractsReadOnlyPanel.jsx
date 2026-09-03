import { useCallback, useEffect, useState } from 'react';


const statusLabels = {
  draft: 'Черновик',
  issued: 'Выдан',
  active: 'Действует',
  expired: 'Истёк',
  terminated: 'Расторгнут',
  cancelled: 'Аннулирован',
};

const contractTone = status => {
  if (status === 'active') return 'success';
  if (['terminated', 'cancelled'].includes(status)) return 'danger';
  if (['draft', 'issued'].includes(status)) return 'warning';
  return 'info';
};

const formatDate = value => {
  if (!value) return '-';
  try {
    return new Date(value).toLocaleDateString('ru-RU');
  } catch (_) {
    return String(value).slice(0, 10);
  }
};

const formatMoney = value => {
  const amount = Number(value || 0);
  return amount ? Math.round(amount).toLocaleString('ru-RU') + ' ₽' : '-';
};

export default function ClientContractsReadOnlyPanel({API, C, card, btnG, embedded=false}) {
  const [contracts, setContracts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const loadContracts = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const response = await fetch(API + '/account/client-contracts', {
        credentials: 'include',
        cache: 'no-store',
      });
      if (!response.ok) throw new Error();
      const data = await response.json();
      setContracts(Array.isArray(data?.items) ? data.items : []);
    } catch (_) {
      setContracts([]);
      setError('Договоры временно не загрузились. Остальные данные кабинета доступны.');
    } finally {
      setLoading(false);
    }
  }, [API]);

  useEffect(() => { loadContracts(); }, [loadContracts]);

  const tone = level => {
    if (level === 'danger') return {backgroundColor:C.dangerLight, color:C.danger, borderColor:C.dangerBorder};
    if (level === 'warning') return {backgroundColor:C.warningLight, color:C.warning, borderColor:C.warningBorder};
    if (level === 'info') return {backgroundColor:C.infoLight, color:C.info, borderColor:C.infoBorder};
    return {backgroundColor:C.successLight, color:C.success, borderColor:C.successBorder};
  };
  const chip = (text, level) => (
    <span style={{...tone(level),border:'1px solid',borderRadius:'999px',padding:'3px 8px',fontSize:'11px',fontWeight:800,whiteSpace:'nowrap'}}>
      {text}
    </span>
  );
  const muted = {color:C.textSec,fontSize:'13px',lineHeight:1.45};
  const rootStyle = embedded
    ? {borderTop:'1px solid '+C.border,marginTop:'14px',paddingTop:'14px'}
    : {...card,padding:'16px',marginBottom:'16px'};

  return (
    <section aria-label="Договоры платформы" style={rootStyle}>
      <div style={{display:'flex',justifyContent:'space-between',gap:'8px',alignItems:'center',flexWrap:'wrap',marginBottom:'9px'}}>
        <b style={{color:C.text}}>Договоры платформы</b>
        {chip('Только просмотр', 'info')}
      </div>
      {loading && <p role="status" style={{...muted,margin:0}}>Загружаю договоры…</p>}
      {error && <p role="alert" style={{...muted,color:C.warning || '#b45309',margin:'0 0 8px'}}>{error}</p>}
      <div style={{display:'grid',gap:'8px'}}>
        {contracts.map(contract => (
          <article key={contract.id} style={{border:'1px solid '+C.border,borderRadius:'8px',padding:'10px'}}>
            <div style={{display:'flex',justifyContent:'space-between',gap:'8px',alignItems:'center',flexWrap:'wrap'}}>
              <b style={{color:C.text}}>{contract.number || `Договор #${contract.id}`}</b>
              {chip(contract.statusLabel || contract.status, contractTone(contract.status))}
            </div>
            <div style={{...muted,marginTop:'6px'}}>
              {contract.companyName || 'Компания'} · {formatMoney(contract.monthlyFee)} · с {formatDate(contract.startsOn)}
              {contract.endsOn ? ` по ${formatDate(contract.endsOn)}` : ''}
            </div>
            <div style={{display:'flex',gap:'8px',flexWrap:'wrap',marginTop:'8px'}}>
              {contract.generatedFileUrl && (
                <a href={contract.generatedFileUrl} target="_blank" rel="noreferrer" style={{...btnG,textDecoration:'none',fontSize:'12px',padding:'6px 9px'}}>
                  Открыть договор
                </a>
              )}
              {contract.signedFileUrl && (
                <a href={contract.signedFileUrl} target="_blank" rel="noreferrer" style={{...btnG,textDecoration:'none',fontSize:'12px',padding:'6px 9px'}}>
                  Подписанный договор
                </a>
              )}
            </div>
            {!!contract.statusHistory?.length && (
              <details style={{marginTop:'8px'}}>
                <summary style={{...muted,cursor:'pointer'}}>История статусов: {contract.statusHistory.length}</summary>
                <div style={{display:'grid',gap:'4px',marginTop:'6px'}}>
                  {contract.statusHistory.map((item, index) => (
                    <small key={`${item.changedAt}-${index}`} style={muted}>
                      {formatDate(item.changedAt)} · {statusLabels[item.fromStatus] || item.fromStatus || '—'} → {statusLabels[item.toStatus] || item.toStatus || '—'}
                      {item.reason ? ` · ${item.reason}` : ''}
                    </small>
                  ))}
                </div>
              </details>
            )}
          </article>
        ))}
        {!loading && !error && contracts.length === 0 && (
          <p style={{...muted,margin:0}}>Договоров пока нет.</p>
        )}
      </div>
    </section>
  );
}
