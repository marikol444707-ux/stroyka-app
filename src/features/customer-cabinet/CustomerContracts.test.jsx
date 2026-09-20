import React from 'react';
import { render, screen } from '@testing-library/react';
import CustomerContracts from './CustomerContracts';

test('only published owned customer contracts can be opened', () => {
  const row = { id: 1, companyId: 2, projectId: 3, side: 'customer', docType: 'Договор', number: 'PUBLIC', scanUrl: '/tenant-files/1/content' };
  render(<CustomerContracts project={{ id: 3, companyId: 2 }} user={{ id: 7 }} C={{}} card={{}}
    loadState={{ documents: { scope: '7:2:3:', status: 'ready' } }} fileSrc={value => value}
    documents={[row, { ...row, id: 2, side: 'contractor', number: 'INTERNAL' },
      { ...row, id: 3, projectId: 4, number: 'FOREIGN' }, { ...row, id: 4, signStatus: 'Аннулирован', number: 'VOID' }]} />);
  expect(screen.getByText('Договор № PUBLIC')).toBeTruthy();
  expect(screen.getAllByRole('link')).toHaveLength(1);
  for (const text of ['INTERNAL', 'FOREIGN', 'VOID']) expect(screen.queryByText(new RegExp(text))).toBeNull();
});
