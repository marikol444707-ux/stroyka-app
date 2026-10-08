import React from 'react';

const money = value => Number(value).toLocaleString('ru-RU', { maximumFractionDigits: 2 }) + ' ₽';

export default function CommercialComparison({ C, compareResult: result, hasSelectedOffer = false }) {
  if (!result) return null;
  const ranking = result.ranking || [];
  const best = ranking.find(row => row.offerId === result.bestOfferId) || ranking[0];
  return <section aria-label="Сравнение предложений" style={{ padding: 16, background: C.bg, border: '1px solid '+C.border, borderRadius: 14, marginBottom: 12 }}>
    {result.error ? <p role="alert">{result.error}</p> : <>
      <div style={{ padding: 16, background: C.successLight, border: '1px solid '+C.successBorder, borderRadius: 12 }}>
        <span style={{ color: C.success, fontSize: 12, fontWeight: 700 }}>ЛУЧШЕЕ ПРЕДЛОЖЕНИЕ ПО УСЛОВИЯМ</span>
        <h3 style={{ margin: '8px 0', color: C.text }}>{result.bestSupplier}</h3>
        {best && <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px 24px' }}>
          <strong style={{ fontSize: 22 }}>{money(best.totalPrice)}</strong>
          <span>{best.vatIncluded ? 'С НДС' : 'Без НДС'} · доставка {best.deliveryDays} дн.</span>
          <span>{best.paymentTerms || 'Условия оплаты не указаны'}</span>
        </div>}
        <p style={{ marginBottom: 0, fontSize: 13 }}>{hasSelectedOffer ? 'Результат сравнения показан для справки.' : 'Чтобы выбрать поставщика, проверьте его КП и нажмите «Выбрать» в карточке ниже.'}</p>
      </div>
      <p style={{ fontSize: 13 }}>{result.aiText ? 'Почему этот вариант: '+result.aiText : 'Сравнение готово. Пояснение ИИ сейчас недоступно.'}</p>
      {ranking.length === 1 && <p style={{ fontSize: 13 }}>Из полученных предложений только это покрывает всю заявку.</p>}
      <details>
        <summary style={{ cursor: 'pointer', padding: '8px 0', fontWeight: 600 }}>Сравнить условия всех поставщиков ({ranking.length})</summary>
        <div style={{ overflowX: 'auto' }}><table style={{ width: '100%', fontSize: 13, borderCollapse: 'collapse' }}>
          <thead><tr>{['Поставщик', 'Сумма КП', 'Доставка', 'Оплата', 'Балл'].map(label => <th key={label} style={{ textAlign: 'left', padding: 8 }}>{label}</th>)}</tr></thead>
          <tbody>{ranking.map(row => <tr key={row.offerId}>
            <td style={{ padding: 8 }}>{row.supplier}{row.rating > 0 && ` · рейтинг ${row.rating}/5`}</td>
            <td style={{ padding: 8, whiteSpace: 'nowrap' }}>{money(row.totalPrice)}{row.vatIncluded ? ' · с НДС' : ' · без НДС'}</td>
            <td style={{ padding: 8 }}>{row.deliveryDays} дн.</td><td style={{ padding: 8 }}>{row.paymentTerms || 'Не указано'}</td><td style={{ padding: 8 }}>{row.score}</td>
          </tr>)}</tbody>
        </table></div>
        <p style={{ fontSize: 12, color: C.textSec }}>Сравниваем всю заявку: сумма — 40%, доставка, оплата и рейтинг — по 20%. Дополнительные расходы учитываются, если поставщик включил их в сумму. Оригинал КП проверьте перед выбором.</p>
      </details>
      <p style={{ fontSize: 12, color: C.textSec }}>{hasSelectedOffer ? 'Поставщик уже выбран. Сравнение не меняет ваш выбор.' : 'Это рекомендация. Поставщик пока не выбран.'}</p>
    </>}
    {result.excludedOffers?.length > 0 && <div style={{ marginTop: 12 }}><strong>Не участвуют в сравнении</strong><ul>{result.excludedOffers.map(row => <li key={row.offerId}>{row.supplier}: {row.reason}</li>)}</ul></div>}
  </section>;
}
