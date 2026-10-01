import {buildInvoiceDocContent} from './printDocumentBuilders';

test('prints frozen shipment parties and destination on a supply receipt', () => {
  const html = buildInvoiceDocContent({
    inv: {
      number:'Н-1', date:'2026-10-01', supplierName:'Текущее имя', acceptedBy:'Кладовщик', project:'Лицей', vat:'Без НДС',
      supplyDeliveryId:51, supplyRequestId:31,
      documentParties:{
        reviewRequired:false,
        supplier:{fullName:'ООО Поставщик <старое>'},
        buyer:{fullName:'ООО Покупатель'},
        consignee:{companyName:'ООО Покупатель',deliveryAddress:'Кисловодск, ул. Школьная, 4',contactName:'Иван',contactPhone:'+7 911'},
        contract:{number:'Д-7',date:'2026-09-20'},
      },
    },
    invoiceRows:{items:[]}, vatCalc:{base:0,vat:0,total:0}, isSupplyDelivery:true,
  });
  expect(html).toContain('ООО Поставщик &lt;старое&gt;');
  expect(html).toContain('Грузополучатель');
  expect(html).toContain('Кисловодск, ул. Школьная, 4');
  expect(html).toContain('Договор № Д-7 от 2026-09-20');
  expect(html).not.toContain('ООО Поставщик <старое>');
});
