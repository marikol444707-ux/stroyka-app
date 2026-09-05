import { createProjectOperationActions } from './projectOperationActions';


afterEach(() => jest.restoreAllMocks());


test('saving company requisites returns the canonical server response', async () => {
  const saved = {
    id: 17,
    companyId: 42,
    fullName: 'ООО Клиент',
    email: 'office@example.ru',
  };
  global.fetch = jest.fn(async () => ({
    ok: true,
    status: 200,
    json: async () => saved,
  }));
  global.alert = jest.fn();
  const refreshData = jest.fn(async () => {});
  const actions = createProjectOperationActions({
    API: '/api',
    companyReqForm: {fullName: ' ООО Клиент ', email: ' OFFICE@EXAMPLE.RU '},
    refreshData,
  });

  await expect(actions.saveCompanyRequisites()).resolves.toEqual(saved);
  expect(global.fetch).toHaveBeenCalledWith('/api/company-requisites', expect.objectContaining({
    method: 'POST',
    body: JSON.stringify({fullName: ' ООО Клиент ', email: ' OFFICE@EXAMPLE.RU '}),
  }));
  expect(refreshData).toHaveBeenCalledTimes(1);
});

test('failed requisites save stays on the form and explains the failure', async () => {
  global.fetch = jest.fn(async () => ({
    ok: false,
    status: 500,
  }));
  global.alert = jest.fn();
  const refreshData = jest.fn(async () => {});
  const actions = createProjectOperationActions({
    API: '/api',
    companyReqForm: {fullName: 'ООО Клиент'},
    refreshData,
  });

  await expect(actions.saveCompanyRequisites()).resolves.toBeNull();
  expect(global.alert).toHaveBeenCalledWith('Не удалось сохранить реквизиты');
  expect(refreshData).not.toHaveBeenCalled();
  expect(global.alert).not.toHaveBeenCalledWith('Реквизиты сохранены!');
});
