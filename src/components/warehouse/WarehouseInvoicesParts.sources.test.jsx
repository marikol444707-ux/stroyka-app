import React from 'react';
import { render, screen } from '@testing-library/react';
import { WarehouseInvoiceCard } from './WarehouseInvoicesParts';

const line = invoiceLineIndex => ({ name: 'Кабель', workPackage: 'Электрика', unit: 'м', quantity: 10, invoiceLineIndex });
const transfer = changes => ({ companyId: 2, invoiceId: 5, invoiceLineIndex: 2, materialName: 'Кабель', workPackage: 'Электрика', unit: 'м', quantity: 3, fromLocation: 'Школа', invoiceLineKey: 'кабель|электрика|м', ...changes });
const show = (isMobile, materialTransfers, items = [line(2), line(5)], invChanges = {}) => render(<WarehouseInvoiceCard
  inv={{ id: 5, companyId: 2, number: 'TEST', project: 'Школа', ...invChanges }} invoiceRows={{ items }}
  estimateControl={[]} estimateIssues={[]} isSupplyDeliveryInvoice={() => false} renderControlBadge={() => null}
  projectName="Школа" materialTransfers={materialTransfers} C={{}} card={{}} isMobile={isMobile} />);
const issued = mobile => screen.getAllByText(mobile ? /^Выдано из накладной/ : /^Накл выд:/).map(el => el.textContent);
const remaining = mobile => screen.getAllByText(mobile ? /^Осталось по накладной/ : /^Накл ост:/).map(el => el.textContent);

describe.each([false, true])('source balances mobile=%s', mobile => {
  test('same-name lines use exact index and company, not material key', () => {
    show(mobile, [transfer({}), transfer({ invoiceLineIndex: 5, quantity: 1 }),
      transfer({ companyId: 3, quantity: 80 }), transfer({ invoiceId: 9, quantity: 70 }),
      transfer({ status: 'Аннулирована', quantity: 60 }), transfer({ invoiceLineIndex: 0, quantity: 50 })]);
    expect(issued(mobile)[0]).toMatch(/3 м$/);
    expect(issued(mobile)[1]).toMatch(/1 м$/);
    expect(remaining(mobile)[0]).toMatch(/7 м$/);
    expect(remaining(mobile)[1]).toMatch(/9 м$/);
  });

  test.each([
    { invoiceLineIndex: undefined }, { invoiceLineIndex: '2' },
    { companyId: undefined }, { invoiceId: undefined, invoiceLineIndex: undefined },
    { invoiceLineIndex: undefined, materialName: 'Переименованный материал', invoiceLineKey: 'old-key' },
  ])('legacy potentially related transfer is unverified, not zero: %j', changes => {
    show(mobile, [transfer(changes)], [line(2)]);
    expect(issued(mobile)[0]).toMatch(/не подтверждено$/);
    expect(remaining(mobile)[0]).toMatch(/не подтверждено$/);
  });

  test.each([[line(undefined)], [line(2), line(2)]])('unidentified or duplicate receipt line has no asserted balance %#', (...items) => {
    show(mobile, [], items);
    issued(mobile).forEach(value => expect(value).toMatch(/не подтверждено$/));
    remaining(mobile).forEach(value => expect(value).toMatch(/не подтверждено$/));
  });

  test('unrelated legacy material or explicit foreign company does not taint exact zero', () => {
    show(mobile, [transfer({ invoiceId: null, invoiceLineIndex: null, materialName: 'Краска', invoiceLineKey: 'краска|электрика|м' }),
      transfer({ invoiceLineIndex: null, companyId: 3 })], [line(2)]);
    expect(issued(mobile)[0]).toMatch(/0 м$/);
  });

  test('exact identity wins over stale material names and string ids retain company checks', () => {
    show(mobile, [transfer({ companyId: '2', invoiceId: '5', materialName: 'Старое имя', invoiceLineKey: 'old', quantity: 2 })], [line(2)]);
    expect(issued(mobile)[0]).toMatch(/2 м$/);
    expect(remaining(mobile)[0]).toMatch(/8 м$/);
  });

  test('missing receipt company cannot claim a verified zero balance', () => {
    show(mobile, [], [line(2)], { companyId: null });
    expect(issued(mobile)[0]).toMatch(/не подтверждено$/);
  });

  test('exact plus ambiguous legacy issuance remains unverified', () => {
    show(mobile, [transfer({}), transfer({ invoiceLineIndex: null, quantity: 1 })], [line(2)]);
    expect(issued(mobile)[0]).toMatch(/не подтверждено$/);
    expect(remaining(mobile)[0]).toMatch(/не подтверждено$/);
  });
});
