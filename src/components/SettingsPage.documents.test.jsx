import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import SettingsPage from './SettingsPage';

jest.mock('./SitePricingSettingsPanel', () => () => null);
jest.mock('../features/client-account/ClientContractsReadOnlyPanel', () => () => null);
const props = () => ({
  API: '', C: {}, btnB:{},btnG:{},btnO:{},btnR:{},card:{},inp:{},
  selectedCompanyId: 1, companyDocuments: [
    {id:1,companyId:1,docType:'Устав',name:'Own charter'},
    {id:2,companyId:2,docType:'Устав',name:'Foreign charter'},
    {id:3,companyId:null,docType:'Устав',name:'Unassigned charter'},
  ], companyReqForm:{},companyRequisites:{},newCompanyDoc:{name:'Draft',docType:'Устав',expiresAt:'',fileUrl:''},
  settingsTab:'documents',showForm:false,user:{role:'бухгалтер'},
  loadAll:jest.fn(),setNewCompanyDoc:jest.fn(),setShowForm:jest.fn(),
  setShowPhotoModal:jest.fn(),setSettingsTab:jest.fn(),uploadPhoto:jest.fn(),
});
afterEach(() => jest.restoreAllMocks());
test('only selected company documents appear; all-company view stays closed', () => {
  const p=props(); const view=render(<SettingsPage {...p}/>);
  expect(screen.queryByText('Own charter')).not.toBeNull();
  expect(screen.queryByText('Foreign charter')).toBeNull();
  expect(screen.queryByText('Unassigned charter')).toBeNull();
  view.rerender(<SettingsPage {...p} selectedCompanyId={null}/>);
  expect(screen.queryByText('Own charter')).toBeNull();
  expect(screen.getByRole('status').textContent).toContain('Выберите компанию');
});
test('failed deletion shows error without reloading or clearing the form', async () => {
  const p=props(); global.fetch=jest.fn().mockResolvedValue({ok:false,json:async()=>({detail:'Нет доступа'})});
  const view=render(<SettingsPage {...p}/>);
  p.setShowForm.mockClear();
  fireEvent.click(view.container.querySelector('svg.lucide-trash2').closest('button'));
  await waitFor(()=>expect(screen.getByRole('alert').textContent).toBe('Нет доступа'));
  expect(p.loadAll).not.toHaveBeenCalled();
  expect(p.setShowForm).not.toHaveBeenCalled();
  expect(global.fetch.mock.calls[0][1].headers['X-Company-Id']).toBe('1');
});
test('upload finishing after company switch cannot populate the new draft', async () => {
  const p=props(); let finish;
  p.uploadPhoto.mockReturnValue(new Promise(resolve=>{finish=resolve;}));
  const view=render(<SettingsPage {...p} showForm/>);
  fireEvent.change(view.container.querySelector('input[type="file"]'), {target:{files:[new File(['a'],'a.pdf')]}});
  view.rerender(<SettingsPage {...p} selectedCompanyId={2} showForm/>);
  p.setNewCompanyDoc.mockClear();
  finish('/tenant-files/1/content');
  await waitFor(()=>expect(view.container.querySelector('input[type="file"]').disabled).toBe(false));
  expect(p.setNewCompanyDoc).not.toHaveBeenCalled();
});
