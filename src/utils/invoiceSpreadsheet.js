import {invoiceScanNumber} from './invoiceScanValidation';

export const invoiceSpreadsheetAccept = '.xlsx,.xls,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet,application/vnd.ms-excel';
export const isInvoiceSpreadsheet = file => /\.(xlsx|xls)$/i.test(file?.name || '')
  || /application\/vnd\.(ms-excel|openxmlformats-officedocument.spreadsheetml.sheet)/i.test(file?.type || '');
const label = value => String(value ?? '').toLowerCase().replace(/ё/g,'е').replace(/\s+/g,' ').trim();
const nameHeader = value => /наименован|^название$|номенклатур|^name$/.test(label(value));
const qtyHeader = value => /количество|кол-?во|^кол\.?$|^quantity$|^qty$/.test(label(value)) && !/код/.test(label(value));
const withVat = value => /с\s*ндс|с налогом|с учетом/.test(label(value)) && !/без/.test(label(value));
const money = value => invoiceScanNumber(value);
const spreadsheetVatRate = value => {
  const text=String(value ?? '').trim();
  if (!text) return null;
  if (/без\s*ндс/i.test(text)) return 0;
  let parsed=money(text.replace('%',''));
  if (parsed !== null && parsed>0 && parsed<1) parsed=Math.round(parsed*1000000)/10000;
  if (![0,20,22].includes(parsed)) throw new Error('Ставка НДС в Excel не поддерживается. Проверьте документ вручную.');
  return parsed;
};

export function parseInvoiceSpreadsheetRows(rows) {
  const headerIndex = rows.findIndex(row => row.some(nameHeader) && row.some(qtyHeader));
  if (headerIndex < 0) return null;
  const header = rows[headerIndex];
  const column = test => header.findIndex(cell => test(label(cell)));
  const name = header.findIndex(nameHeader), quantity = header.findIndex(qtyHeader);
  const unit = column(text => /^(ед\.?|единица|единицы|unit)|условное обозначение/.test(text) && !/код/.test(text));
  const article = column(text => /артикул|код товара/.test(text));
  const rate = column(text => /налоговая ставка|ставка.*ндс|^ндс\s*%?$/.test(text));
  const amountColumns = header.map((text,index)=>({text:label(text),index})).filter(({text}) =>
    /стоимость|сумма|^итого$|^total$/.test(text) && !/акциз/.test(text)
    && !(/сумма.*налог|сумма.*ндс/.test(text) && !withVat(text) && !/без.*ндс|без налога/.test(text)));
  const grossColumn = amountColumns.find(({text})=>withVat(text)) || amountColumns.filter(({text})=>!/без.*ндс|без налога/.test(text)).slice(-1)[0];
  const gross = grossColumn?.index ?? -1;
  const base = amountColumns.find(({text})=>/без.*ндс|без налога/.test(text))?.index ?? -1;
  const tax = column(text => /сумма.*налог|сумма.*ндс/.test(text) && !withVat(text) && !/без.*ндс|без налога/.test(text));
  const price = column(text => /^цена|^тариф|^price$/.test(text));
  if (price < 0 && gross < 0) throw new Error('В Excel не найдены колонки цены или суммы строки. Укажите заголовки колонок.');
  const docText = rows.slice(0,headerIndex).map(row=>row.join(' ')).join('\n');
  const doc = docText.match(/(?:упд|счет[ -]фактура|счет(?: на оплату)?|накладная)\s*№\s*([^\s]+)\s*от\s*(\d{1,2}[./-]\d{1,2}[./-]\d{4})/i);
  const supplierRow = rows.slice(0,headerIndex).find(row=>row.some(cell=>/^(поставщик|продавец)\s*:?$/i.test(String(cell).trim())));
  const supplierIndex = supplierRow?.findIndex(cell=>/^(поставщик|продавец)\s*:?$/i.test(String(cell).trim()));
  const supplier = supplierRow ? supplierRow.slice(supplierIndex+1).find(value=>String(value).trim()) || '' : '';
  const result = {documentType:'supplier_invoice',number:doc?.[1] || '',date:doc?.[2] || '',supplier,items:[],pagesCount:1,
    recognition:{method:'spreadsheet',label:'Прочитано из Excel',warnings:[]}};
  const rates = new Set();
  for (let index=headerIndex+1;index<rows.length;index++) {
    const row=rows[index];
    if (!row.some(value=>String(value ?? '').trim())) continue;
    const rowText=row.map(label).join(' ');
    if (/всего к оплате|^\s*(итого|всего)(?:\s|:|$)/.test(rowText)) {
      const laterItems=rows.slice(index+1).some(next=>String(next[name] ?? '').trim()
        && money(next[quantity])>0 && ((gross>=0 && money(next[gross])!==null) || (price>=0 && money(next[price])!==null)));
      if (laterItems) throw new Error('После итога Excel есть ещё товарные строки. Оставьте одну полную таблицу без промежуточных итогов.');
      if (gross >= 0 && money(row[gross]) !== null) result.totalWithVat=money(row[gross]);
      if (base >= 0 && money(row[base]) !== null) result.totalBase=money(row[base]);
      if (tax >= 0 && money(row[tax]) !== null) result.totalVat=money(row[tax]);
      break;
    }
    if (nameHeader(row[name]) || ['1а','а'].includes(label(row[name]))) continue;
    const itemName=String(row[name] ?? '').trim();
    if (!itemName) continue;
    const qty=money(row[quantity]);
    if (qty === null || qty <= 0) throw new Error(`Excel, строка ${index+1}: количество не читается. Проверьте исходную таблицу.`);
    const total=gross >= 0 ? money(row[gross]) : null;
    let unitPrice=price >= 0 ? money(row[price]) : null;
    if (gross >= 0 && total === null) throw new Error(`Excel, строка ${index+1}: сумма строки не читается.`);
    const priceWithoutVat = price >= 0 && /без.*ндс|без налога/.test(label(header[price]));
    const vatRate=rate>=0 ? spreadsheetVatRate(row[rate]) : null;
    if (priceWithoutVat && gross<0 && vatRate!==0 && !/без\s*ндс/i.test(docText)) {
      throw new Error('В Excel указана цена без НДС, но нет суммы с НДС. Добавьте колонку суммы с НДС или проверьте документ вручную.');
    }
    if (total !== null && (unitPrice === null || priceWithoutVat || withVat(header[gross]) || (base >= 0 && gross !== base))) unitPrice=total/qty;
    if (unitPrice === null || unitPrice < 0) throw new Error(`Excel, строка ${index+1}: цена не читается.`);
    if (vatRate !== null) rates.add(vatRate);
    result.items.push({name:itemName,article:article >= 0 ? String(row[article] ?? '') : '',quantity:qty,
      unit:unit >= 0 ? String(row[unit] || 'шт') : 'шт',price:unitPrice,lineTotal:total ?? Math.round(qty*unitPrice*100)/100});
    if (result.items.length>500) throw new Error('В одной накладной допускается не более 500 позиций. Разделите файл.');
  }
  if (!result.items.length) throw new Error('В Excel нет товарных строк под найденными заголовками.');
  if (rates.size>1) throw new Error('В Excel разные ставки НДС. Разделите документ по ставкам или проверьте его вручную.');
  if (rates.size===1) {
    result.vatRate=[...rates][0];
    result.vat=result.vatRate ? `С НДС ${result.vatRate}%` : 'Без НДС';
  } else if (/без\s*ндс/i.test(docText)) result.vat='Без НДС';
  else result.recognition.warnings.push('Ставка НДС в Excel не определена. Выберите её по оригиналу перед сохранением.');
  return result;
}

export async function readInvoiceSpreadsheet(file) {
  if (!isInvoiceSpreadsheet(file)) throw new Error('Для таблицы накладной выберите XLSX или XLS.');
  if (file.size>15*1024*1024) throw new Error('Excel накладной должен быть не больше 15 МБ.');
  const bytes=await new Promise((resolve,reject)=>{
    const reader=new FileReader();
    reader.onload=()=>resolve(reader.result);
    reader.onerror=()=>reject(new Error('Не удалось прочитать Excel.'));
    reader.readAsArrayBuffer(file);
  });
  const XLSX=await import('xlsx');
  let book;
  try { book=XLSX.read(bytes,{type:'array',cellDates:false,sheetRows:1201}); }
  catch (_error) { throw new Error('Excel повреждён или защищён паролем. Сохраните обычный XLSX и повторите.'); }
  if (book.SheetNames.length>8) throw new Error('В книге больше 8 листов. Оставьте только одну накладную.');
  const documents=[];
  for (const name of book.SheetNames) {
    const sheet=book.Sheets[name];
    const range=XLSX.utils.decode_range(sheet['!fullref'] || sheet['!ref'] || 'A1');
    if (range.e.r>1200 || range.e.c>100) throw new Error('Таблица Excel слишком большая. Оставьте одну накладную до 500 позиций.');
    for (const [address,cell] of Object.entries(sheet)) {
      if (!address.startsWith('!') && cell.f && (cell.v === undefined || cell.v === null || cell.t === 'e')) {
        throw new Error('В Excel есть формулы без рассчитанного результата. Пересчитайте и сохраните файл в Excel.');
      }
    }
    const parsed=parseInvoiceSpreadsheetRows(XLSX.utils.sheet_to_json(sheet,{header:1,defval:'',raw:true}));
    if (parsed) documents.push(parsed);
  }
  if (documents.length!==1) throw new Error(documents.length ? 'В книге несколько товарных таблиц. Оставьте одну накладную в файле.' : 'Не найдена таблица с заголовками «Наименование» и «Количество».');
  return documents[0];
}
