import { fireEvent, render, screen, within } from '@testing-library/react';
import ProjectMaterialsTransferPanel from './ProjectMaterialsTransferPanel';
import { TransferRecipientSelect } from './materials/ProjectMaterialsTransferParts';

const staff = [
  {id: 901, accessUserId: 42, name: 'Иван Петров', role: 'мастер'},
  {id: 902, accessUserId: 41, name: 'Иван Петров', role: 'мастер'},
];
const transfers = [
  {id: 1, projectName: 'Объект', toPerson: 'Иван Петров', toUserId: 41, materialName: 'Кабель', unit: 'м', quantity: 10, signed: true},
  {id: 2, projectName: 'Объект', toPerson: 'Иван Петров', toUserId: 42, materialName: 'Кабель', unit: 'м', quantity: 20, signed: true},
];

function renderPanel(overrides = {}) {
  return render(<ProjectMaterialsTransferPanel
    projectName="Объект" C={{}} inp={{}} user={{name: 'Кладовщик'}} staff={staff}
    newTransfer={{toPerson: 'Иван Петров', toUserId: 41, toPersonRole: 'мастер',
      materialName: 'Кабель', unit: 'м', quantity: 1, notes: '', transferDate: '2026-09-18'}}
    setNewTransfer={() => {}} materialTransfers={transfers}
    workJournal={[
      {project: 'Объект', masterId: 41, masterName: 'Прежняя фамилия', materialsUsed: [{name: 'Кабель', quantity: 2}]},
      {project: 'Объект', masterId: 42, masterName: 'Иван Петров', materialsUsed: [{name: 'Кабель', quantity: 3}]},
    ]}
    history={[
      {project: 'Объект', type: 'возврат от мастера', sourceType: 'material_return_user', sourceId: 41,
        issuedBy: 'Прежняя фамилия', material: 'Кабель', quantity: 1},
      {project: 'Объект', type: 'возврат от мастера', sourceType: 'material_return_user', sourceId: 42,
        issuedBy: 'Иван Петров', material: 'Кабель', quantity: 4},
    ]}
    {...overrides}
  />);
}

test('table balances distinguish same-name recipients by transfer user ID', () => {
  renderPanel();
  const rows = screen.getAllByRole('row').slice(1);
  expect(within(rows[0]).getAllByRole('cell')[4]).toHaveTextContent('7 м');
  expect(within(rows[1]).getAllByRole('cell')[4]).toHaveTextContent('13 м');
});

test('form balance follows the selected user instead of the first same-name staff row', () => {
  renderPanel({showTransferForm: true});
  expect(screen.getByText('У получателя: 7 м')).toBeInTheDocument();
});

test('recipient selection sends the linked account ID rather than the staff primary ID', () => {
  const setNewTransfer = jest.fn();
  render(<TransferRecipientSelect staff={staff} newTransfer={{toPerson: '', toUserId: ''}}
    requesterOptions={{requesters: [], requesterNames: new Set()}} setNewTransfer={setNewTransfer}/>);
  const options = screen.getAllByRole('option');
  expect(options.map(option => option.value)).toEqual(['', 'user:42', 'user:41']);
  fireEvent.change(screen.getByRole('combobox'), {target: {value: 'user:41'}});
  expect(setNewTransfer.mock.calls[0][0]({})).toMatchObject({toUserId: 41, toPerson: 'Иван Петров'});
});

test('unlinked staff remain name-only recipients without inventing a user ID', () => {
  const setNewTransfer = jest.fn();
  render(<TransferRecipientSelect staff={[{id: 999, name: 'Пётр Сидоров', role: 'мастер'}]}
    newTransfer={{toPerson: '', toUserId: ''}} requesterOptions={{requesters: [], requesterNames: new Set()}}
    setNewTransfer={setNewTransfer}/>);
  expect(screen.getByRole('option', {name: 'Пётр Сидоров (мастер)'})).toHaveValue('Пётр Сидоров');
  fireEvent.change(screen.getByRole('combobox'), {target: {value: 'Пётр Сидоров'}});
  expect(setNewTransfer.mock.calls[0][0]({})).toMatchObject({toUserId: '', toPerson: 'Пётр Сидоров'});
});
