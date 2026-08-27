import React from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';

import AssignmentDailyDraftPreviewPanel, {
  parseAssignmentDailyPreviewCompanyIds,
} from './AssignmentDailyDraftPreviewPanel';
import {
  buildAssignmentDailyDraftPrintContent,
  validateAssignmentDailyDraftPreview,
} from './assignmentDailyDraftPreview';


const C = {
  accent: '#f97316',
  accentLight: '#fff7ed',
  border: '#d1d5db',
  bg: '#f8fafc',
  bgWhite: '#ffffff',
  danger: '#dc2626',
  dangerLight: '#fef2f2',
  success: '#15803d',
  successLight: '#f0fdf4',
  text: '#111827',
  textMuted: '#94a3b8',
  textSec: '#64748b',
  warning: '#b45309',
  warningLight: '#fffbeb',
};

const projects = [
  { id: 10, companyId: 1, name: 'Школа', status: 'В работе' },
  { id: 20, companyId: 2, name: 'Чужая школа', status: 'В работе' },
];

const estimates = [
  {
    id: 80,
    companyId: 1,
    projectId: 10,
    projectName: 'Школа',
    name: 'Смета СКС',
    status: 'Активная',
    smetaType: 'Заказчик',
    workPackage: 'Слаботочка',
    isTemplate: false,
  },
  {
    id: 81,
    companyId: 2,
    projectId: 20,
    projectName: 'Чужая школа',
    name: 'Чужая смета',
    status: 'Активная',
    smetaType: 'Заказчик',
    workPackage: 'Основная',
    isTemplate: false,
  },
  {
    id: 82,
    companyId: 1,
    projectId: 10,
    projectName: 'Школа',
    name: 'Черновик',
    status: 'Черновик',
    smetaType: 'Заказчик',
    workPackage: 'Основная',
    isTemplate: false,
  },
];

const preview = {
  version: 1,
  state: 'ready',
  companyId: 1,
  projectId: 10,
  date: '2026-08-21',
  assignmentDraft: {
    state: 'ready',
    items: [{
      sourceEstimateId: 80,
      sourceEstimateVersionId: 4,
      sectionIndex: 0,
      itemIndex: 0,
      itemKey: 'work-1',
      sectionName: 'Раздел <script>alert(1)</script>',
      itemName: 'Монтаж кабеля',
      unit: 'м',
      estimateQuantity: '10',
      assignedQuantity: '4',
      availableQuantity: '6',
      workPackage: 'Слаботочка',
      assignee: null,
    }],
    summary: { sourceWorkRows: 1, availableRows: 1, fullyAssignedRows: 0 },
    review: [],
  },
  dailyWorkDraft: {
    state: 'ready',
    items: [{
      sourceId: 7,
      description: 'Монтаж кабеля',
      unit: 'м',
      quantity: '2.5',
      responsibleId: 31,
      responsibleName: 'Иван Петров',
      workPackage: 'Слаботочка',
      status: 'Подтверждено',
    }],
    summary: { confirmedRows: 1, workPackages: 1, responsiblePeople: 1 },
    review: [],
  },
  review: [],
  previewOnly: true,
  applyAllowed: false,
  writesAttempted: 0,
  readOnlyTransaction: true,
  rolledBack: true,
};

const jsonResponse = (value, status = 200) => Promise.resolve({
  ok: status >= 200 && status < 300,
  status,
  json: () => Promise.resolve(value),
});

const renderPanel = (overrides = {}) => {
  const showPreview = jest.fn();
  render(
    <AssignmentDailyDraftPreviewPanel
      API=""
      C={C}
      btnG={{}}
      btnO={{}}
      card={{}}
      enabled
      allowedCompanyIds={new Set([1])}
      estimates={estimates}
      inp={{}}
      isMobile={false}
      projects={projects}
      selectedCompanyId={1}
      showPreview={showPreview}
      user={{ role: 'директор', companyId: 1 }}
      {...overrides}
    />,
  );
  return { showPreview };
};


describe('AssignmentDailyDraftPreviewPanel', () => {
  beforeEach(() => {
    global.fetch = jest.fn();
  });

  afterEach(() => {
    jest.restoreAllMocks();
    delete global.fetch;
  });

  test('is absent when disabled or the user is not director/deputy', () => {
    const { rerender } = render(
      <AssignmentDailyDraftPreviewPanel enabled={false} user={{ role: 'директор' }} />,
    );
    expect(screen.queryByText('Черновик назначений и работ')).not.toBeInTheDocument();

    rerender(
      <AssignmentDailyDraftPreviewPanel enabled user={{ role: 'прораб' }} />,
    );
    expect(screen.queryByText('Черновик назначений и работ')).not.toBeInTheDocument();
    expect(global.fetch).not.toHaveBeenCalled();
  });

  test('is absent outside the exact frontend company allowlist', () => {
    renderPanel({ allowedCompanyIds: new Set([2]) });

    expect(screen.queryByText('Черновик назначений и работ')).not.toBeInTheDocument();
    expect(global.fetch).not.toHaveBeenCalled();
  });

  test('uses the selected-company role instead of the platform account role', async () => {
    global.fetch.mockReturnValue(jsonResponse([], 200));
    renderPanel({
      selectedCompanyRole: 'директор',
      user: { role: 'platform_admin', companyId: 1 },
    });

    expect(screen.getByText('Черновик назначений и работ')).toBeInTheDocument();
    await waitFor(() => expect(screen.getByText('Нет версий')).toBeInTheDocument());
  });

  test('does not fall back to an eligible platform role for an ineligible company role', () => {
    renderPanel({
      selectedCompanyRole: 'прораб',
      user: { role: 'директор', companyId: 1 },
    });

    expect(screen.queryByText('Черновик назначений и работ')).not.toBeInTheDocument();
    expect(global.fetch).not.toHaveBeenCalled();
  });

  test('explains how to continue when the selected estimate has no saved versions', async () => {
    global.fetch.mockReturnValue(jsonResponse([], 200));
    renderPanel();

    await screen.findByText('Нет версий');
    const previewButton = screen.getByRole('button', { name: 'Сформировать предпросмотр' });

    expect(previewButton).toBeEnabled();
    fireEvent.click(previewButton);
    expect(screen.getByRole('alert')).toHaveTextContent(
      'У этой сметы нет сохранённой версии. Откройте смету, сохраните версию и повторите.',
    );
    expect(global.fetch).toHaveBeenCalledTimes(1);
  });

  test('loads exact versions and posts only selected preview coordinates', async () => {
    global.fetch
      .mockImplementationOnce(() => jsonResponse([
        { id: 4, versionLabel: '2.0' },
        { id: 3, versionLabel: '1.0' },
      ]))
      .mockImplementationOnce(() => jsonResponse(preview));

    renderPanel();

    expect(await screen.findByRole('option', { name: 'Смета СКС · Слаботочка' })).toBeInTheDocument();
    expect(screen.queryByRole('option', { name: 'Чужая школа' })).not.toBeInTheDocument();
    await waitFor(() => expect(global.fetch).toHaveBeenCalledTimes(1));
    expect(global.fetch.mock.calls[0][0]).toBe('/estimates/80/versions');
    expect(global.fetch.mock.calls[0][1]).toEqual({
      credentials: 'include',
      signal: expect.any(AbortSignal),
    });

    fireEvent.change(screen.getByLabelText('Дата подтверждённых работ'), {
      target: { value: '2026-08-21' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Сформировать предпросмотр' }));

    await screen.findByText('Доступно к назначению');
    expect(global.fetch).toHaveBeenCalledTimes(2);
    const [url, options] = global.fetch.mock.calls[1];
    expect(url).toBe('/assignment-daily-draft-previews');
    expect(options.method).toBe('POST');
    expect(options.credentials).toBe('include');
    expect(options.headers).toEqual({ 'Content-Type': 'application/json' });
    expect(JSON.parse(options.body)).toEqual({
      projectId: 10,
      date: '2026-08-21',
      estimateId: 80,
      estimateVersionId: 4,
      workPackage: 'Слаботочка',
    });
    expect(options.headers.Authorization).toBeUndefined();
    expect(screen.queryByRole('button', { name: /применить/i })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /сохранить/i })).not.toBeInTheDocument();
  });

  test('opens an escaped printable review and never exposes an apply action', async () => {
    global.fetch
      .mockImplementationOnce(() => jsonResponse([{ id: 4, versionLabel: '2.0' }]))
      .mockImplementationOnce(() => jsonResponse(preview));
    const { showPreview } = renderPanel();

    await screen.findByRole('option', { name: '2.0' });
    fireEvent.change(screen.getByLabelText('Дата подтверждённых работ'), {
      target: { value: '2026-08-21' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Сформировать предпросмотр' }));
    expect(await screen.findAllByText('Монтаж кабеля')).toHaveLength(2);
    fireEvent.click(screen.getByRole('button', { name: 'Печатная версия' }));

    expect(showPreview).toHaveBeenCalledTimes(1);
    const [html, title] = showPreview.mock.calls[0];
    expect(title).toBe('Черновик назначений и работ — Школа');
    expect(html).toContain('&lt;script&gt;alert(1)&lt;/script&gt;');
    expect(html).not.toContain('<script>alert(1)</script>');
    expect(html).not.toMatch(/Применить|Сохранить|Назначить исполнителя/i);
  });

  test('fails closed on malformed server output', async () => {
    global.fetch
      .mockImplementationOnce(() => jsonResponse([{ id: 4, versionLabel: '2.0' }]))
      .mockImplementationOnce(() => jsonResponse({ ...preview, applyAllowed: true }));
    renderPanel();

    await screen.findByRole('option', { name: '2.0' });
    fireEvent.change(screen.getByLabelText('Дата подтверждённых работ'), {
      target: { value: '2026-08-21' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Сформировать предпросмотр' }));

    expect(await screen.findByRole('alert')).toHaveTextContent('Предпросмотр временно недоступен');
    expect(screen.queryByText('Доступно к назначению')).not.toBeInTheDocument();
  });

  test('never renders a stale preview after the selected date changes', async () => {
    let resolvePreview;
    const pendingPreview = new Promise(resolve => { resolvePreview = resolve; });
    global.fetch
      .mockImplementationOnce(() => jsonResponse([{ id: 4, versionLabel: '2.0' }]))
      .mockImplementationOnce(() => pendingPreview);
    renderPanel();

    await screen.findByRole('option', { name: '2.0' });
    fireEvent.change(screen.getByLabelText('Дата подтверждённых работ'), {
      target: { value: '2026-08-21' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Сформировать предпросмотр' }));
    await waitFor(() => expect(global.fetch).toHaveBeenCalledTimes(2));
    fireEvent.change(screen.getByLabelText('Дата подтверждённых работ'), {
      target: { value: '2026-08-22' },
    });
    resolvePreview(await jsonResponse(preview));

    await screen.findByRole('button', { name: 'Сформировать предпросмотр' });
    expect(screen.getByLabelText('Дата подтверждённых работ')).toHaveValue('2026-08-22');
    expect(screen.queryByText('Доступно к назначению')).not.toBeInTheDocument();
    expect(screen.queryByRole('alert')).not.toBeInTheDocument();
  });
});


describe('assignment daily preview contract', () => {
  test('parses only a strict duplicate-free frontend company allowlist', () => {
    expect(Array.from(parseAssignmentDailyPreviewCompanyIds('1,17'))).toEqual([1, 17]);
    for (const value of (
      [undefined, null, '', '0', '01', '1,1', '1,', ' 1', '1.0', '9007199254740992']
    )) {
      expect(parseAssignmentDailyPreviewCompanyIds(value)).toBeNull();
    }
  });

  test('accepts only the exact preview-only response', () => {
    const validated = validateAssignmentDailyDraftPreview(preview, {
      companyId: 1,
      projectId: 10,
      date: '2026-08-21',
      estimateId: 80,
      estimateVersionId: 4,
      workPackage: 'Слаботочка',
    });

    expect(validated).toEqual(preview);
    expect(() => validateAssignmentDailyDraftPreview(
      { ...preview, writesAttempted: 1 },
      { companyId: 1, projectId: 10, date: '2026-08-21', estimateId: 80, estimateVersionId: 4, workPackage: 'Слаботочка' },
    )).toThrow('assignment_daily_preview_invalid');
  });

  test('print builder escapes every source string and contains no money/photos', () => {
    const html = buildAssignmentDailyDraftPrintContent(preview, {
      projectName: 'Школа <img src=x onerror=alert(1)>',
      estimateName: 'Смета',
      versionLabel: '2.0',
    });

    expect(html).toContain('&lt;img src=x onerror=alert(1)&gt;');
    expect(html).not.toContain('<img src=x onerror=alert(1)>');
    expect(html).not.toMatch(/₽|цена|стоимость|фото/i);
  });
});
