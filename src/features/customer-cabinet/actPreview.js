import { docEsc } from '../../utils/documentFormatUtils';

const money = value => Number(value).toLocaleString('ru-RU', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
const sum = rows => rows.reduce((cents, row) => cents + Math.round(row.total * 100), 0) / 100;

export function buildCustomerActPreview(project, data, kind) {
  const sections = [
    ['Работы по смете', data.sourceItems],
    ['Дополнительные объёмы', data.additionalVolumeItems],
    ['Работы вне сметы', data.outsideEstimateItems],
  ];
  let html = `<h2>Расчёт для ${kind === 'ks3' ? 'КС-3' : 'КС-2'}</h2><p>Объект: ${docEsc(project.name)}</p>`;
  html += '<p>Предварительный расчёт по всем подтверждённым работам. Подписанные документы доступны в разделе документов.</p>';
  for (const [title, rows] of sections) {
    if (!rows.length) continue;
    html += `<h3>${title}</h3><table><thead><tr><th>Работа</th>${kind === 'ks3' ? '' : '<th>Ед.</th><th>Объём</th><th>Цена, ₽</th>'}<th>Сумма, ₽</th></tr></thead><tbody>`;
    for (const row of rows) {
      html += `<tr><td>${docEsc(row.description)}</td>`;
      if (kind !== 'ks3') html += `<td>${docEsc(row.unit || '')}</td><td>${Number(row.quantity).toLocaleString('ru-RU', { maximumFractionDigits: 6 })}</td><td>${money(row.pricePerUnit)}</td>`;
      html += `<td>${money(row.total)}</td></tr>`;
    }
    html += `</tbody></table><p>Итого по разделу: ${money(sum(rows))} ₽</p>`;
  }
  html += `<p><b>Итого выполнено: ${money(sum(sections.flatMap(([, rows]) => rows)))} ₽</b></p>`;
  return html;
}
