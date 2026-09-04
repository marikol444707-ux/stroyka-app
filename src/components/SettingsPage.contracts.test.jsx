import { render, screen, waitFor } from '@testing-library/react';

import SettingsPage from './SettingsPage';


const colors = {
  bg: '#101828', card: '#1d2939', text: '#fff', textSec: '#d0d5dd',
  textMuted: '#98a2b3', border: '#344054', info: '#2684ff',
  infoLight: '#eef6ff', infoBorder: '#2684ff', success: '#0a6',
  successLight: '#e8fff7', successBorder: '#0a6', warning: '#b70',
  warningLight: '#fff7e0', warningBorder: '#b70', danger: '#d22',
  dangerLight: '#fff0f0', dangerBorder: '#d22', accent: '#f60',
};

describe('SettingsPage client contract access', () => {
  beforeEach(() => {
    global.fetch = jest.fn(async url => ({
      ok: true,
      status: 200,
      json: async () => url === '/account/client-contracts' ? {
        readOnly: true,
        items: [{
          id: 101,
          number: 'STK-2026-0101',
          companyName: 'ООО Клиент',
          startsOn: '2026-09-02',
          monthlyFee: 49900,
          status: 'active',
          statusLabel: 'Действует',
          signedFileUrl: '/tenant-files/502/content',
          statusHistory: [],
        }],
      } : {},
    }));
  });

  afterEach(() => jest.restoreAllMocks());

  test('director sees the signed contract in existing documents settings as read only', async () => {
    render(
      <SettingsPage
        API=""
        C={colors}
        btnB={{}}
        btnG={{}}
        btnO={{}}
        btnR={{}}
        card={{}}
        companyDocuments={[]}
        companyReqForm={{}}
        companyRequisites={{}}
        inp={{}}
        loadAll={jest.fn()}
        newCompanyDoc={{name:'',docType:'Прочее',expiresAt:'',fileUrl:''}}
        saveCompanyRequisites={jest.fn()}
        setCompanyReqForm={jest.fn()}
        setCompanyRequisites={jest.fn()}
        setNewCompanyDoc={jest.fn()}
        setShowForm={jest.fn()}
        setShowPhotoModal={jest.fn()}
        settingsTab="documents"
        setSettingsTab={jest.fn()}
        showForm={false}
        uploadPhoto={jest.fn()}
        user={{id:9,role:'директор',companyId:42}}
      />,
    );

    expect(await screen.findByText('STK-2026-0101')).toBeInTheDocument();
    expect(screen.getByText('Только просмотр')).toBeInTheDocument();
    expect(screen.getByRole('link', {name:'Подписанный договор'})).toHaveAttribute(
      'href', '/tenant-files/502/content',
    );
    expect(screen.queryByRole('button', {name:/активировать|аннулировать|прекратить/i})).not.toBeInTheDocument();

    await waitFor(() => expect(global.fetch).toHaveBeenCalledWith(
      '/account/client-contracts',
      expect.objectContaining({credentials: 'include', cache: 'no-store'}),
    ));
    expect(global.fetch.mock.calls.every(([_url, options]) => !options?.method)).toBe(true);
  });
});
