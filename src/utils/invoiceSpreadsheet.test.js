import * as XLSX from 'xlsx';
import {parseInvoiceSpreadsheetRows, readInvoiceSpreadsheet} from './invoiceSpreadsheet';
import {validateInvoiceScan} from './invoiceScanValidation';

export const spreadsheetRows = () => [
  ['УПД № SYN-7 от 06.10.2026'], ['Поставщик','Synthetic supplier'],
  ['Артикул','Наименование товара','Код ОКЕИ','Ед.','Количество','Цена без НДС','Стоимость без налога','Налоговая ставка','Сумма налога','Стоимость с налогом'],
  ...[6,6,42,26,40,120].map((quantity,index)=>[String(index),'Synthetic plaster',796,'шт',quantity,327.87,quantity*400/1.22,'22%',quantity*400*22/122,quantity*400]),
  ['PRIMER','Synthetic primer',796,'шт',20,445.90,8918.03,'22%',1961.97,10880],
  ['Всего к оплате','','','','','',87606.56,'',19273.44,106880],
];

function spreadsheetFile(rows, bookType='xlsx') {
  const book=XLSX.utils.book_new();
  XLSX.utils.book_append_sheet(book,XLSX.utils.aoa_to_sheet(rows),'Invoice');
  return new File([XLSX.write(book,{type:'array',bookType})],`synthetic.${bookType}`,{type:bookType==='xls'?'application/vnd.ms-excel':'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'});
}

test.each(['xlsx','xls'])('reads real generated %s bytes without confusing OKEI with quantity',async bookType=>{
  const result=await readInvoiceSpreadsheet(spreadsheetFile(spreadsheetRows(),bookType));
  expect(result.items.map(item=>item.quantity)).toEqual([6,6,42,26,40,120,20]);
  expect(result.items.map(item=>item.price)).toEqual([400,400,400,400,400,400,544]);
  expect(result.items).toHaveLength(7);
  expect(result).toMatchObject({supplier:'Synthetic supplier',number:'SYN-7',date:'06.10.2026',totalWithVat:106880,vat:'С НДС 22%'});
  expect(validateInvoiceScan(result).valid).toBe(true);
});

test('string decimal amounts and simple columns preserve cents',()=>{
  const result=parseInvoiceSpreadsheetRows([['Наименование','Количество','Ед.','Цена','Сумма'],['Synthetic goods','2','л','1 200,50','2 401,00'],['Итого','','','','2401.00']]);
  expect(result.items[0]).toMatchObject({quantity:2,price:1200.5,lineTotal:2401,unit:'л'});
  expect(result.recognition.warnings).toHaveLength(1);
});

test.each([0,'not a number',null])('invalid quantity %s fails instead of dropping a line',quantity=>{
  const rows=spreadsheetRows(); rows[3][4]=quantity;
  expect(()=>parseInvoiceSpreadsheetRows(rows)).toThrow('количество не читается');
});

test('wrong source total remains visible to the arithmetic guard',()=>{
  const rows=spreadsheetRows(); rows[rows.length-1][9]=999;
  expect(validateInvoiceScan(parseInvoiceSpreadsheetRows(rows)).valid).toBe(false);
});

test('missing headers cannot trigger guessed column positions',()=>{
  expect(parseInvoiceSpreadsheetRows([['Synthetic goods',796,'шт',6,400]])).toBe(null);
});

test('uncomputed formulas and multiple invoice sheets are refused',async()=>{
  const book=XLSX.utils.book_new(), sheet=XLSX.utils.aoa_to_sheet(spreadsheetRows());
  sheet.E4={t:'n',f:'SUM(1,5)'};
  XLSX.utils.book_append_sheet(book,sheet,'Invoice');
  await expect(readInvoiceSpreadsheet(new File([XLSX.write(book,{type:'array',bookType:'xlsx'})],'formula.xlsx'))).rejects.toThrow('формулы без рассчитанного результата');
  const other=XLSX.utils.book_new();
  XLSX.utils.book_append_sheet(other,XLSX.utils.aoa_to_sheet(spreadsheetRows()),'One');
  XLSX.utils.book_append_sheet(other,XLSX.utils.aoa_to_sheet(spreadsheetRows()),'Two');
  await expect(readInvoiceSpreadsheet(new File([XLSX.write(other,{type:'array',bookType:'xlsx'})],'two.xlsx'))).rejects.toThrow('несколько товарных таблиц');
});
