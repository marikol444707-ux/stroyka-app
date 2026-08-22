import React from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';

import HumanApprovedActionReviewPanel from './HumanApprovedActionReviewPanel';

const C = {
  accent: '#f97316', accentLight: '#fff7ed', border: '#d1d5db',
  danger: '#b91c1c', dangerLight: '#fef2f2', success: '#15803d',
  successLight: '#f0fdf4', text: '#111827', textMuted: '#6b7280',
  textSec: '#4b5563', warning: '#a16207', warningLight: '#fefce8',
};
const projects = [{ id: 17, companyId: 4, name: 'Школа № 8', status: 'В работе' }];
const selected = {
  subjectKind: 'warehouseInvoice',
  subjectId: 91,
  anomalyCode: 'warehouse_invoice_project_mismatch',
};
const preview = {
  warehouseAnomalyRuntimeVersion: 1, ok: true, dryRun: true, writesAttempted: 0,
  previewOnly: true, stockMovementAllowed: false, inventoryAdjustmentAllowed: false,
  applyAllowed: false, state: 'preview_ready',
  candidate: { ...selected, recommendationCode: 'review_warehouse_invoice_lineage' },
  content: {
    title: 'Проверить объект складской накладной',
    finding: 'Складская накладная относится к другому объекту.',
    nextSafeAction: 'Сопоставьте объект накладной с заявкой и поставкой.',
  },
  blockers: [], readOnlyTransaction: true, rolledBack: true,
};
const proposal = {
  humanActionReceiptVersion: 1, state: 'proposed',
  actionKind: 'warehouse_anomaly_review_acknowledged', proposalId: 301,
  proposalSha256: 'a'.repeat(64), companyId: 4, projectId: 17, sourceJobId: 27,
  subjectKind: 'warehouseInvoice', subjectId: 91, actorUserId: 8,
  actorMembershipId: 12, expiresAt: '2026-08-23T12:15:00.000000Z',
  writesAttempted: 2, committed: true, idempotent: false,
};
const decision = {
  humanActionReceiptVersion: 1, state: 'applied',
  actionKind: 'warehouse_anomaly_review_acknowledged', proposalId: 301,
  proposalSha256: 'a'.repeat(64), companyId: 4, projectId: 17, sourceJobId: 27,
  subjectKind: 'warehouseInvoice', subjectId: 91, actorUserId: 8,
  actorMembershipId: 12, eventId: 501, auditEventId: 701,
  writesAttempted: 3, committed: true, idempotent: false,
};
const jsonResponse = (value, status = 200) => Promise.resolve({
  ok: status >= 200 && status < 300,
  status,
  json: () => Promise.resolve(value),
});

const renderPanel = (overrides = {}) => render(
  <HumanApprovedActionReviewPanel
    API=""
    C={C}
    allowedCompanyIds={new Set([4])}
    card={{}}
    companyMode="company"
    enabled
    isMobile={false}
    projects={projects}
    selectedCompanyId={4}
    user={{ role: 'директор' }}
    {...overrides}
  />,
);

const fillSource = () => {
  fireEvent.change(screen.getByLabelText('Объект проверки'), { target: { value: '17' } });
  fireEvent.change(screen.getByLabelText('Задание проверки'), { target: { value: '27' } });
  fireEvent.change(screen.getByLabelText('Тип аномалии'), {
    target: { value: 'warehouse_invoice_project_mismatch' },
  });
  fireEvent.change(screen.getByLabelText('Номер записи'), { target: { value: '91' } });
};

describe('HumanApprovedActionReviewPanel', () => {
  beforeEach(() => { global.fetch = jest.fn(); });
  afterEach(() => { jest.restoreAllMocks(); delete global.fetch; });

  test('is default-off and hidden outside one exact director/company context', () => {
    const cases = [
      { enabled: false },
      { allowedCompanyIds: new Set([5]) },
      { companyMode: 'all_companies' },
      { selectedCompanyId: null },
      { user: { role: 'бухгалтер' } },
    ];
    cases.forEach(props => {
      const view = renderPanel(props);
      expect(screen.queryByText('Ручная фиксация проверки аномалии')).not.toBeInTheDocument();
      view.unmount();
    });
    expect(global.fetch).not.toHaveBeenCalled();
  });

  test('shows the exact read-only preview and fixed no-correction consequence before proposal', async () => {
    global.fetch.mockImplementation(() => jsonResponse(preview));
    renderPanel();
    fillSource();
    fireEvent.click(screen.getByRole('button', { name: 'Проверить текущие данные' }));

    expect(await screen.findByText('Проверить объект складской накладной')).toBeInTheDocument();
    expect(screen.getByText('Складская накладная относится к другому объекту.')).toBeInTheDocument();
    expect(screen.getByText((_text, element) => (
      element.tagName === 'P'
      && element.textContent === 'Затронутая запись: Накладная относится к другому объекту · №91'
    ))).toBeInTheDocument();
    expect(screen.getByText(/не изменит накладную, складские остатки, движения или суммы/i)).toBeInTheDocument();
    expect(screen.getByText('Компания №4 · Объект Школа № 8 · Задание №27')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /исправить|скорректировать|применить к складу/i }))
      .not.toBeInTheDocument();
    const [url, options] = global.fetch.mock.calls[0];
    expect(url).toBe('/warehouse-anomaly-previews');
    expect(options).toMatchObject({ method: 'POST', credentials: 'include' });
    expect(JSON.parse(options.body)).toEqual({ projectId: 17, jobId: 27, selected });
  });

  test('creates one proposal despite a double click and requires a separate explicit decision', async () => {
    let resolveProposal;
    global.fetch
      .mockImplementationOnce(() => jsonResponse(preview))
      .mockImplementationOnce(() => new Promise(resolve => { resolveProposal = resolve; }))
      .mockImplementationOnce(() => jsonResponse(decision));
    renderPanel({ clock: () => Date.parse('2026-08-23T12:00:00Z') });
    fillSource();
    fireEvent.click(screen.getByRole('button', { name: 'Проверить текущие данные' }));
    await screen.findByText('Проверить объект складской накладной');

    const proposeButton = screen.getByRole('button', { name: 'Подготовить запись проверки' });
    fireEvent.click(proposeButton);
    fireEvent.click(proposeButton);
    expect(global.fetch).toHaveBeenCalledTimes(2);
    resolveProposal(await jsonResponse(proposal));

    const approve = await screen.findByRole('button', {
      name: 'Записать факт проверки — данные не исправляются',
    });
    expect(approve).toBeEnabled();
    expect(screen.getByText('Действует до 23.08.2026, 15:15:00')).toBeInTheDocument();
    fireEvent.click(approve);
    fireEvent.click(approve);

    expect(await screen.findByText('Факт проверки записан')).toBeInTheDocument();
    expect(global.fetch).toHaveBeenCalledTimes(3);
    expect(global.fetch.mock.calls[2][0]).toBe('/human-approved-actions/decisions');
    expect(JSON.parse(global.fetch.mock.calls[2][1].body)).toEqual({
      proposalId: 301, proposalSha256: 'a'.repeat(64), decision: 'approve',
    });
    expect(screen.getByText('Квитанция №501 · аудит №701')).toBeInTheDocument();
    expect(screen.getByText('Предложение №301 · warehouse_anomaly_review_acknowledged')).toBeInTheDocument();
    expect(screen.getByText(/Складские и финансовые записи не изменялись/)).toBeInTheDocument();
  });

  test('clears a prepared proposal when company or source drifts and disables an expired decision', async () => {
    global.fetch
      .mockImplementationOnce(() => jsonResponse(preview))
      .mockImplementationOnce(() => jsonResponse(proposal));
    const view = renderPanel({ clock: () => Date.parse('2026-08-23T12:00:00Z') });
    fillSource();
    fireEvent.click(screen.getByRole('button', { name: 'Проверить текущие данные' }));
    await screen.findByText('Проверить объект складской накладной');
    fireEvent.click(screen.getByRole('button', { name: 'Подготовить запись проверки' }));
    expect(await screen.findByText('Действует до 23.08.2026, 15:15:00')).toBeInTheDocument();

    fireEvent.change(screen.getByLabelText('Номер записи'), { target: { value: '92' } });
    expect(screen.queryByText('Действует до 23.08.2026, 15:15:00')).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /Записать факт проверки/ })).not.toBeInTheDocument();

    view.rerender(
      <HumanApprovedActionReviewPanel
        API="" C={C} allowedCompanyIds={new Set([4])} card={{}}
        companyMode="company" enabled isMobile={false} projects={projects}
        selectedCompanyId={5} user={{ role: 'директор' }}
      />,
    );
    expect(screen.queryByText('Ручная фиксация проверки аномалии')).not.toBeInTheDocument();

    global.fetch.mockReset();
    global.fetch
      .mockImplementationOnce(() => jsonResponse(preview))
      .mockImplementationOnce(() => jsonResponse({
        ...proposal, expiresAt: '2026-08-23T11:59:59.000000Z',
      }));
    view.unmount();
    renderPanel({ clock: () => Date.parse('2026-08-23T12:00:00Z') });
    fillSource();
    fireEvent.click(screen.getByRole('button', { name: 'Проверить текущие данные' }));
    await screen.findByText('Проверить объект складской накладной');
    fireEvent.click(screen.getByRole('button', { name: 'Подготовить запись проверки' }));
    expect(await screen.findByRole('button', { name: /Записать факт проверки/ })).toBeDisabled();
    expect(screen.getByRole('alert')).toHaveTextContent('Срок предложения истёк');
  });

  test('invalidates a prepared proposal when the selected project leaves the loaded context', async () => {
    global.fetch
      .mockImplementationOnce(() => jsonResponse(preview))
      .mockImplementationOnce(() => jsonResponse(proposal));
    const view = renderPanel({ clock: () => Date.parse('2026-08-23T12:00:00Z') });
    fillSource();
    fireEvent.click(screen.getByRole('button', { name: 'Проверить текущие данные' }));
    await screen.findByText('Проверить объект складской накладной');
    fireEvent.click(screen.getByRole('button', { name: 'Подготовить запись проверки' }));
    expect(await screen.findByText('Предложение №301')).toBeInTheDocument();

    view.rerender(
      <HumanApprovedActionReviewPanel
        API="" C={C} allowedCompanyIds={new Set([4])} card={{}}
        clock={() => Date.parse('2026-08-23T12:00:00Z')}
        companyMode="company" enabled isMobile={false} projects={[]}
        selectedCompanyId={4} user={{ role: 'директор' }}
      />,
    );

    expect(screen.queryByText('Предложение №301')).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /Записать факт проверки/ })).not.toBeInTheDocument();
  });

  test('fails closed on malformed API data without rendering private response fields', async () => {
    global.fetch.mockImplementation(() => jsonResponse({ ...preview, secret: 'PRIVATE_ROW' }));
    renderPanel();
    fillSource();
    fireEvent.click(screen.getByRole('button', { name: 'Проверить текущие данные' }));

    expect(await screen.findByRole('alert')).toHaveTextContent('Текущая проверка недоступна');
    expect(screen.queryByText('PRIVATE_ROW')).not.toBeInTheDocument();
    await waitFor(() => expect(screen.getByRole('button', { name: 'Проверить текущие данные' })).toBeEnabled());
  });
});
