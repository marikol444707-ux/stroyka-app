import React from 'react';
import { fireEvent, render, screen } from '@testing-library/react';
import RequestKpModal from './RequestKpModal';

it('keeps distinct supplier IDs and changes selection only on an explicit checkbox action', () => {
  const send = jest.fn();
  function Fixture() {
    const [ids, setIds] = React.useState([]);
    return <RequestKpModal showRequestKpModal={7} setShowRequestKpModal={jest.fn()}
      C={{}} card={{}} btnG={{}} btnO={{}} badge={() => ({})}
      supplyRequests={[{id:7}]} parseSupplyItems={() => [{materialName:'Труба',quantity:2,unit:'м'}]} renderSupplyRequestOrigin={() => null}
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
  fireEvent.change(screen.getByLabelText('Ответить на КП до (МСК)'),{target:{value:'2000-01-01T14:00'}});
  expect(screen.getByRole('button',{name:'Отправить (1)'})).toBeDisabled();
  fireEvent.change(screen.getByLabelText('Ответить на КП до (МСК)'),{target:{value:'2099-09-21T14:00'}});
  fireEvent.click(screen.getByRole('button', { name: 'Отправить (1)' }));
  expect(send).toHaveBeenCalledTimes(1);
  expect(send).toHaveBeenCalledWith('2099-09-21T14:00:00+03:00', {'2':[0]});
});

it('sends different overlapping item sets to suppliers and blocks empty sets', () => {
  const send=jest.fn();
  const items=[{materialName:'Труба',quantity:2,unit:'м'},{materialName:'Крепёж',quantity:5,unit:'шт'}];
  render(<RequestKpModal showRequestKpModal={7} setShowRequestKpModal={jest.fn()} C={{}} card={{}} btnG={{}} btnO={{}} badge={()=>({})}
    supplyRequests={[{id:7}]} parseSupplyItems={()=>items} renderSupplyRequestOrigin={()=>null}
    suggestedSuppliers={{suppliers:[{id:1,name:'Первый'},{id:2,name:'Второй'}]}} selectedSupplierIds={[1,2]} setSelectedSupplierIds={jest.fn()} sendKpRequest={send}/>);
  fireEvent.click(screen.getByRole('checkbox',{name:'Первый: Крепёж'}));
  fireEvent.click(screen.getByRole('checkbox',{name:'Первый: Труба'}));
  expect(screen.getByRole('button',{name:'Отправить (2)'})).toBeDisabled();
  fireEvent.click(screen.getByRole('checkbox',{name:'Первый: Труба'}));
  fireEvent.click(screen.getByRole('button',{name:'Отправить (2)'}));
  expect(send).toHaveBeenCalledWith(expect.any(String),{'1':[0],'2':[0,1]});
});
