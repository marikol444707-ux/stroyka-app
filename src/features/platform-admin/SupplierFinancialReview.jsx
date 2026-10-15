const labels={orders:'Заказы',invoices:'Счета',deliveries:'Поставки',receipts:'Накладные',contracts:'Договоры'};

export function financialReviewState(review) {
  if(!review)return null;
  const counts=['source','connected'].flatMap(side=>Object.keys(labels).map(key=>review[side]?.[key]));
  if(counts.some(n=>n!==null&&(!Number.isInteger(n)||n<0))||counts.includes(null))return 'needs_check';
  const expected=Object.values(review.connected).some(n=>n>0)?'review_required':'clear';
  return review.state===expected?expected:'needs_check';
}

export default function SupplierFinancialReview({review}) {
  const state=financialReviewState(review);
  if(!state)return null;
  return <section className="supplier-correction-financial" aria-label="Оформленные документы">
    <h4>{state==='review_required'?'Нужен разбор оформленных документов':
      state==='needs_check'?'Часть документов не удалось проверить':'Заказов, счетов и поставок у кабинета нет'}</h4>
    {state!=='clear'&&<p>Сначала разберите, кому адресованы эти документы.</p>}
    <details><summary>Документы по карточкам</summary>
      {['source','connected'].map(side=><div key={side}>
        <strong>{side==='source'?'Исходная карточка':'Подключённый кабинет'}</strong>
        <dl>{Object.entries(labels).map(([key,label])=><div key={key}><dt>{label}</dt><dd>{Number.isInteger(review[side]?.[key])&&review[side][key]>=0?review[side][key]:'Нужна проверка'}</dd></div>)}</dl>
      </div>)}
    </details>
  </section>;
}
