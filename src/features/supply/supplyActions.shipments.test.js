import {createSupplyActions} from './supplyActions';

describe('shipment retries',()=>{
 const originalFetch=global.fetch;
 beforeEach(()=>{global.fetch=jest.fn();jest.spyOn(window,'alert').mockImplementation(()=>{});});
 afterEach(()=>{global.fetch=originalFetch;jest.restoreAllMocks();});
 const deps=()=>({API:'/api',user:{id:7,role:'поставщик'},shipmentForm:{requestId:'12345678-1234-4234-8234-123456789012',shippedItems:[{materialName:'Кабель',unit:'м',workPackage:'Основная',shippedQuantity:'4'},{materialName:'Труба',unit:'шт',workPackage:'Основная',shippedQuantity:'0'}]},setShipmentForm:jest.fn(),setShippingOfferId:jest.fn(),notify:jest.fn(),refreshData:jest.fn().mockResolvedValue()});
 it('keeps the same batch on a network retry and preserves zero quantities',async()=>{
  const context=deps(),actions=createSupplyActions(context);
  global.fetch.mockRejectedValueOnce(new Error('network')).mockResolvedValueOnce({ok:true,json:async()=>({id:16})});
  expect(await actions.createShipmentFromOffer({id:70})).toBe(false);
  expect(context.setShipmentForm).not.toHaveBeenCalled();
  expect(await actions.createShipmentFromOffer({id:70})).toBe(true);
  expect(global.fetch.mock.calls[0][1].body).toBe(global.fetch.mock.calls[1][1].body);
  expect(JSON.parse(global.fetch.mock.calls[1][1].body).shippedItems.map(i=>i.shippedQuantity)).toEqual([4,0]);
  expect(context.notify).toHaveBeenCalledTimes(1);
 });
 it('does not silently substitute the full order for a blank quantity',async()=>{
  const context=deps();context.shipmentForm.shippedItems[0].shippedQuantity='';
  expect(await createSupplyActions(context).createShipmentFromOffer({id:70})).toBe(false);
  expect(global.fetch).not.toHaveBeenCalled();
 });
});
