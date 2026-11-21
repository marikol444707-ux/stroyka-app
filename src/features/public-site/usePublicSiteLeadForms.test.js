import { act, renderHook } from '@testing-library/react';
import { usePublicSiteLeadForms } from './usePublicSiteLeadForms';

afterEach(() => window.localStorage.clear());

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

test('sends the first ad source with the client form and the later partner form', async () => {
  window.history.replaceState({}, '', '/?utm_source=netip&utm_medium=telegram&utm_campaign=ads');
  jest.spyOn(global, 'fetch').mockResolvedValue({ ok: true, json: async () => ({ ok: true, id: 15 }) });
  const { result, unmount } = renderHook(() => usePublicSiteLeadForms(options));
  act(() => { result.current.setLeadConsent(true); });
  await act(async () => { await result.current.submitLead(event); });
  expect(JSON.parse(global.fetch.mock.calls[0][1].body).utm).toEqual({
    utm_source: 'netip',
    utm_medium: 'telegram',
    utm_campaign: 'ads',
  });
  unmount();
  window.history.replaceState({}, '', '/partners');
  const partner = renderHook(() => usePublicSiteLeadForms(options));
  act(() => { partner.result.current.setPartnerConsent(true); });
  await act(async () => { await partner.result.current.submitPartnerLead(event); });
  expect(JSON.parse(global.fetch.mock.calls[1][1].body).utm.utm_source).toBe('netip');
  expect(JSON.parse(global.fetch.mock.calls[1][1].body).source).toBe('Сайт: партнерская заявка');
});

test('still opens the form when the browser blocks localStorage', async () => {
  const original = Object.getOwnPropertyDescriptor(window, 'localStorage');
  Object.defineProperty(window, 'localStorage', {
    configurable: true,
    get() {
      throw new DOMException('blocked');
    },
  });
  window.history.replaceState({}, '', '/?utm_source=netip&utm_medium=telegram&utm_campaign=ads');
  try {
    jest.spyOn(global, 'fetch').mockResolvedValue({ ok: true, json: async () => ({ ok: true, id: 15 }) });
    const { result } = renderHook(() => usePublicSiteLeadForms(options));
    act(() => { result.current.setLeadConsent(true); });
    await act(async () => { await result.current.submitLead(event); });
    expect(result.current.sent).toBe(true);
    expect(JSON.parse(global.fetch.mock.calls[0][1].body).utm.utm_source).toBe('netip');
  } finally {
    Object.defineProperty(window, 'localStorage', original);
    window.history.replaceState({}, '', '/');
  }
});

test('keeps server validation errors distinct from connection failures', async () => {
  jest.spyOn(global, 'fetch').mockResolvedValue({ ok: false, json: async () => ({ detail: 'Проверьте номер телефона' }) });
  const { result } = renderHook(() => usePublicSiteLeadForms(options));
  act(() => { result.current.setLeadConsent(true); });
  await act(async () => { await result.current.submitLead(event); });
  expect(result.current.leadError).toBe('Проверьте номер телефона');
  expect(result.current.sent).toBe(false);
});
