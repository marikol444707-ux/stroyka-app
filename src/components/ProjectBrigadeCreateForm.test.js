import { fireEvent, render, screen, waitFor } from '@testing-library/react';

import ProjectBrigadeCreateForm from './ProjectBrigadeCreateForm';


const buildProps = (overrides = {}) => ({
  project: {id: 17, name: 'Лицей'},
  newBrigadeContract: {
    projectId: '',
    projectName: '',
    brigadeName: 'Бригада Север',
    contractorType: 'Своя бригада',
    contractorId: '',
    notes: '',
    pricelistId: '',
  },
  setNewBrigadeContract: jest.fn(),
  staff: [],
  pricelists: [],
  setBrigadeContracts: jest.fn(),
  setSelectedBrigadeContract: jest.fn(),
  setBrigadeContractItems: jest.fn(),
  setBrigadePayments: jest.fn(),
  setShowBrigadeForm: jest.fn(),
  card: {},
  inp: {},
  btnO: {},
  btnG: {},
  ...overrides,
});


describe('ProjectBrigadeCreateForm', () => {
  const originalFetch = window.fetch;
  const originalAlert = window.alert;

  afterEach(() => {
    window.fetch = originalFetch;
    window.alert = originalAlert;
  });

  it('does not add a local contract when the server rejects tenant context', async () => {
    const props = buildProps();
    window.fetch = jest.fn().mockResolvedValue({
      ok: false,
      json: async () => ({detail: 'Исполнитель не найден в выбранной компании'}),
    });
    window.alert = jest.fn();

    render(<ProjectBrigadeCreateForm {...props} />);
    fireEvent.click(screen.getByRole('button', {name: 'Создать'}));

    await waitFor(() => expect(window.alert).toHaveBeenCalledWith(
      'Не удалось создать договор: Исполнитель не найден в выбранной компании',
    ));
    expect(props.setBrigadeContracts).not.toHaveBeenCalled();
    expect(props.setSelectedBrigadeContract).not.toHaveBeenCalled();
  });

  it('uses the company and project confirmed by the server', async () => {
    const props = buildProps();
    window.fetch = jest.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ok: true, id: 51, companyId: 4, projectId: 17}),
    });

    render(<ProjectBrigadeCreateForm {...props} />);
    fireEvent.click(screen.getByRole('button', {name: 'Создать'}));

    await waitFor(() => expect(props.setBrigadeContracts).toHaveBeenCalled());
    const appendContract = props.setBrigadeContracts.mock.calls[0][0];
    const [savedContract] = appendContract([]);
    expect(savedContract).toMatchObject({id: 51, companyId: 4, projectId: 17});
    expect(props.setSelectedBrigadeContract).toHaveBeenCalledWith(savedContract);
  });
});
