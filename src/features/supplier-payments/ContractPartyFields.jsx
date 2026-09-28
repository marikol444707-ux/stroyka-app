import React from 'react';

const labels={fullName:'Полное наименование',inn:'ИНН',kpp:'КПП',ogrn:'ОГРН / ОГРНИП',legalAddress:'Юридический адрес',
 bankName:'Банк',bik:'БИК',rs:'Расчётный счёт',ks:'Корреспондентский счёт',directorName:'ФИО подписанта',
 directorPosition:'Должность подписанта',basis:'Основание полномочий',phone:'Телефон',email:'Email'};
const limits={fullName:500,kpp:9,ogrn:15,legalAddress:2000,bankName:500,bik:9,rs:20,ks:20,directorName:255,directorPosition:255,basis:1000,phone:100,email:255};
const patterns={inn:'(?:[0-9]{10}|[0-9]{12})',kpp:'[0-9]{9}',ogrn:'(?:[0-9]{13}|[0-9]{15})',bik:'[0-9]{9}',rs:'[0-9]{20}',ks:'[0-9]{20}'};
const groups=[['Организация',['fullName','inn','kpp','ogrn','legalAddress']],['Банковские реквизиты',['bankName','bik','rs','ks']],['Подписант и контакты',['directorName','directorPosition','basis','phone','email']]];
export default function ContractPartyFields({side,value,recognized,onChange,onApply}) {
 return <div className="contract-party-groups">{groups.map(([title,fields])=><section className="contract-field-group" key={title}>
  <h4>{title}</h4><div className="contract-field-grid">{fields.map(field=>{
   const source=recognized?.status==='matched'?recognized.fields[field]:null;
   const equal=source && source.value===value[field];
   const id=`contract-${side}-${field}`;
   return <div key={field} className={`contract-field ${['fullName','legalAddress','bankName','basis'].includes(field)?'contract-field-wide':''}`}>
    <div className="contract-field-heading"><label htmlFor={id}>{labels[field]}</label>
     {field==='inn'?<span className="contract-field-note">Из карточки</span>:source?
      <span className={`contract-field-note ${equal?'contract-note-found':'contract-note-warning'}`}>{equal?'Из договора · сверить':'Есть отличие'}</span>:
      !value[field] && recognized && <span className="contract-field-note">Не найдено</span>}
    </div>
    {['legalAddress','bankName'].includes(field)?<textarea id={id} rows={2} maxLength={limits[field]} value={value[field]} onChange={e=>onChange(field,e.target.value)}/>:
      <input id={id} required={['fullName','inn'].includes(field)} readOnly={field==='inn'} inputMode={patterns[field]?'numeric':undefined}
       pattern={patterns[field]} maxLength={limits[field] || 12} value={value[field]} onChange={e=>onChange(field,e.target.value)}/>}
    {source && field!=='inn' && <details className="contract-source"><summary>Текст в договоре</summary>
      <blockquote>{source.quote || source.value}</blockquote>
      {!equal && <button type="button" onClick={()=>onApply(field,source.value)}>Подставить из договора</button>}
     </details>}
   </div>;
  })}</div>
  {title==='Подписант и контакты' && <p className="contract-hint">ФИО и должность могут быть в падеже, как в тексте договора. При необходимости исправьте.</p>}
 </section>)}</div>;
}
