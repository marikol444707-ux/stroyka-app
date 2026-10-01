import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import ProjectBrigadeSelectedHeader from './ProjectBrigadeSelectedHeader';


const styles = {display: 'inline-flex'};
const contract = {
  id: 71, projectId: 17, projectName: 'Лицей 4', brigadeName: 'Иванов Иван',
  contractorType: 'ИП', contractorId: 41, status: 'Черновик', totalAmount: 1000,
};

function props(changes = {}) {
  return {
    projectName: 'Лицей 4', projectId: 17, selectedBrigadeContract: contract,
    setSelectedBrigadeContract: jest.fn(), brigadeContractItems: [],
    setBrigadeContractItems: jest.fn(), setBrigadeContracts: jest.fn(),
    setBrigadePayments: jest.fn(), showPreview: jest.fn(), companyRequisites: {},
    companyName: 'ООО Альянс', staff: [], masterProfiles: [], users: [],
    uploadPhoto: jest.fn().mockResolvedValue('/tenant-files/77/content'),
    C: {text: '#111', textSec: '#555', accent: '#f60', accentLight: '#fee', border: '#ddd', card: '#fff'},
    btnG: styles, btnO: styles, btnB: styles, ...changes,
  };
}

beforeEach(() => {
  global.fetch = jest.fn().mockResolvedValue({
    ok: true,
    json: async () => ({ok: true, status: 'Подписан', signedAt: '2026-10-01',
      contractScanUrl: '/tenant-files/77/content', partySnapshot: {contractor: {fullName: 'Иванов Иван'}}}),
  });
});

test('uploads the protected original before signing and stores the server snapshot', async () => {
  const p = props();
  const {container} = render(<ProjectBrigadeSelectedHeader {...p}/>);
  fireEvent.click(screen.getByRole('button', {name: /Загрузить подписанный договор/i}));
  const file = new File(['contract'], 'signed.pdf', {type: 'application/pdf'});
  fireEvent.change(container.querySelector('input[type="file"]'), {target: {files: [file]}});
  await waitFor(() => expect(p.uploadPhoto).toHaveBeenCalledWith(file, {
    projectId: 17, projectName: 'Лицей 4', context: 'brigade-contracts',
  }));
  await waitFor(() => expect(global.fetch).toHaveBeenCalledWith(expect.stringContaining('/brigade-contracts/71/signature'),
    expect.objectContaining({method: 'POST', body: JSON.stringify({scanUrl: '/tenant-files/77/content'})})));
  expect(p.setSelectedBrigadeContract).toHaveBeenCalledWith(expect.objectContaining({
    status: 'Подписан', contractScanUrl: '/tenant-files/77/content',
  }));
});

test('shows that frozen parties and original are retained', () => {
  render(<ProjectBrigadeSelectedHeader {...props({selectedBrigadeContract: {
    ...contract, status: 'Подписан', contractScanUrl: '/tenant-files/77/content',
    partySnapshot: {customer: {fullName: 'ООО Альянс'}, contractor: {fullName: 'Иванов Иван'}},
  }})}/>);
  expect(screen.getByText('Стороны зафиксированы')).toBeInTheDocument();
  expect(screen.getByText(/оригинал сохранён в документах компании/i)).toBeInTheDocument();
  expect(screen.queryByRole('button', {name: /Загрузить подписанный договор/i})).not.toBeInTheDocument();
});

test('lets an old signed contract freeze its original before a new act', () => {
  render(<ProjectBrigadeSelectedHeader {...props({selectedBrigadeContract: {
    ...contract, status: 'Подписан', partySnapshot: null,
  }})}/>);
  expect(screen.getByRole('button', {name: /Проверить подписанный договор/i})).toBeInTheDocument();
});
