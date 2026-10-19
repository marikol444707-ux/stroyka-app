import { fireEvent, render, screen, waitFor } from '@testing-library/react';

import ProjectBrigadeCreateForm from './ProjectBrigadeCreateForm';

jest.mock('../utils/commandUuid',()=>({commandUuid:()=> '619c59a4-88af-4c11-9e58-765f2b232680'}));


const buildProps = (overrides = {}) => ({
  project: {id: 17, name: 'Лицей'},
  user:{id:9},companyContext:{mode:'company',selectedCompanyId:4},
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

  beforeEach(()=>{sessionStorage.clear();localStorage.clear();});

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

    expect(await screen.findByRole('alert')).toHaveTextContent('Исполнитель не найден в выбранной компании');
    expect(props.setBrigadeContracts).not.toHaveBeenCalled();
    expect(props.setSelectedBrigadeContract).not.toHaveBeenCalled();
  });

  it('sends the staff namespace and keeps the canonical user returned by the server', async () => {
    const props=buildProps({staff:[{id:23,name:'Иван',accessUserId:41}],
      newBrigadeContract:{...buildProps().newBrigadeContract,contractorId:'23',brigadeName:'Иван'},
      brigadeContracts:[{id:70,projectId:17,brigadeName:'Иван',contractorId:23}]});
    window.fetch=jest.fn().mockResolvedValue({ok:true,json:async()=>({ok:true,id:71,companyId:4,projectId:17,contractorId:41})});
    render(<ProjectBrigadeCreateForm {...props}/>);
    fireEvent.click(screen.getByRole('button',{name:'Создать договор'}));
    await waitFor(()=>expect(props.setSelectedBrigadeContract).toHaveBeenCalled());
    expect(JSON.parse(fetch.mock.calls[0][1].body)).toMatchObject({contractorId:'23',contractorRef:{type:'staff',id:23}});
    expect(props.setSelectedBrigadeContract).toHaveBeenCalledWith(expect.objectContaining({contractorId:41}));
  });

  it('rechecks the staff link on the server before opening a visible existing contract',async()=>{
    const props=buildProps({staff:[{id:23,name:'Иван',accessUserId:41}],
      newBrigadeContract:{...buildProps().newBrigadeContract,contractorId:'23',brigadeName:'Иван'},
      brigadeContracts:[{id:70,projectId:17,brigadeName:'Иван',contractorId:41}],openBrigadeContract:jest.fn()});
    window.alert=jest.fn();
    window.fetch=jest.fn().mockResolvedValue({ok:false,json:async()=>({detail:'Доступ исполнителя изменился'})});
    render(<ProjectBrigadeCreateForm {...props}/>);
    fireEvent.click(screen.getByRole('button',{name:'Создать договор'}));
    await waitFor(()=>expect(window.alert).toHaveBeenCalled());
    expect(window.fetch).toHaveBeenCalledTimes(1);
    expect(props.openBrigadeContract).not.toHaveBeenCalled();
  });

  it('uses the company and project confirmed by the server', async () => {
    const props = buildProps();
    window.fetch = jest.fn()
      .mockResolvedValueOnce({ok:true,json:async()=>({ok:true,id:51,companyId:4,projectId:17,manualRequestId:'619c59a4-88af-4c11-9e58-765f2b232680'})})
      .mockResolvedValueOnce({ok:true,json:async()=>[{id:51,companyId:4,projectId:17,brigadeName:'Бригада Север'}]});

    render(<ProjectBrigadeCreateForm {...props} />);
    fireEvent.click(screen.getByRole('button', {name: 'Создать договор'}));

    await waitFor(() => expect(props.setBrigadeContracts).toHaveBeenCalled());
    const appendContract = props.setBrigadeContracts.mock.calls[0][0];
    const [savedContract] = appendContract([]);
    expect(savedContract).toMatchObject({id: 51, companyId: 4, projectId: 17});
    expect(props.setSelectedBrigadeContract).toHaveBeenCalledWith(savedContract);
  });

  it('never opens a same-name contract without an explicit selection', async () => {
    const existing = {id:70,projectId:17,brigadeName:'Бригада Север',contractorId:11};
    const props = buildProps({brigadeContracts:[existing],openBrigadeContract:jest.fn()});
    window.fetch=jest.fn().mockResolvedValue({ok:false,json:async()=>({detail:'Проверка ручного создания'})});
    window.alert=jest.fn();
    render(<ProjectBrigadeCreateForm {...props}/>);
    fireEvent.click(screen.getByRole('button',{name:'Создать договор'}));
    expect(await screen.findByRole('alert')).toHaveTextContent('Проверка ручного создания');
    expect(props.openBrigadeContract).not.toHaveBeenCalled();
    expect(JSON.parse(fetch.mock.calls[0][1].body)).toMatchObject({contractorId:null,contractorRef:{type:'manual',requestId:expect.any(String)}});
  });

  it('checks the explicitly selected contract on the server instead of ranking same-name duplicates', async () => {
    const props=buildProps({brigadeContracts:[
      {id:18,projectId:17,brigadeName:'Бригада Север',contractorId:41,planAmount:2000},
      {id:20,projectId:17,brigadeName:'Бригада Север',contractorId:41,planAmount:0},
    ],openBrigadeContract:jest.fn()});
    window.fetch=jest.fn().mockResolvedValue({ok:false,json:async()=>({detail:'Доступ изменился'})});
    window.alert=jest.fn();
    render(<ProjectBrigadeCreateForm {...props}/>);
    fireEvent.change(screen.getByRole('combobox',{name:'Существующий договор'}),{target:{value:'20'}});
    fireEvent.click(screen.getByRole('button',{name:'Открыть договор'}));
    await waitFor(()=>expect(window.alert).toHaveBeenCalled());
    expect(props.openBrigadeContract).not.toHaveBeenCalled();
    expect(JSON.parse(fetch.mock.calls[0][1].body)).toMatchObject({contractorId:41,contractorRef:{type:'contract',id:20}});
  });

  it('reuses the manual command key after a network failure',async()=>{
    const props=buildProps();
    window.fetch=jest.fn().mockRejectedValue(new Error('network'));
    window.alert=jest.fn();
    render(<ProjectBrigadeCreateForm {...props}/>);
    fireEvent.click(screen.getByRole('button',{name:'Создать договор'}));
    expect(await screen.findByRole('alert')).toHaveTextContent('Проверьте соединение');
    fireEvent.click(screen.getByRole('button',{name:'Повторить сохранённую отправку'}));
    await waitFor(()=>expect(fetch).toHaveBeenCalledTimes(2));
    const refs=fetch.mock.calls.map(call=>JSON.parse(call[1].body).contractorRef);
    expect(refs[0]).toEqual({type:'manual',requestId:expect.stringMatching(/^[0-9a-f-]{36}$/)});
    expect(refs[1]).toEqual(refs[0]);
  });

  it('does not offer a contract from another project with the same name', () => {
    const otherProjectContract = {id: 72, projectId: 99, projectName: 'Лицей', brigadeName: 'Бригада Север', status: 'Подписан', planAmount: 3000};
    const props = buildProps({brigadeContracts: [otherProjectContract]});
    render(<ProjectBrigadeCreateForm {...props} />);
    expect(screen.getByRole('button', {name: 'Создать договор'})).toBeInTheDocument();
  });

  it('opens the existing contract when the server detects a duplicate after the page loaded', async () => {
    const props = buildProps({openBrigadeContract: jest.fn()});
    window.fetch = jest.fn()
      .mockResolvedValueOnce({ok: true, json: async () => ({ok:true,id:70,reused:true,companyId:4,projectId:17,manualRequestId:'619c59a4-88af-4c11-9e58-765f2b232680'})})
      .mockResolvedValueOnce({ok: true, json: async () => ([
        {id:70,companyId:4,projectId:17,projectName:'Лицей',brigadeName:'Бригада Север',status:'Подписан'},
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
