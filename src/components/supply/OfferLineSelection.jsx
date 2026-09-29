import React from 'react';
import { offerItemRows, offerLineKey } from '../../features/supply/offerItemScopes';

export default function OfferLineSelection({offer, offers, onSelect, C, buttonStyle}) {
  const occupied = new Set(offers.flatMap(other => offerItemRows(other.awardedItemsJson).map(line => line.requestPosition)));
  const requested = offerItemRows(offer.requestedItemsJson);
  const prices = new Map(offerItemRows(offer.itemsKpJson).map(line => [offerLineKey(line), line]));
  const [excluded, setExcluded] = React.useState([]);
  const [pending, setPending] = React.useState(false);
  const [error, setError] = React.useState('');
  const selected = requested.filter(line => !occupied.has(line.requestPosition) && !excluded.includes(line.requestPosition));
  const total = selected.reduce((sum, line) => sum + Number(prices.get(offerLineKey(line))?.totalPrice || 0), 0);
  return <fieldset disabled={pending} style={{border:`1px solid ${C.border}`,borderRadius:6,padding:8,minWidth:220,maxWidth:'100%'}}>
    <legend>Заказать у этого поставщика</legend>
    {requested.map(line => <label key={line.requestPosition} style={{display:'flex',gap:8,alignItems:'start',marginBottom:6}}>
      <input type="checkbox" aria-label={`Заказать ${line.materialName}`} disabled={occupied.has(line.requestPosition)} checked={selected.includes(line)} onChange={() => setExcluded(prev => prev.includes(line.requestPosition) ? prev.filter(p => p !== line.requestPosition) : [...prev,line.requestPosition])}/>
      <span>{line.materialName} · {line.quantity} {line.unit} · {Number(prices.get(offerLineKey(line))?.pricePerUnit || 0).toLocaleString('ru-RU')} ₽/ед.
        {occupied.has(line.requestPosition) && <small style={{display:'block'}}>Уже заказано</small>}
      </span>
    </label>)}
    <p>Выбрано: {selected.length} · {total.toLocaleString('ru-RU')} ₽</p>
    <button type="button" style={buttonStyle} disabled={!selected.length || pending} onClick={async () => {setPending(true);setError('');try {await onSelect(offer.id,selected.map(line=>line.requestPosition));} catch (error) {setError('Не удалось утвердить позиции. Обновите КП и повторите.');} finally {setPending(false);}}}>Утвердить выбранные позиции</button>
    {error && <p role="alert" style={{color:C.danger}}>{error}</p>}
  </fieldset>;
}
