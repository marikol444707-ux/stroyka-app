import {createSupplyActions} from './supplyActions';

test('invoice submission preserves exact tax strings and original quote positions',async()=>{
  const originalFetch=global.fetch;
  const originalFlag=process.env.REACT_APP_SUPPLIER_VAT_RECEIPTS_ENABLED;
  global.fetch=jest.fn().mockResolvedValue({ok:true,json:async()=>({id:9})});
  process.env.REACT_APP_SUPPLIER_VAT_RECEIPTS_ENABLED='true';
  try {
    const actions=createSupplyActions({API:'/api',newOfferInvoice:{invoiceNumber:'TEST',
      amount:'12.30',vatAmount:'0.01',lineTaxes:[{sourceOfferPosition:7,vatAmount:'0.01'},
        {sourceOfferPosition:2,vatAmount:'0.00'}]},notify:jest.fn(),setInvoicingOfferId:jest.fn(),
      setNewOfferInvoice:jest.fn(),refreshData:jest.fn()});
    await actions.createInvoiceFromOffer(4);
    const body=JSON.parse(global.fetch.mock.calls[0][1].body);
    expect(body).toMatchObject({amount:'12.30',vatAmount:'0.01',lineTaxes:[
      {sourceOfferPosition:7,vatAmount:'0.01'},{sourceOfferPosition:2,vatAmount:'0.00'}]});
  } finally {
    global.fetch=originalFetch;
    if(originalFlag===undefined)delete process.env.REACT_APP_SUPPLIER_VAT_RECEIPTS_ENABLED;
    else process.env.REACT_APP_SUPPLIER_VAT_RECEIPTS_ENABLED=originalFlag;
  }
});
