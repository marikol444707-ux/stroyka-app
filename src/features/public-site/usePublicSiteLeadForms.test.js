import { act, renderHook } from '@testing-library/react';
import { usePublicSiteLeadForms } from './usePublicSiteLeadForms';

const event = { preventDefault: jest.fn() };
const options = {
  result: { min: 100, max: 200, typeLabel: 'Дом', summary: 'Расчёт' },
  selectedLeadProject: { code: 'FAC-01' },
};

afterEach(() => jest.restoreAllMocks());

test('preserves the customer form after a network failure and allows a retry', async () => {
  jest.spyOn(global, 'fetch').mockRejectedValueOnce(new TypeError('Failed to fetch'))
    .mockResolvedValueOnce({ ok: true, json: async () => ({ ok: true, id: 123 }) });
  const { result } = renderHook(() => usePublicSiteLeadForms(options));
  const lead = { name: 'Тест', phone: '+79990000000', comment: 'Проверка формы' };
  act(() => { result.current.setLead(lead); result.current.setLeadConsent(true); });
  await act(async () => { await result.current.submitLead(event); });
  expect(result.current.sent).toBe(false);
  expect(result.current.lead).toEqual(lead);
  expect(result.current.leadConsent).toBe(true);
  expect(result.current.leadSending).toBe(false);
  expect(result.current.leadError).toContain('Не удалось связаться с сервером заявок');
  await act(async () => { await result.current.submitLead(event); });
  expect(result.current.sent).toBe(true);
  expect(result.current.leadError).toBe('');
  expect(JSON.parse(global.fetch.mock.calls[1][1].body).selectedProject).toEqual(options.selectedLeadProject);
});

test('preserves partner details and explains Safari network errors', async () => {
  jest.spyOn(global, 'fetch').mockRejectedValue(new TypeError('Load failed'));
  const { result } = renderHook(() => usePublicSiteLeadForms(options));
  act(() => {
    result.current.setPartnerLead({ type: 'supplier', name: 'Поставщик', phone: '+79990000000' });
    result.current.setPartnerConsent(true);
  });
  await act(async () => { await result.current.submitPartnerLead(event); });
  expect(result.current.partnerSent).toBe(false);
  expect(result.current.partnerSending).toBe(false);
  expect(result.current.partnerLead.name).toBe('Поставщик');
  expect(result.current.partnerError).toContain('Не удалось связаться с сервером заявок');
});

test('keeps server validation errors distinct from connection failures', async () => {
  jest.spyOn(global, 'fetch').mockResolvedValue({ ok: false, json: async () => ({ detail: 'Проверьте номер телефона' }) });
  const { result } = renderHook(() => usePublicSiteLeadForms(options));
  act(() => { result.current.setLeadConsent(true); });
  await act(async () => { await result.current.submitLead(event); });
  expect(result.current.leadError).toBe('Проверьте номер телефона');
  expect(result.current.sent).toBe(false);
});
