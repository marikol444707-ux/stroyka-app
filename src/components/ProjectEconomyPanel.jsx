import React from 'react';

const fmtMoney = (value) => Math.round(Number(value || 0)).toLocaleString('ru-RU') + ' ₽';
const fmtPct = (value) => {
  if (!Number.isFinite(value)) return '0%';
  return (Math.round(value * 10) / 10).toLocaleString('ru-RU') + '%';
};

export default function ProjectEconomyPanel({
  C,
  card,
  btnB,
  btnG,
  btnO,
  project,
  economy,
  isMobile,
  onOpenFinance,
  onOpenJournal,
  onOpenMaterials,
  onOpenEstimate,
  showPreview,
}) {
  if (!economy) return null;

  const marginColor = economy.marginClosed >= 0 ? C.success : C.danger;
  const forecastColor = economy.marginForecast >= 0 ? C.success : C.warning;
  const progressColor = economy.customerPlan > 0 && economy.customerClosed > economy.customerPlan ? C.warning : C.success;
  const costTotal = economy.executionConfirmed + economy.legacyWorkCost + economy.materialCost + economy.otherCost;

  const buildManagementReport = () => {
    const rows = [
      ['Смета заказчика', fmtMoney(economy.customerPlan), economy.activeEstimates + ' активных смет'],
      ['Закрыто заказчику', fmtMoney(economy.customerClosed), fmtPct(economy.customerProgress) + ' от сметы'],
      ['К оплате исполнителям', fmtMoney(economy.executionConfirmed), economy.confirmedWorks + ' подтверждено, ' + fmtMoney(economy.executionPending) + ' на проверке'],
      ['Материалы по смете', fmtMoney(economy.materialPlan), economy.materialRows + ' позиций потребности'],
      ['Фактические затраты', fmtMoney(costTotal), 'исполнители + материалы + прочие'],
      ['Материалы факт', fmtMoney(economy.materialCost), 'по складу/приходам объекта'],
      ['Прочие затраты', fmtMoney(economy.otherCost + economy.legacyWorkCost), economy.legacyWorkCost > 0 ? 'включая старые трудовые расходы' : 'без ЖПР исполнителей'],
      ['Маржа по закрытому', fmtMoney(economy.marginClosed), fmtPct(economy.marginClosedPct)],
      ['Прогноз маржи по плану', fmtMoney(economy.marginForecast), 'смета - исполнители - материалы - прочие затраты'],
    ];
    const table = rows.map(row => '<tr><td>' + row[0] + '</td><td><b>' + row[1] + '</b></td><td>' + row[2] + '</td></tr>').join('');
    return (
      '<h2 style="text-align:center">Управленческий отчет по объекту</h2>' +
      '<p><b>Объект:</b> ' + (project?.name || '—') + '</p>' +
      '<p><b>Дата:</b> ' + new Date().toLocaleDateString('ru-RU') + '</p>' +
      '<table><tr><th>Показатель</th><th>Сумма/значение</th><th>Комментарий</th></tr>' + table + '</table>' +
      '<p style="margin-top:18px"><b>Пакеты в расчете:</b> ' + (economy.packages.length ? economy.packages.join(', ') : 'не определены') + '</p>' +
      '<p style="font-size:10px;color:#666">Отчет сформирован автоматически из активных смет, подтвержденного ЖПР, материалов и финансовых движений объекта.</p>'
    );
  };

  const metricCard = (label, value, color, sub, options = {}) => (
    <div style={{
      padding: '12px',
      borderRadius: '10px',
      backgroundColor: options.bg || C.bg,
      border: '1.5px solid ' + (options.border || C.border),
      minWidth: 0,
    }}>
      <p style={{margin: '0 0 5px', color: C.textSec, fontSize: '11px'}}>{label}</p>
      <b style={{display: 'block', color, fontSize: options.large ? '18px' : '15px', lineHeight: 1.2, wordBreak: 'break-word'}}>{value}</b>
      {sub ? <p style={{margin: '5px 0 0', color: C.textMuted, fontSize: '10px', lineHeight: 1.35}}>{sub}</p> : null}
    </div>
  );

  return (
    <div style={{...card, padding: '16px', marginBottom: '12px', backgroundColor: C.bgWhite, border: '1.5px solid ' + C.accentBorder}}>
      <div style={{display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: '12px', flexWrap: 'wrap', marginBottom: '12px'}}>
        <div>
          <b style={{display: 'block', color: C.text, fontSize: '15px'}}>💼 Экономика объекта</b>
          <p style={{margin: '4px 0 0', color: C.textSec, fontSize: '12px', lineHeight: 1.4}}>
            Заказчик считается по смете и КС, исполнители - по внутренней цене из ЖПР.
          </p>
        </div>
        <div style={{display: 'flex', gap: '8px', flexWrap: 'wrap'}}>
          <button onClick={onOpenFinance} style={{...btnB, padding: '6px 10px', fontSize: '12px'}}>Финансы</button>
          <button onClick={onOpenJournal} style={{...btnG, padding: '6px 10px', fontSize: '12px'}}>ЖПР</button>
          <button onClick={onOpenMaterials} style={{...btnG, padding: '6px 10px', fontSize: '12px'}}>Материалы</button>
          <button onClick={onOpenEstimate} style={{...btnO, padding: '6px 10px', fontSize: '12px'}}>Смета</button>
          <button onClick={() => showPreview?.(buildManagementReport(), 'Управленческий отчет — ' + (project?.name || 'объект'))} style={{...btnB, padding: '6px 10px', fontSize: '12px'}}>Отчет</button>
        </div>
      </div>

      <div style={{display: 'grid', gridTemplateColumns: isMobile ? '1fr 1fr' : 'repeat(4,minmax(0,1fr))', gap: '10px', marginBottom: '10px'}}>
        {metricCard('Смета заказчика', fmtMoney(economy.customerPlan), C.success, economy.activeEstimates + ' активных смет')}
        {metricCard('Закрыто заказчику', fmtMoney(economy.customerClosed), progressColor, fmtPct(economy.customerProgress) + ' от сметы')}
        {metricCard('К оплате исполнителям', fmtMoney(economy.executionConfirmed), C.warning, economy.confirmedWorks + ' подтверждено, ' + fmtMoney(economy.executionPending) + ' на проверке')}
        {metricCard('Материалы по смете', fmtMoney(economy.materialPlan), C.info, economy.materialRows + ' позиций потребности')}
      </div>

      <div style={{display: 'grid', gridTemplateColumns: isMobile ? '1fr' : 'repeat(4,minmax(0,1fr))', gap: '10px', marginBottom: '10px'}}>
        {metricCard('Фактические затраты', fmtMoney(costTotal), C.text, 'исполнители + материалы + прочие')}
        {metricCard('Материалы факт', fmtMoney(economy.materialCost), C.info, 'по складу/приходам объекта')}
        {metricCard('Прочие затраты', fmtMoney(economy.otherCost + economy.legacyWorkCost), C.textSec, economy.legacyWorkCost > 0 ? 'включая старые трудовые расходы' : 'без ЖПР исполнителей')}
        {metricCard('Маржа по закрытому', fmtMoney(economy.marginClosed), marginColor, fmtPct(economy.marginClosedPct), {bg: economy.marginClosed >= 0 ? C.successLight : C.dangerLight, border: economy.marginClosed >= 0 ? C.successBorder : C.dangerBorder, large: true})}
      </div>

      <div style={{display: 'grid', gridTemplateColumns: isMobile ? '1fr' : '1fr 1fr', gap: '10px'}}>
        <div style={{padding: '10px 12px', borderRadius: '10px', backgroundColor: C.bg, border: '1.5px solid ' + C.border}}>
          <div style={{display: 'flex', justifyContent: 'space-between', gap: '10px', alignItems: 'center'}}>
            <span style={{color: C.textSec, fontSize: '12px'}}>Прогноз маржи по плану</span>
            <b style={{color: forecastColor, fontSize: '15px'}}>{fmtMoney(economy.marginForecast)}</b>
          </div>
          <p style={{margin: '5px 0 0', color: C.textMuted, fontSize: '10px', lineHeight: 1.35}}>
            Прогноз = смета заказчика - подтвержденные/ожидающие выплаты исполнителям - материалы - прочие затраты.
          </p>
        </div>
        <div style={{padding: '10px 12px', borderRadius: '10px', backgroundColor: C.bg, border: '1.5px solid ' + C.border}}>
          <div style={{display: 'flex', justifyContent: 'space-between', gap: '10px', alignItems: 'center'}}>
            <span style={{color: C.textSec, fontSize: '12px'}}>Пакеты в расчете</span>
            <b style={{color: C.accent, fontSize: '15px'}}>{economy.packages.length || 0}</b>
          </div>
          <p style={{margin: '5px 0 0', color: C.textMuted, fontSize: '10px', lineHeight: 1.35}}>
            {economy.packages.length ? economy.packages.slice(0, 6).join(', ') + (economy.packages.length > 6 ? '...' : '') : 'Пакеты не определены'}
          </p>
        </div>
      </div>
    </div>
  );
}
