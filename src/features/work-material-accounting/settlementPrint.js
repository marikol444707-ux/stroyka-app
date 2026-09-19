const escape = value => String(value ?? '').replace(/[&<>"']/g, char => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[char]));
const money = value => Number(value || 0).toLocaleString('ru-RU', { minimumFractionDigits: 2, maximumFractionDigits: 2 });

function fineRow(fine) {
  const tool = fine.source === 'tool';
  const title = tool ? `Инструмент: ${escape(fine.toolName)}, происшествие №${escape(fine.incidentId)}` : `Брак №${escape(fine.defectId)}, ЖПР №${escape(fine.journalId)}`;
  const evidence = tool ? escape(fine.priceEvidence) : (fine.valuations || []).map(v => `${escape(v.name || 'Материал №' + v.entryId)}: ${escape(v.quantity)} ${escape(v.unit || '')} × ${money(v.unitPrice)} ₽; ${escape(v.priceEvidence)}`).join('<br>');
  return `<tr><td>${title}<br>Решение №${escape(fine.decisionId)}<br>${escape(fine.reason)}<br>${escape(fine.contractEvidence)}</td><td>${evidence}</td><td>${money(fine.amount)}</td></tr>`;
}

export function buildSettlementAct(act) {
  const s = act.snapshot;
  if (!s || !Array.isArray(s.works) || !Array.isArray(s.fines)) throw new Error('Нет сохранённого состава акта.');
  return `<h2>АКТ ВЫПОЛНЕННЫХ РАБОТ №${escape(act.id)}</h2>
    <p>Объект: ${escape(s.projectName)}<br>Исполнитель: ${escape(s.brigadeName)}<br>
    Договор №${escape(s.contractId)} · ${escape(s.workPackage)}<br>Период: ${escape(s.periodFrom)} — ${escape(s.periodTo)}</p>
    <table border="1" cellpadding="6" style="width:100%;border-collapse:collapse"><thead><tr><th>ЖПР</th><th>Работа / помещение</th><th>Ед.</th><th>Объём</th><th>Цена, ₽</th><th>Сумма, ₽</th></tr></thead><tbody>
    ${s.works.map(w => `<tr><td>${escape(w.id)}</td><td>${escape(w.description)}<br>${escape(w.room_name)}</td><td>${escape(w.unit)}</td><td>${escape(w.quantity)}</td><td>${money(w.execution_price_per_unit)}</td><td>${money(w.execution_total)}</td></tr>`).join('')}
    </tbody></table><p><b>Стоимость принятых работ: ${money(s.grossAmount)} ₽</b></p>
    <h3>Штрафы</h3>${s.fines.length ? `<table border="1" cellpadding="6" style="width:100%;border-collapse:collapse"><tr><th>Основание</th><th>Подтверждение стоимости</th><th>Включено в этот акт, ₽</th></tr>
    ${s.fines.map(fineRow).join('')}</table>` : '<p>Подтверждённых штрафов нет.</p>'}
    <p>Итого штрафы: <b>${money(s.fineAmount)} ₽</b></p><p><b>К оплате по акту: ${money(s.netAmount)} ₽</b></p>
    <p style="margin-top:36px">Заказчик ____________________ &nbsp; Исполнитель ____________________</p>`;
}
