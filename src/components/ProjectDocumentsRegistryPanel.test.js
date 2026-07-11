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
});
