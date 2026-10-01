import {fireEvent, render, screen, waitFor} from '@testing-library/react';

import ProjectLettersPanel from './ProjectLettersPanel';


const buildProps = (overrides = {}) => ({
  projectId: 17,
  projectCompanyId: 12,
  projectName: 'Лицей',
  projectLetters: [],
  newLetter: {
    side: 'customer',
    direction: 'outgoing',
    subject: '',
    body: '',
    counterparty: '',
    letterDate: '',
    fileUrl: '',
  },
  setNewLetter: jest.fn(),
  showLetterForm: true,
  setShowLetterForm: jest.fn(),
  uploadingLetter: false,
  setUploadingLetter: jest.fn(),
  uploadPhoto: jest.fn().mockResolvedValue('/tenant-files/31/content'),
  fileSrc: value => value,
  loadAll: jest.fn(),
  user: {name: 'Прораб'},
  C: {
    accent: '#2563eb',
    accentBorder: '#bfdbfe',
    accentLight: '#eff6ff',
    border: '#e5e7eb',
    success: '#15803d',
    successLight: '#f0fdf4',
    text: '#111827',
    textMuted: '#6b7280',
    textSec: '#4b5563',
    warning: '#b45309',
  },
  card: {},
  inp: {},
  btnO: {},
  btnG: {},
  btnB: {},
  btnR: {},
  ...overrides,
});


describe('ProjectLettersPanel', () => {
  it('requests a protected URL for a new letter attachment', async () => {
    const props = buildProps();
    const {container} = render(<ProjectLettersPanel {...props}/>);
    const file = new File(['letter'], 'letter.pdf', {type: 'application/pdf'});

    fireEvent.change(container.querySelector('input[type="file"]'), {
      target: {files: [file]},
    });

    await waitFor(() => expect(props.uploadPhoto).toHaveBeenCalledWith(file, {
      projectId: 17,
      projectName: 'Лицей',
      context: 'project-letters',
      preferProtectedUrl: true,
      companyId: 12,
    }));
  });

  it('returns an incoming customer file with a clear reason', async () => {
    global.fetch = jest.fn(async () => ({ok: true, json: async () => ({ok: true})}));
    const props = buildProps({showLetterForm:false,projectLetters:[{id:9,projectId:17,projectName:'Лицей',
      side:'customer',direction:'incoming',subject:'Акт',fileUrl:'/tenant-files/9/content'},
      {id:10,projectId:99,projectName:'Лицей',side:'customer',direction:'incoming',subject:'Чужой объект'}]});
    render(<ProjectLettersPanel {...props}/>);
    expect(screen.queryByText('Чужой объект')).toBeNull();
    fireEvent.click(screen.getByRole('button',{name:'Запросить исправление'}));
    fireEvent.change(screen.getByLabelText('Что нужно исправить'),{target:{value:'Добавьте страницу с подписью'}});
    fireEvent.click(screen.getByRole('button',{name:'Отправить заказчику'}));
    await waitFor(()=>expect(fetch).toHaveBeenCalledWith(expect.stringMatching(/project-letters\/9\/request-correction$/),
      expect.objectContaining({method:'POST',body:JSON.stringify({reason:'Добавьте страницу с подписью'})})));
    expect(props.loadAll).toHaveBeenCalledTimes(1);
  });

  it('sends a customer letter through the addressed publication endpoint', async () => {
    global.fetch = jest.fn(async () => ({ok: true, json: async () => ({ok: true, deliveryStatus:'sent'})}));
    const props = buildProps({newLetter:{side:'customer',direction:'outgoing',subject:'Акт обследования',
      body:'Ознакомьтесь с документом',counterparty:'',letterDate:'2026-09-29',
      fileUrl:'/tenant-files/31/content'}});
    render(<ProjectLettersPanel {...props}/>);
    fireEvent.click(screen.getByRole('button',{name:'Отправить заказчику'}));
    await waitFor(()=>expect(fetch).toHaveBeenCalledWith(expect.stringMatching(/project-letters\/customer-publications$/),
      expect.objectContaining({method:'POST',credentials:'include',headers:expect.objectContaining({
        'X-Company-Id':'12','X-Company-Mode':'company'}),body:expect.any(String)})));
    const payload=JSON.parse(fetch.mock.calls[0][1].body);
    expect(payload).toEqual(expect.objectContaining({projectId:17,fileId:31,subject:'Акт обследования',
      body:'Ознакомьтесь с документом',letterDate:'2026-09-29',requestId:expect.any(String)}));
    expect(payload).not.toHaveProperty('counterparty');
    expect(props.loadAll).toHaveBeenCalledTimes(1);
  });

  it('shows addressed delivery state in the correspondence history', () => {
    render(<ProjectLettersPanel {...buildProps({showLetterForm:false,projectLetters:[{id:41,projectId:17,
      side:'customer',direction:'outgoing',subject:'Исполнительная схема',deliveryStatus:'sent',
      publishedAt:'2026-09-29T08:30:00Z',publishedByName:'Директор',partySnapshot:{
        sender:{fullName:'ООО Альянс',inn:'2611008712'},recipient:{fullName:'Лицей №4'},
      }}]})}/>);
    expect(screen.getByText(/ООО Альянс → Лицей №4/)).toBeInTheDocument();
    expect(screen.getByText(/ИНН 2611008712/)).toBeInTheDocument();
    expect(screen.getByText(/Директор/)).toBeInTheDocument();
  });
});
