import {createSupplyActions} from './supplyActions';
const flag='REACT_APP_SUPPLIER_DOCUMENT_CONTRACT_BINDINGS_ENABLED';
let oldFlag,oldFetch,oldAlert;
beforeEach(()=>{oldFlag=process.env[flag];process.env[flag]='true';oldFetch=global.fetch;oldAlert=global.alert;global.alert=jest.fn();global.fetch=jest.fn().mockResolvedValue({ok:true,json:async()=>({id:9})});});
afterEach(()=>{global.fetch=oldFetch;global.alert=oldAlert;if(oldFlag===undefined)delete process.env[flag];else process.env[flag]=oldFlag;});
function actions(extra={}){return createSupplyActions({API:'/api',newOfferInvoice:{invoiceNumber:'NEW',amount:'200.00',...extra},notify:jest.fn(),setInvoicingOfferId:jest.fn(),setNewOfferInvoice:jest.fn(),refreshData:jest.fn()});}
test.each([{}, {contractVersionId:8,contractOfferId:99},{contractVersionId:0,contractOfferId:4}])('blocks missing or unrelated contract %j',async extra=>{await actions(extra).createInvoiceFromOffer(4);expect(global.fetch).not.toHaveBeenCalled();expect(global.alert).toHaveBeenCalled();});
test('submits the explicitly selected contract with the invoice',async()=>{await actions({contractVersionId:8,contractOfferId:4}).createInvoiceFromOffer(4);expect(JSON.parse(global.fetch.mock.calls[0][1].body).contractVersionId).toBe(8);});
test('disabled rollout does not submit a stale contract selection',async()=>{process.env[flag]='false';await actions({contractVersionId:8,contractOfferId:4}).createInvoiceFromOffer(4);expect(JSON.parse(global.fetch.mock.calls[0][1].body)).not.toHaveProperty('contractVersionId');});
