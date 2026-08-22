import React from 'react';
import { act, render, screen, waitFor } from '@testing-library/react';

import AccountingExceptionChecksPanel from './AccountingExceptionChecksPanel';
import { ACCOUNTING_EXCEPTION_SOURCES } from './accountingExceptionChecks';

const counts = () => Object.fromEntries(
  ACCOUNTING_EXCEPTION_SOURCES.map(source => [source, 0]),
);

const clearReport = (companyId = 4) => ({
  version: 'accounting-exception-projection-v1',
  companyId,
  state: 'clear',
  scanComplete: true,
  sourceCounts: counts(),
  findingCount: 0,
  findings: [],
  truncated: false,
  blockers: [],
});

const reviewReport = (companyId = 4) => ({
  ...clearReport(companyId),
  state: 'review_required',
  findingCount: 1,
  findings: [{
    reasonCode: 'accounting_supplier_invoice_overpaid',
    subjectKind: 'supplier_invoice',
    subjectId: 91,
    projectId: 17,
    invoiceAmount: '1000.5',
    paidAmount: '1001',
  }],
});

const jsonResponse = (value, status = 200) => Promise.resolve({
  ok: status >= 200 && status < 300,
  status,
  json: () => Promise.resolve(value),
});

const C = {
  text: '#111827',
  textSec: '#4b5563',
  textMuted: '#6b7280',
  border: '#d1d5db',
  accent: '#f97316',
  accentLight: '#fff7ed',
  success: '#15803d',
  successLight: '#f0fdf4',
  warning: '#a16207',
  warningLight: '#fefce8',
  danger: '#b91c1c',
  dangerLight: '#fef2f2',
};

const renderPanel = (overrides = {}) => render(
  <AccountingExceptionChecksPanel
    API=""
    C={C}
    allowedCompanyIds={new Set([4])}
    card={{}}
    companyMode="company"
    enabled
    isMobile={false}
    selectedCompanyId={4}
    user={{ role: 'бухгалтер' }}
    {...overrides}
  />,
);

describe('AccountingExceptionChecksPanel', () => {
  beforeEach(() => {
    global.fetch = jest.fn();
  });

  afterEach(() => {
    jest.restoreAllMocks();
    delete global.fetch;
  });

  test('is absent by default when frontend environment gates are not configured', () => {
    render(
      <AccountingExceptionChecksPanel
        API=""
        C={C}
        card={{}}
        companyMode="company"
        isMobile={false}
        selectedCompanyId={4}
        user={{ role: 'бухгалтер' }}
      />,
    );

    expect(screen.queryByText('Проверка бухгалтерских связей')).not.toBeInTheDocument();
    expect(global.fetch).not.toHaveBeenCalled();
  });

  test('is absent and performs no read when any frontend gate is closed', () => {
    const cases = [
      { enabled: false },
      { allowedCompanyIds: new Set([5]) },
      { companyMode: 'all_companies' },
      { companyMode: 'COMPANY' },
      { selectedCompanyId: null },
      { user: { role: 'прораб' } },
    ];

    cases.forEach(props => {
      const view = renderPanel(props);
      expect(screen.queryByText('Проверка бухгалтерских связей')).not.toBeInTheDocument();
      view.unmount();
    });
    expect(global.fetch).not.toHaveBeenCalled();
  });

  test('loads one exact cookie-only GET and renders the closed review', async () => {
    global.fetch.mockImplementation(() => jsonResponse(reviewReport()));
    renderPanel();

    expect(await screen.findByText(
      'По накладной поставщика оплачено больше суммы документа',
    )).toBeInTheDocument();
    expect(screen.getByText((_text, element) => (
      element.tagName === 'P'
      && element.textContent === 'Накладная поставщика №91 · Объект №17'
    ))).toBeInTheDocument();
    expect(screen.getByText((_text, element) => (
      element.tagName === 'LI'
      && element.textContent === 'Сумма документа: 1000.5 ₽'
    ))).toBeInTheDocument();
    expect(screen.getByText((_text, element) => (
      element.tagName === 'LI'
      && element.textContent === 'Оплачено: 1001 ₽'
    ))).toBeInTheDocument();

    expect(global.fetch).toHaveBeenCalledTimes(1);
    const [url, options] = global.fetch.mock.calls[0];
    expect(url).toBe('/accounting-exception-checks');
    expect(options.credentials).toBe('include');
    expect(options.signal).toEqual(expect.any(AbortSignal));
    expect(options.method).toBeUndefined();
    expect(options.body).toBeUndefined();
    expect(options.headers).toBeUndefined();
    for (const forbidden of [/оплатить/i, /подтвердить/i, /исправить/i, /применить/i, /изменить статус/i]) {
      expect(screen.queryByRole('button', { name: forbidden })).not.toBeInTheDocument();
    }
  });

  test('renders clear and incomplete as non-actionable review states', async () => {
    global.fetch.mockImplementation(() => jsonResponse(clearReport()));
    const view = renderPanel();
    expect(await screen.findByText('Противоречий в проверенном контуре не найдено')).toBeInTheDocument();
    view.unmount();

    global.fetch.mockImplementation(() => jsonResponse({
      ...clearReport(),
      state: 'incomplete',
      scanComplete: false,
      blockers: ['accounting_exception_projection_source_incomplete'],
    }));
    renderPanel();
    expect(await screen.findByRole('alert')).toHaveTextContent(
      'Проверка не завершена: часть данных не прошла безопасные ограничения',
    );
  });

  test('clears stale findings immediately when the selected company changes', async () => {
    let resolveSecond;
    global.fetch
      .mockImplementationOnce(() => jsonResponse(reviewReport(4)))
      .mockImplementationOnce(() => new Promise(resolve => { resolveSecond = resolve; }));
    const view = renderPanel({ allowedCompanyIds: new Set([4, 5]) });

    expect(await screen.findByText(
      'По накладной поставщика оплачено больше суммы документа',
    )).toBeInTheDocument();
    view.rerender(
      <AccountingExceptionChecksPanel
        API=""
        C={C}
        allowedCompanyIds={new Set([4, 5])}
        card={{}}
        companyMode="company"
        enabled
        isMobile={false}
        selectedCompanyId={5}
        user={{ role: 'бухгалтер' }}
      />,
    );

    await waitFor(() => expect(screen.queryByText(
      'По накладной поставщика оплачено больше суммы документа',
    )).not.toBeInTheDocument());
    expect(screen.getByRole('status')).toHaveTextContent('Проверяем бухгалтерские связи');

    await act(async () => {
      resolveSecond(await jsonResponse(clearReport(5)));
    });
    expect(await screen.findByText('Противоречий в проверенном контуре не найдено')).toBeInTheDocument();
  });

  test('ignores a late response from the previously selected company', async () => {
    let resolveFirst;
    global.fetch
      .mockImplementationOnce(() => new Promise(resolve => { resolveFirst = resolve; }))
      .mockImplementationOnce(() => jsonResponse(clearReport(5)));
    const view = renderPanel({ allowedCompanyIds: new Set([4, 5]) });

    view.rerender(
      <AccountingExceptionChecksPanel
        API=""
        C={C}
        allowedCompanyIds={new Set([4, 5])}
        card={{}}
        companyMode="company"
        enabled
        isMobile={false}
        selectedCompanyId={5}
        user={{ role: 'бухгалтер' }}
      />,
    );
    expect(await screen.findByText('Противоречий в проверенном контуре не найдено')).toBeInTheDocument();

    await act(async () => {
      resolveFirst(await jsonResponse(reviewReport(4)));
      await Promise.resolve();
    });
    expect(screen.queryByText(
      'По накладной поставщика оплачено больше суммы документа',
    )).not.toBeInTheDocument();
    expect(screen.getByText('Противоречий в проверенном контуре не найдено')).toBeInTheDocument();
  });

  test('fails closed without rendering private malformed response fields', async () => {
    global.fetch.mockImplementation(() => jsonResponse({
      ...reviewReport(),
      rawRows: [{ note: 'PRIVATE_NOTE' }],
    }));
    renderPanel();

    expect(await screen.findByRole('alert')).toHaveTextContent(
      'Проверка бухгалтерских связей временно недоступна',
    );
    expect(screen.queryByText(/PRIVATE/)).not.toBeInTheDocument();
    expect(screen.queryByText(
      'По накладной поставщика оплачено больше суммы документа',
    )).not.toBeInTheDocument();
  });

  test('aborts the in-flight read on unmount', () => {
    let signal;
    global.fetch.mockImplementation((_url, options) => {
      signal = options.signal;
      return new Promise(() => {});
    });
    const view = renderPanel();
    expect(signal.aborted).toBe(false);
    view.unmount();
    expect(signal.aborted).toBe(true);
  });
});
