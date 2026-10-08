import React from 'react';
import './supplierCardDetails.css';

const value = text => String(text || '').trim() || 'Не указано';

export default function SupplierCardDetails({supplier, C, onEdit}) {
  const fields = [
    ['ИНН', supplier.inn], ['КПП', supplier.kpp], ['ОГРН / ОГРНИП', supplier.ogrn],
    ['Юридический адрес', supplier.legalAddress || supplier.legal_address], ['Банк', supplier.bank],
    ['БИК', supplier.bik], ['Расчётный счёт', supplier.account],
    ['Корреспондентский счёт', supplier.korAccount || supplier.kor_account],
    ['Подписант', supplier.directorName || supplier.director_name], ['Должность подписанта', supplier.directorPosition || supplier.director_position],
  ];
  return <section className="supplier-card-details" aria-label="Условия и реквизиты поставщика"
    style={{'--supplier-border':C.border,'--supplier-muted':C.textSec,'--supplier-text':C.text,'--supplier-bg':C.bg}}>
    <div className="supplier-card-details__heading">
      <h3>Условия работы</h3>
      {onEdit && <button type="button" onClick={onEdit}>Изменить карточку</button>}
    </div>
    <p className="supplier-card-details__hint">Для выбранной компании</p>
    <dl className="supplier-card-details__terms">
      <div><dt>Оплата</dt><dd>{value(supplier.paymentTerms)}</dd></div>
      <div><dt>Доставка</dt><dd>{value(supplier.deliveryTerms)}</dd></div>
    </dl>
    {supplier.notes && <p className="supplier-card-details__notes">{supplier.notes}</p>}
    <details>
      <summary>Реквизиты поставщика</summary>
      <dl className="supplier-card-details__requisites">
        {fields.map(([label,text])=><div key={label}><dt>{label}</dt><dd>{value(text)}</dd></div>)}
      </dl>
    </details>
  </section>;
}
