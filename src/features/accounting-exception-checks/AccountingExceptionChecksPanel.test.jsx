import React from 'react';
import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';

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
  findingCount: 31,
  findings: Array.from({ length: 31 }, (_value, index) => ({
    reasonCode: 'accounting_supplier_warehouse_link_not_found',
    subjectKind: 'supplier_invoice',
    subjectId: 91 + index,
    projectId: 17,
    relatedId: 999 + index,
  })),
  truncated: false,
});
const repairPreview = (companyId = 4, overrides = {}) => ({
  version: 'accounting-exception-link-repair-v1',
  companyId,
  state: 'clear',
  repairCount: 0,
  unresolvedCount: 31,
  proofCounts: { reciprocal: 0, delivery: 0, request: 0 },
  planSha256: 'a'.repeat(64),
  blockers: [],
  ...overrides,
});
const readyPreview = (companyId = 4) => repairPreview(companyId, {
  state: 'ready',
  repairCount: 7,
  unresolvedCount: 24,
  proofCounts: { reciprocal: 1, delivery: 5, request: 1 },
  planSha256: 'b'.repeat(64),
});
const jsonResponse = (value, status = 200) => Promise.resolve({
  ok: status >= 200 && status < 300,
  status,
  json: () => Promise.resolve(value),
});

const C = {
  text: '#111827', textSec: '#4b5563', textMuted: '#6b7280',
  border: '#d1d5db', accent: '#f97316', success: '#15803d',
  successLight: '#f0fdf4', warning: '#a16207', warningLight: '#fefce8',
  danger: '#b91c1c', dangerLight: '#fef2f2',
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

const installReadResponses = (report, preview) => {
  global.fetch.mockImplementation(url => (
    url === '/accounting-exception-link-repairs'
      ? jsonResponse(preview)
      : jsonResponse(report)
  ));
};

describe('AccountingExceptionChecksPanel', () => {
  beforeEach(() => {
    global.fetch = jest.fn();
  });

  afterEach(() => {
    jest.restoreAllMocks();
    delete global.fetch;
    delete window.confirm;
  });

  test('is absent and performs no request while any frontend gate is closed', () => {
    const cases = [
      { enabled: false },
      { allowedCompanyIds: new Set([5]) },
      { companyMode: 'all_companies' },
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

  test('loads the review and server repair preview with two exact read-only requests', async () => {
    installReadResponses(reviewReport(), repairPreview());
    renderPanel();

    expect(await screen.findByText('Требуется проверка: 31')).toBeInTheDocument();
    expect(screen.getByText(/Однозначных связей для автоматического исправления пока нет/)).toBeInTheDocument();
    await waitFor(() => expect(global.fetch).toHaveBeenCalledTimes(2));
    const calls = Object.fromEntries(global.fetch.mock.calls.map(([url, options]) => [url, options]));
    expect(Object.keys(calls).sort()).toEqual([
      '/accounting-exception-checks',
      '/accounting-exception-link-repairs',
    ]);
    Object.values(calls).forEach(options => {
      expect(options.credentials).toBe('include');
      expect(options.signal).toEqual(expect.any(AbortSignal));
      expect(options.method).toBeUndefined();
    });
    expect(screen.queryByRole('button', { name: /Исправить безопасные связи/ })).not.toBeInTheDocument();
  });

  test('applies the exact server plan with one confirmation and one POST', async () => {
    window.confirm = jest.fn(() => true);
    const refreshData = jest.fn(() => Promise.resolve());
    let reportReads = 0;
    let previewReads = 0;
    global.fetch.mockImplementation((url, options = {}) => {
      if (url === '/accounting-exception-link-repairs' && options.method === 'POST') {
        return jsonResponse({
          ok: true,
          appliedCount: 7,
          unresolvedCount: 24,
          planSha256: 'b'.repeat(64),
        });
      }
      if (url === '/accounting-exception-link-repairs') {
        previewReads += 1;
        return jsonResponse(previewReads === 1 ? readyPreview() : repairPreview(4, {
          unresolvedCount: 24,
        }));
      }
      reportReads += 1;
      return jsonResponse(reportReads === 1 ? reviewReport() : clearReport());
    });

    renderPanel({ refreshData });
    fireEvent.click(await screen.findByRole('button', {
      name: 'Исправить безопасные связи (7)',
    }));

    expect(window.confirm).toHaveBeenCalledWith(
      'Исправить 7 однозначных связей? Суммы, оплаты и складские остатки не изменятся.',
    );
    await waitFor(() => expect(global.fetch.mock.calls.some(([, options]) => (
      options?.method === 'POST'
    ))).toBe(true));
    const [url, options] = global.fetch.mock.calls.find(([, init]) => init?.method === 'POST');
    expect(url).toBe('/accounting-exception-link-repairs');
    expect(options.credentials).toBe('include');
    expect(options.headers).toEqual({ 'Content-Type': 'application/json' });
    expect(JSON.parse(options.body)).toEqual({
      confirm: 'APPLY_ACCOUNTING_EXCEPTION_LINK_REPAIRS',
      expectedRepairCount: 7,
      expectedPlanSha256: 'b'.repeat(64),
    });
    expect(global.fetch.mock.calls.filter(([calledUrl, init]) => (
      calledUrl.startsWith('/supplier-invoices/') && init?.method === 'PUT'
    ))).toHaveLength(0);
    await waitFor(() => expect(refreshData).toHaveBeenCalledTimes(1));
    expect(await screen.findByText(/Исправлено связей: 7/)).toBeInTheDocument();
  });

  test('turns a stale-plan conflict into one plain refresh instruction', async () => {
    window.confirm = jest.fn(() => true);
    global.fetch.mockImplementation((url, options = {}) => {
      if (options.method === 'POST') return jsonResponse({ detail: 'conflict' }, 409);
      return url === '/accounting-exception-link-repairs'
        ? jsonResponse(readyPreview())
        : jsonResponse(reviewReport());
    });
    renderPanel();

    fireEvent.click(await screen.findByRole('button', { name: /Исправить безопасные связи/ }));

    expect(await screen.findByRole('alert')).toHaveTextContent(
      'Данные изменились. Обновите проверку и повторите действие.',
    );
  });

  test('does not apply an old-company receipt to a newly selected company', async () => {
    window.confirm = jest.fn(() => true);
    const refreshData = jest.fn(() => Promise.resolve());
    let resolveApply;
    global.fetch.mockImplementation((url, options = {}) => {
      if (options.method === 'POST') {
        return new Promise(resolve => { resolveApply = resolve; });
      }
      return url === '/accounting-exception-link-repairs'
        ? jsonResponse(readyPreview())
        : jsonResponse(reviewReport());
    });
    const view = renderPanel({
      allowedCompanyIds: new Set([4, 5]),
      refreshData,
    });

    fireEvent.click(await screen.findByRole('button', {
      name: 'Исправить безопасные связи (7)',
    }));
    view.rerender(
      <AccountingExceptionChecksPanel
        API=""
        C={C}
        allowedCompanyIds={new Set([4, 5])}
        card={{}}
        companyMode="company"
        enabled={false}
        isMobile={false}
        refreshData={refreshData}
        selectedCompanyId={5}
        user={{ role: 'бухгалтер' }}
      />,
    );
    await act(async () => {
      resolveApply(await jsonResponse({
        ok: true,
        appliedCount: 7,
        unresolvedCount: 24,
        planSha256: 'b'.repeat(64),
      }));
    });

    expect(refreshData).not.toHaveBeenCalled();
    expect(screen.queryByText(/Исправлено связей: 7/)).not.toBeInTheDocument();
  });

  test('clears stale company state and aborts both in-flight reads', async () => {
    const signals = [];
    global.fetch.mockImplementation((_url, options) => {
      signals.push(options.signal);
      return new Promise(() => {});
    });
    const view = renderPanel({ allowedCompanyIds: new Set([4, 5]) });
    expect(signals).toHaveLength(2);

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

    await waitFor(() => expect(signals.slice(0, 2).every(signal => signal.aborted)).toBe(true));
    view.unmount();
  });

  test('keeps disputed findings collapsed and groups repeated reasons into one card', async () => {
    installReadResponses(reviewReport(), { ...readyPreview(), privateRows: ['SECRET'] });
    renderPanel();

    expect(await screen.findByText('Требуется проверка: 31')).toBeInTheDocument();
    expect(screen.queryByText(/SECRET/)).not.toBeInTheDocument();
    expect(screen.queryByText('Связанный складской или поставщицкий документ не найден')).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /Исправить безопасные связи/ })).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Показать причины' }));
    expect(screen.getAllByText(
      'Связанный складской или поставщицкий документ не найден',
    )).toHaveLength(1);
    expect(screen.getByText('31 документ')).toBeInTheDocument();
    expect(screen.getByText('Показать документы (31)')).toBeInTheDocument();
    expect(screen.getByText(
      'Откройте накладную и связанный счёт: загрузите отсутствующий документ или уберите ошибочную связь.',
    )).toBeInTheDocument();
  });
});
