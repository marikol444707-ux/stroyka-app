import { supplierPublicRequisites } from './supplierPublicRequisites';

it('does not send bilateral contract, notes or a price file as global requisites', () => {
  expect(supplierPublicRequisites({ companyName: 'ООО', inn: '7701234567', address: 'Москва',
    notes: 'Private', contractNumber: 'Private', priceUrl: '/private', companyId: 2,
  })).toEqual({ name: 'ООО', inn: '7701234567', legalAddress: 'Москва' });
});
