import React from 'react';

function SupplyCatalogPanel({
  C,
  card,
  inp,
  tblH,
  tblC,
  badge,
  supplierCatalog,
  listSearch,
  setListSearch,
}) {
  const q = (listSearch || '').toLowerCase().trim();
  const items = (supplierCatalog || []).filter(item =>
    !q ||
    (item.materialName || '').toLowerCase().includes(q) ||
    (item.supplierName || '').toLowerCase().includes(q)
  );

  const bySupplier = new Map();
  items.forEach(item => {
    const key = item.supplierName || ('Поставщик #' + item.supplierId);
    if (!bySupplier.has(key)) bySupplier.set(key, []);
    bySupplier.get(key).push(item);
  });

  return (
    <div>
      <div style={{...card,padding:'14px 16px',marginBottom:'16px',backgroundColor:C.accentLight,border:'1.5px solid '+(C.accentBorder||C.border)}}>
        <b style={{color:C.text,fontSize:'14px'}}>📦 Каталоги поставщиков</b>
        <p style={{color:C.textSec,fontSize:'11px',margin:'2px 0 0'}}>Прайсы заполняют сами поставщики в своих кабинетах. Здесь — актуальные цены, минимальные партии и сроки поставки. Используйте при выборе, у кого запросить КП.</p>
      </div>

      <input value={listSearch} onChange={e=>setListSearch(e.target.value)} placeholder="🔍 Поиск по материалу или поставщику..." style={{...inp,marginBottom:'16px'}} />

      {bySupplier.size===0 && (
        <div style={{...card,padding:'40px',textAlign:'center',color:C.textMuted}}>
          {(supplierCatalog||[]).length===0 ? 'Каталоги пока пусты — поставщики ещё не загрузили прайсы.' : 'Ничего не найдено по запросу.'}
        </div>
      )}

      {Array.from(bySupplier.entries()).map(([supplierName, rows])=>(
        <div key={supplierName} style={{...card,padding:'14px 16px',marginBottom:'12px'}}>
          <div style={{display:'flex',alignItems:'center',gap:'8px',marginBottom:'10px'}}>
            <b style={{color:C.text,fontSize:'14px'}}>🏢 {supplierName}</b>
            <span style={{fontSize:'12px',color:C.textSec}}>{rows.length+' поз.'}</span>
          </div>
          <div style={{overflowX:'auto'}}>
            <table style={{width:'100%',borderCollapse:'collapse',fontSize:'12px'}}>
              <thead>
                <tr style={{color:C.textMuted,textAlign:'left'}}>
                  <th style={{...tblH}}>Материал</th>
                  <th style={tblH}>Цена</th>
                  <th style={tblH}>Ед.</th>
                  <th style={tblH}>Мин. партия</th>
                  <th style={tblH}>Срок</th>
                  <th style={tblH}>Наличие</th>
                </tr>
              </thead>
              <tbody>
                {rows.map(item=>(
                  <tr key={item.id} style={{borderTop:'1px solid '+C.border}}>
                    <td style={{...tblC,fontWeight:'600',color:C.text}}>{item.materialName}</td>
                    <td style={{...tblC,whiteSpace:'nowrap'}}>{(item.price||0).toLocaleString('ru-RU')+' ₽'}</td>
                    <td style={tblC}>{item.unit}</td>
                    <td style={tblC}>{item.minQuantity}</td>
                    <td style={tblC}>{(item.deliveryDays||0)+' дн.'}</td>
                    <td style={tblC}>{item.inStock?<span style={badge(C.success,C.successLight,C.successBorder)}>В наличии</span>:<span style={badge(C.textMuted,C.bg,C.border)}>Под заказ</span>}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      ))}
    </div>
  );
}

export default SupplyCatalogPanel;
