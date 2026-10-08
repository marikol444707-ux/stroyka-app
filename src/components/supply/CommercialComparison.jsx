import React from 'react';

export default function CommercialComparison({ C, compareResult: result }) {
  if (!result) return null;
  const ranking = result.ranking || [];
  return <section aria-label="Сравнение КП" style={{ padding: 12, background: C.bg, border: '1px solid '+C.border, borderRadius: 10, marginBottom: 10 }}>
    {result.error ? <p role="alert">{result.error}</p> : <>
      <strong style={{ color: C.success }}>Лучшее по условиям: {result.bestSupplier}</strong>
      <p style={{ fontSize: 12 }}>Сравнена стоимость всей заявки. Утвердите выбранное КП после проверки документов.</p>
      {result.aiText ? <p style={{ fontSize: 12 }}>Пояснение ИИ: {result.aiText}</p>
        : <p style={{ color: C.textSec, fontSize: 12 }}>Пояснение ИИ недоступно. Сравнение по условиям выполнено.</p>}
      {ranking.length === 1 && <p style={{ fontSize: 12 }}>Для всей заявки подходит только одно КП из полученных.</p>}
      <div style={{ overflowX: 'auto' }}><table style={{ width: '100%', fontSize: 12, borderCollapse: 'collapse' }}>
        <thead><tr>{['Поставщик', 'Сумма КП', 'Доставка', 'Оплата', 'Балл'].map(label => <th key={label} style={{ textAlign: 'left', padding: 6 }}>{label}</th>)}</tr></thead>
        <tbody>{ranking.map(row => <tr key={row.offerId}>
          <td style={{ padding: 6 }}>{row.supplier}{row.rating > 0 && ` · рейтинг ${row.rating}/5`}</td>
          <td style={{ padding: 6, whiteSpace: 'nowrap' }}>{Number(row.totalPrice).toLocaleString('ru-RU', { maximumFractionDigits: 2 })} ₽{row.vatIncluded ? ' · с НДС' : ' · без НДС'}</td>
          <td style={{ padding: 6 }}>{row.deliveryDays} дн.</td><td style={{ padding: 6 }}>{row.paymentTerms || 'Не указано'}</td><td style={{ padding: 6 }}>{row.score}</td>
        </tr>)}</tbody>
      </table></div>
      <p style={{ fontSize: 11, color: C.textSec }}>Сумма 40% · доставка 20% · оплата 20% · рейтинг 20%. Доставка и дополнительные расходы учитываются только если включены поставщиком в сумму КП. Соответствие файлам проверяется отдельно.</p>
    </>}
    {result.excludedOffers?.length > 0 && <div><strong>Нужно проверить</strong><ul>{result.excludedOffers.map(row => <li key={row.offerId}>{row.supplier}: {row.reason}</li>)}</ul></div>}
  </section>;
}
