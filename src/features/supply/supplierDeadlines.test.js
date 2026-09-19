import { defaultResponseDeadline, deadlineState, canPrepareOffer } from './supplierDeadlines';
it('uses Moscow weekdays and keeps Friday time across a weekend',()=>{
  expect(defaultResponseDeadline(new Date('2026-09-18T11:00:00Z'))).toBe('2026-09-21T14:00');
  expect(defaultResponseDeadline(new Date('2026-09-21T21:30:00Z'))).toBe('2026-09-23T00:30');
});
it('classifies only waiting responses with Moscow day boundaries',()=>{
  const now=new Date('2026-09-19T21:10:00Z').getTime();
  expect(deadlineState({status:'Ожидает ответа',responseDueAt:'2026-09-19T22:00:00Z'},now)).toBe('today');
  expect(deadlineState({status:'Ожидает ответа',responseDueAt:'2026-09-19T21:00:00Z'},now)).toBe('overdue');
  expect(deadlineState({status:'Отозвано',responseDueAt:'2026-01-01T00:00:00Z'},now)).toBe('');
  expect(deadlineState({status:'Ожидает ответа'},now)).toBe('undated');
});
it('respects existing payment requirements, latest invoice and shipment presence',()=>{
  const offer={id:2,status:'Утверждено',paymentTerms:'50/50',totalPrice:100};
  expect(canPrepareOffer(offer,[],[])).toBe(false);
  expect(canPrepareOffer(offer,[{id:1,offerId:2,amount:100,paidAmount:50}],[])).toBe(true);
  expect(canPrepareOffer(offer,[{id:1,offerId:2,amount:100,paidAmount:100},{id:2,offerId:2,amount:100,paidAmount:0}],[])).toBe(false);
  expect(canPrepareOffer({...offer,paymentTerms:'Постоплата'},[],[{offerId:2}])).toBe(false);
  expect(canPrepareOffer({...offer,status:'Отозвано',paymentTerms:'Постоплата'},[],[])).toBe(false);
});
