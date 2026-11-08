import {fireEvent, render, screen, waitFor} from '@testing-library/react';

import ProjectWorkJournalPanel from './ProjectWorkJournalPanel';


const buildProps = (photoUrl, overrides = {}) => ({
  project: {id: 17, name: 'Лицей'},
  workJournal: [{
    id: 91,
    project: 'Лицей',
    date: '2026-07-11',
    masterName: 'Мастер',
    description: 'Штукатурка стен',
    quantity: 10,
    unit: 'м2',
    executionTotal: 12000,
    status: 'На проверке',
    photoUrl,
  }],
  workJournalPage: {},
  weatherLog: [],
  listSearch: '',
  setListSearch: jest.fn(),
  matchSearch: () => true,
  setShowJournalTableModal: jest.fn(),
  showPreview: jest.fn(),
  buildJPRContent: jest.fn(),
  showKS2: jest.fn(),
  setEditingJournal: jest.fn(),
  getActStatusForJournal: jest.fn(),
  setEditingAct: jest.fn(),
  openConfirmModal: jest.fn(),
  setRejectingEntry: jest.fn(),
  fileSrc: value => 'https://api.test' + value,
  setShowPhotoModal: jest.fn(),
  C: {
    accent: '#2563eb',
    bg: '#f8fafc',
    border: '#e2e8f0',
    danger: '#dc2626',
    success: '#15803d',
    text: '#0f172a',
    textMuted: '#64748b',
    textSec: '#475569',
  },
  inp: {},
  btnB: {},
  btnG: {},
  btnGr: {},
  btnR: {},
  badge: () => ({}),
  ...overrides,
});


describe('ProjectWorkJournalPanel protected photo preview', () => {
  const originalFetch = global.fetch;
  const originalCreateObjectUrl = global.URL.createObjectURL;
  const originalRevokeObjectUrl = global.URL.revokeObjectURL;

  beforeEach(() => {
    global.fetch = jest.fn();
    global.URL.createObjectURL = jest.fn(() => 'blob:work-journal-photo');
    global.URL.revokeObjectURL = jest.fn();
  });

  afterEach(() => {
    global.fetch = originalFetch;
    if (originalCreateObjectUrl) global.URL.createObjectURL = originalCreateObjectUrl;
    else delete global.URL.createObjectURL;
    if (originalRevokeObjectUrl) global.URL.revokeObjectURL = originalRevokeObjectUrl;
    else delete global.URL.revokeObjectURL;
  });

  it('loads a protected ЖПР photo and opens the resolved Blob URL', async () => {
    const blob = new Blob(['protected-photo'], {type: 'image/png'});
    global.fetch.mockResolvedValue({ok: true, blob: async () => blob});
    const props = buildProps('/tenant-files/51/content');
    const {unmount} = render(<ProjectWorkJournalPanel {...props}/>);

    expect(screen.getByLabelText('Фото ЖПР загружается')).toBeInTheDocument();
    const image = await screen.findByRole('img', {name: 'Фото к записи ЖПР'});
    expect(image).toHaveAttribute('src', 'blob:work-journal-photo');
    expect(global.fetch).toHaveBeenCalledWith(
      'https://api.test/tenant-files/51/content',
      expect.objectContaining({credentials: 'include'}),
    );

    fireEvent.click(image);
    expect(props.setShowPhotoModal).toHaveBeenCalledWith('blob:work-journal-photo');
    expect(props.setEditingJournal).not.toHaveBeenCalled();

    unmount();
    expect(global.URL.revokeObjectURL).toHaveBeenCalledWith('blob:work-journal-photo');
  });

  it('fails closed when a protected ЖПР photo is forbidden', async () => {
    global.fetch.mockResolvedValue({ok: false, status: 403});
    const props = buildProps('/tenant-files/52/content');
    render(<ProjectWorkJournalPanel {...props}/>);

    await waitFor(() => expect(screen.getByLabelText('Фото ЖПР недоступно')).toBeInTheDocument());
    expect(screen.queryByRole('img', {name: 'Фото к записи ЖПР'})).not.toBeInTheDocument();
    expect(props.setShowPhotoModal).not.toHaveBeenCalled();
  });

  it('keeps a compatibility ЖПР photo direct without a Blob request', () => {
    const props = buildProps('/uploads/company-1/work-journal/photo.png');
    render(<ProjectWorkJournalPanel {...props}/>);

    const image = screen.getByRole('img', {name: 'Фото к записи ЖПР'});
    expect(image).toHaveAttribute('src', 'https://api.test/uploads/company-1/work-journal/photo.png');
    expect(global.fetch).not.toHaveBeenCalled();

    fireEvent.click(image);
    expect(props.setShowPhotoModal).toHaveBeenCalledWith('https://api.test/uploads/company-1/work-journal/photo.png');
    expect(props.setEditingJournal).not.toHaveBeenCalled();
  });

  it('opens the printable journal with the exact project identity', () => {
    const project = {id: 17, companyId: 4, name: 'Лицей'};
    const props = buildProps('', {project});
    render(<ProjectWorkJournalPanel {...props}/>);

    fireEvent.click(screen.getByRole('button', {name: /Таблица КС-6а/}));
    expect(props.setShowJournalTableModal).toHaveBeenCalledWith(project);
    fireEvent.click(screen.getByRole('button', {name: /^ЖПР$/}));
    expect(props.buildJPRContent).toHaveBeenCalledWith(project);
  });
});


describe('leadership review of master reports', () => {
  const {createAppRoleRuntime} = require('../features/app-shell/appShellSelectors');
  test.each(['директор', 'зам_директора'])('%s sees the master report and an explicit acceptance action', role => {
    const user = {id: 7, role};
    const roles = createAppRoleRuntime({user});
    const props = buildProps('', {user, canConfirm: roles.isProrab(), showCustomerTotals: true});
    render(<ProjectWorkJournalPanel {...props}/>);
    expect(screen.getByText('👷 Мастер')).toBeInTheDocument();
    expect(screen.getByText('Штукатурка стен')).toBeInTheDocument();
    expect(screen.getByText('10 м2')).toBeInTheDocument();
    const accept = screen.getByRole('button', {name: 'Принять', exact: true});
    expect(accept).toHaveTextContent('Принять');
    fireEvent.click(accept);
    expect(props.openConfirmModal).toHaveBeenCalledWith(props.workJournal[0]);
    expect(props.setEditingJournal).not.toHaveBeenCalled();
  });
  test.each(['мастер','бухгалтер'])('%s cannot confirm from the review panel', role => {
    const roles = createAppRoleRuntime({user: {role}});
    render(<ProjectWorkJournalPanel {...buildProps('', {canConfirm: roles.isProrab()})}/>);
    expect(screen.queryByTitle('Принять (можно пересчитать)')).not.toBeInTheDocument();
  });
});
