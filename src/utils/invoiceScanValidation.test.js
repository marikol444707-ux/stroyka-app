import {validateInvoiceScan} from './invoiceScanValidation';

const goodInvoice = () => ({totalWithVat:106880, items:[
  ...[6,6,42,26,40,120].map((quantity, index)=>({name:'Synthetic plaster',article:String(index),quantity,price:400,lineTotal:quantity*400})),
  {name:'Synthetic primer',quantity:20,price:544,lineTotal:10880},
]});

test('preserves all seven rows and agrees with the source total',()=>{
  const data=goodInvoice(), original=JSON.parse(JSON.stringify(data));
  expect(validateInvoiceScan(data)).toMatchObject({valid:true,itemsTotal:106880,documentTotal:106880});
  expect(data).toEqual(original);
});

test('unit codes in quantities cannot pass a correct document total',()=>{
  const data=goodInvoice();
  data.items.forEach(item=>{item.quantity=796;item.lineTotal=796*item.price;});
  expect(validateInvoiceScan(data).errors).toContainEqual(expect.objectContaining({code:'document_total_mismatch'}));
});

test('matching sum cannot hide wrong row multiplication',()=>{
  const data=goodInvoice();
  data.items[0].quantity=796;
  expect(validateInvoiceScan(data).errors).toContainEqual(expect.objectContaining({code:'line_total_mismatch',row:1}));
});

test('796 is a valid real quantity when arithmetic agrees',()=>{
  expect(validateInvoiceScan({totalWithVat:1592,items:[{name:'Synthetic bolts',quantity:796,price:2}]}).valid).toBe(true);
});

test.each([null,'NaN','Infinity',true,-1,0])('invalid quantity %s is rejected',quantity=>{
  expect(validateInvoiceScan({items:[{name:'Synthetic goods',quantity,price:1}]}).valid).toBe(false);
});

test('permits printed unit-price rounding and localized currency amounts',()=>{
  expect(validateInvoiceScan({totalWithVat:'94 380,00 ₽',items:[{name:'Synthetic goods',quantity:270,price:349.56,lineTotal:94380}]}).valid).toBe(true);
});

test('small discrepancies cannot hide behind percentage tolerance',()=>{
  expect(validateInvoiceScan({...goodInvoice(),totalWithVat:106930}).valid).toBe(false);
});

test('explicit invalid totals are not silently recalculated',()=>{
  const data=goodInvoice();
  data.items[0].lineTotal='NaN';
  expect(validateInvoiceScan(data).valid).toBe(false);
  expect(validateInvoiceScan({...goodInvoice(),totalWithVat:'Infinity'}).valid).toBe(false);
});

test('checks tax components against the total independently of line sums',()=>{
  expect(validateInvoiceScan({...goodInvoice(),totalBase:87606.56,totalVat:19273.44}).valid).toBe(true);
  expect(validateInvoiceScan({...goodInvoice(),totalBase:87606.56,totalVat:1}).errors)
    .toContainEqual(expect.objectContaining({code:'tax_total_mismatch'}));
});
