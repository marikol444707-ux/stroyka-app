import React from 'react';
import { render, screen } from '@testing-library/react';
import AccountingDocumentsPanel from './AccountingDocumentsPanel';

function show(payments) {
  render(<AccountingDocumentsPanel C={{}} card={{}} btnO={{}} btnG={{}} btnB={{}}
    accountingDocProject="Объект" projects={[{ id: 1, companyId: 2, name: 'Объект' }]}
    projectPayments={payments.map(row => ({ ...row, projectName: 'Объект' }))}
    projectPlanDone={() => ({ done: 0 })} badge={() => null}
    materialControlSummaryForProject={() => ({ outsideRows: [], stockMismatchRows: [], toBuyRows: [] })} />);
}

test.each(['Аванс', 'Оплата счёта', 'Оплата бригаде'])('document cost nets ledger reversal: %s', note => {
  show([{ sourceKind: 'supplier_payment_ledger', operationKind: 'payment', amount: 100, note },
    { sourceKind: 'supplier_payment_ledger', operationKind: 'reversal', amount: -100, note }]);
  expect(screen.getByText('Факт расходов').parentElement.querySelector('b')).toHaveTextContent(/^0 ₽$/);
});

test('document cost preserves legacy brigade and act expenses', () => {
  show([{ amount: 20, note: 'Оплата бригаде' }, { amount: 30, note: 'Выплата исполнителю по акту' }]);
  expect(screen.getByText('Факт расходов').parentElement.querySelector('b')).toHaveTextContent(/^50 ₽$/);
});

test.each([0, 2000])('only spent accountable funds enter expenses: %s', spentAmount => {
  render(<AccountingDocumentsPanel C={{}} card={{}} btnO={{}} btnG={{}} btnB={{}}
    accountingDocProject="Объект" projects={[{id:1, companyId:2, name:'Объект'}]}
    accountablePayments={[{projectName:'Объект',amount:10000,spentAmount}, {projectName:'Другой',amount:99999,spentAmount:99999}]}
    projectPayments={[{projectName:'Объект',amount:100,sourceKind:'supplier_payment_ledger'}, {projectName:'Объект',amount:-100,sourceKind:'supplier_payment_ledger'}]}
    projectPlanDone={()=>({done:0})} badge={()=>null}
    materialControlSummaryForProject={()=>({outsideRows:[],stockMismatchRows:[],toBuyRows:[]})}/>);
  expect(screen.getByText('Факт расходов').parentElement.querySelector('b').textContent.replace(/\s/g,'')).toBe(`${spentAmount}₽`);
  expect(screen.getByText(/Выдано под отчёт/).textContent.replace(/\s/g,'')).toContain('10000₽');
});
