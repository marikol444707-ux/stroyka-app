import React from 'react';
import { fireEvent, render, screen } from '@testing-library/react';
import RequestKpModal from './RequestKpModal';

it('keeps distinct supplier IDs and changes selection only on an explicit checkbox action', () => {
  const send = jest.fn();
  function Fixture() {
    const [ids, setIds] = React.useState([]);
    return <RequestKpModal showRequestKpModal={7} setShowRequestKpModal={jest.fn()}
      C={{}} card={{}} btnG={{}} btnO={{}} badge={() => ({})}
      supplyRequests={[]} parseSupplyItems={() => []} renderSupplyRequestOrigin={() => null}
      suggestedSuppliers={{ suppliers: [
        { id: 1, name: 'Первый', email: 'same@example.test', aiRecommend: true },
        { id: 2, name: 'Второй', email: 'same@example.test', aiRecommend: true },
      ] }} selectedSupplierIds={ids} setSelectedSupplierIds={setIds} sendKpRequest={send} />;
  }
  render(<Fixture />);
  expect(screen.getAllByRole('checkbox')).toHaveLength(2);
  expect(screen.getByRole('button', { name: 'Отправить (0)' })).toBeDisabled();
  fireEvent.click(screen.getByRole('checkbox', { name: 'Второй' }));
  expect(screen.getByRole('checkbox', { name: 'Второй' })).toBeChecked();
  expect(screen.getByRole('checkbox', { name: 'Первый' })).not.toBeChecked();
  expect(send).not.toHaveBeenCalled();
  fireEvent.click(screen.getByRole('button', { name: 'Отправить (1)' }));
  expect(send).toHaveBeenCalledTimes(1);
});
