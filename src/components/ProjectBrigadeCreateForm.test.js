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
    fireEvent.click(screen.getByRole('button', {name: 'Создать договор'}));

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
    fireEvent.click(screen.getByRole('button', {name: 'Создать договор'}));

    await waitFor(() => expect(props.setBrigadeContracts).toHaveBeenCalled());
    const appendContract = props.setBrigadeContracts.mock.calls[0][0];
    const [savedContract] = appendContract([]);
    expect(savedContract).toMatchObject({id: 51, companyId: 4, projectId: 17});
    expect(props.setSelectedBrigadeContract).toHaveBeenCalledWith(savedContract);
  });

  it('opens an existing performer contract instead of creating a duplicate', () => {
    const existing = {id: 70, projectName: 'Лицей', brigadeName: 'Бригада Север', status: 'Подписан'};
    const props = buildProps({brigadeContracts: [existing], openBrigadeContract: jest.fn()});
    window.fetch = jest.fn();

    render(<ProjectBrigadeCreateForm {...props} />);
    expect(screen.getByText(/у этого исполнителя уже есть договор/i)).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', {name: 'Открыть договор'}));

    expect(window.fetch).not.toHaveBeenCalled();
    expect(props.openBrigadeContract).toHaveBeenCalledWith(existing);
    expect(props.setSelectedBrigadeContract).not.toHaveBeenCalled();
    expect(props.setShowBrigadeForm).toHaveBeenCalledWith(false);
  });

  it('opens the existing contract when the server detects a duplicate after the page loaded', async () => {
    const props = buildProps({openBrigadeContract: jest.fn()});
    window.fetch = jest.fn()
      .mockResolvedValueOnce({ok: true, json: async () => ({ok: true, id: 70, reused: true})})
      .mockResolvedValueOnce({ok: true, json: async () => ([
        {id: 70, projectName: 'Лицей', brigadeName: 'Бригада Север', status: 'Подписан'},
      ])});

    render(<ProjectBrigadeCreateForm {...props} />);
    fireEvent.click(screen.getByRole('button', {name: 'Создать договор'}));

    await waitFor(() => expect(props.openBrigadeContract).toHaveBeenCalledWith(
      expect.objectContaining({id: 70, status: 'Подписан'}),
    ));
    expect(props.setBrigadeContracts).toHaveBeenCalled();
    expect(props.setSelectedBrigadeContract).not.toHaveBeenCalled();
  });
});
