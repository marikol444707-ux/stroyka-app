import React from 'react';

export default function InvoiceLineTaxFields({ items, values = [], onChange, inputStyle }) {
  if (items.length < 2) return null;
  return <fieldset style={{minWidth:0,border:'1px solid currentColor',borderRadius:8,margin:'8px 0'}}>
    <legend>НДС по позициям счёта</legend>
    <p>Укажите сумму НДС из документа для каждой позиции. Для позиции без НДС укажите 0. Сумма должна совпасть с общим НДС счёта.</p>
    {items.map((item,index)=>{
      const position=item.quotePosition ?? index;
      const value=values.find(row=>row.sourceOfferPosition===position)?.vatAmount ?? '';
      return <label key={index} style={{display:'block',marginBottom:8}}>
        НДС, ₽ — {index+1}. {item.materialName || item.material_name || item.name}
        <input required type="number" min="0" step="0.01" inputMode="decimal" value={value}
          style={inputStyle} onChange={event=>onChange(items.map((row,i)=>({
            sourceOfferPosition:row.quotePosition ?? i,
            vatAmount:(row.quotePosition ?? i)===position ? event.target.value
              : values.find(old=>old.sourceOfferPosition===(row.quotePosition ?? i))?.vatAmount ?? '',
          })))} />
      </label>;
    })}
  </fieldset>;
}
