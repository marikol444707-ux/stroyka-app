import {fireEvent, render, waitFor} from '@testing-library/react';

import ProjectDocumentsRegistryPanel from './ProjectDocumentsRegistryPanel';


const buildProps = (overrides = {}) => ({
  projectId: 17,
  projectName: 'Лицей',
  projectDocuments: [],
  newProjectDoc: {
    side: 'customer',
    docType: 'Договор',
    number: '',
    docDate: '',
    counterparty: '',
    signStatus: 'Не подписан',
    scanUrl: '',
    amount: '',
    notes: '',
    basisContractDocumentId: null,
  },
  setNewProjectDoc: jest.fn(),
  showDocForm: true,
  setShowDocForm: jest.fn(),
  uploadingDoc: false,
  setUploadingDoc: jest.fn(),
  uploadPhoto: jest.fn().mockResolvedValue('/tenant-files/41/content'),
  fileSrc: value => value,
  loadAll: jest.fn(),
  user: {name: 'Директор'},
  C: {
    accent: '#2563eb',
    accentBorder: '#bfdbfe',
    accentLight: '#eff6ff',
    border: '#e5e7eb',
    card: '#ffffff',
    success: '#15803d',
    successLight: '#f0fdf4',
    text: '#111827',
    textMuted: '#6b7280',
    textSec: '#4b5563',
    warning: '#b45309',
    warningBorder: '#fde68a',
    warningLight: '#fffbeb',
  },
  card: {},
  inp: {},
  btnO: {},
  btnG: {},
  btnB: {},
  btnR: {},
  ...overrides,
});


describe('ProjectDocumentsRegistryPanel', () => {
  const originalFetch = global.fetch;

  afterEach(() => {
    global.fetch = originalFetch;
  });

  it('requests a protected URL for a new project-document scan', async () => {
    const props = buildProps();
    const {container} = render(<ProjectDocumentsRegistryPanel {...props}/>);
    const file = new File(['scan'], 'contract.pdf', {type: 'application/pdf'});
    const fileInputs = container.querySelectorAll('input[type="file"]');

    fireEvent.change(fileInputs[0], {target: {files: [file]}});

    await waitFor(() => expect(props.uploadPhoto).toHaveBeenCalledWith(file, {
      projectId: 17,
      projectName: 'Лицей',
      context: 'project-documents',
      preferProtectedUrl: true,
    }));
    expect(props.setNewProjectDoc).toHaveBeenCalled();
    const updater=props.setNewProjectDoc.mock.calls.at(-1)[0];
    expect(updater(props.newProjectDoc)).toMatchObject({
      scanUrl:'/tenant-files/41/content',signStatus:'Не подписан',
    });
  });

  it('starts a clean next version from a frozen customer contract', () => {
    const props=buildProps({
      showDocForm:false,
      projectDocuments:[{
        id:9,projectName:'Лицей',side:'customer',docType:'Договор',number:'1',
        docDate:'2026-10-01',counterparty:'ООО Заказчик',signStatus:'Подписан',
        scanUrl:'/tenant-files/9/content',contractVersion:1,
        partySnapshot:{schemaVersion:1},partySnapshotHash:'a'.repeat(64),notes:'',
      }],
    });
    const {getByRole}=render(<ProjectDocumentsRegistryPanel {...props}/>);
    fireEvent.click(getByRole('button',{name:/Новая версия/i}));
    expect(props.setNewProjectDoc).toHaveBeenCalledWith(expect.objectContaining({
      revisesDocumentId:9,number:'1',signStatus:'Не подписан',scanUrl:'',
    }));
    expect(props.setShowDocForm).toHaveBeenCalledWith(true);
  });

  it('prefills the exact project customer when opening a new document', () => {
    const props=buildProps({showDocForm:false,projectCustomerName:'ООО Заказчик'});
    const {getByRole}=render(<ProjectDocumentsRegistryPanel {...props}/>);
    fireEvent.click(getByRole('button',{name:/Добавить документ/i}));
    expect(props.setNewProjectDoc).toHaveBeenCalledWith(expect.objectContaining({
      counterparty:'ООО Заказчик',revisesDocumentId:null,scanUrl:'',
    }));
    expect(props.setShowDocForm).toHaveBeenCalledWith(true);
  });

  it('keeps the recognition upload compatible while binding it to the exact project', async () => {
    const props = buildProps();
    const {container} = render(<ProjectDocumentsRegistryPanel {...props}/>);
    const file = new File(['scan'], 'recognition-source.pdf', {type: 'application/pdf'});
    const fileInputs = container.querySelectorAll('input[type="file"]');

    fireEvent.change(fileInputs[1], {target: {files: [file]}});

    await waitFor(() => expect(props.uploadPhoto).toHaveBeenCalledWith(file, {
      projectId: 17,
      projectName: 'Лицей',
      context: 'project-contract-documents',
    }));
  });

  it('requests a protected URL when adding a scan to an existing project document', async () => {
    global.fetch = jest.fn().mockResolvedValue({ok: true});
    const props = buildProps({
      showDocForm: false,
      projectDocuments: [{
        id: 9,
        projectName: 'Лицей',
        side: 'customer',
        docType: 'Договор',
        number: '1',
        docDate: '',
        counterparty: '',
        signStatus: 'Не подписан',
        scanUrl: '',
        notes: '',
      }],
    });
    const {container} = render(<ProjectDocumentsRegistryPanel {...props}/>);
    const file = new File(['scan'], 'signed-contract.pdf', {type: 'application/pdf'});
    const fileInputs = container.querySelectorAll('input[type="file"]');

    fireEvent.change(fileInputs[0], {target: {files: [file]}});

    await waitFor(() => expect(props.uploadPhoto).toHaveBeenCalledWith(file, {
      projectId: 17,
      projectName: 'Лицей',
      context: 'project-documents',
      preferProtectedUrl: true,
    }));
  });

  it('selects the only signed customer contract when KS-2 is chosen', () => {
    const contract={
      id:40,projectName:'Лицей',side:'customer',docType:'Договор',number:'15',
      contractVersion:2,partySnapshot:{schemaVersion:1},signStatus:'Подписан',
      scanUrl:'/tenant-files/40/content',
    };
    const props=buildProps({projectDocuments:[contract]});
    const {getByDisplayValue}=render(<ProjectDocumentsRegistryPanel {...props}/>);
    fireEvent.change(getByDisplayValue('Договор'),{target:{value:'Акт КС-2'}});
    expect(props.setNewProjectDoc).toHaveBeenCalledWith(expect.objectContaining({
      docType:'Акт КС-2',basisContractDocumentId:40,
    }));
  });

  it('does not save a signed KS act without an exact contract basis', () => {
    const alert=jest.spyOn(window,'alert').mockImplementation(()=>{});
    const props=buildProps({newProjectDoc:{...buildProps().newProjectDoc,
      docType:'Акт КС-2',signStatus:'Подписан',scanUrl:'/tenant-files/78/content',
    }});
    global.fetch=jest.fn();
    const {getByRole}=render(<ProjectDocumentsRegistryPanel {...props}/>);
    fireEvent.click(getByRole('button',{name:/Сохранить/i}));
    expect(alert).toHaveBeenCalledWith('Выберите договор-основание для КС');
    expect(global.fetch).not.toHaveBeenCalled();
    alert.mockRestore();
  });

  it('shows the frozen KS contract basis without offering a contract revision', () => {
    const props=buildProps({showDocForm:false,projectDocuments:[{
      id:44,projectName:'Лицей',side:'customer',docType:'Акт КС-3',number:'3',
      signStatus:'Подписан',scanUrl:'/tenant-files/78/content',notes:'',
      partySnapshot:{documentKind:'customerWorkAct',contractBasis:{documentId:40,number:'15',version:2}},
    }]});
    const {getByText,queryByRole}=render(<ProjectDocumentsRegistryPanel {...props}/>);
    expect(getByText('Стороны и договор-основание зафиксированы')).toBeInTheDocument();
    expect(getByText('По договору № 15 · версия 2')).toBeInTheDocument();
    expect(queryByRole('button',{name:/Новая версия/i})).not.toBeInTheDocument();
  });
});
