import React from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';

import SupplyTechnicalComparisonPanel, {
  parseSupplyTechnicalComparisonCompanyIds,
  protectedTenantFileId,
  uniqueScopedProjectId,
} from './SupplyTechnicalComparisonPanel';
import { SupplyRequestCard } from './SupplyRequestsListParts';

const C = {
  bg: '#f4f6f8', bgWhite: '#fff', border: '#d5dbe1', text: '#17212b',
  textSec: '#52606d', textMuted: '#7b8794', accent: '#087f5b',
  info: '#1864ab', infoLight: '#e7f5ff', infoBorder: '#a5d8ff',
  success: '#2b8a3e', successLight: '#ebfbee', successBorder: '#b2f2bb',
  warning: '#9c6500', warningLight: '#fff9db', warningBorder: '#ffe066',
  danger: '#c92a2a', dangerLight: '#fff5f5', dangerBorder: '#ffc9c9',
};

const line = (name, category = '') => ({
  name,
  unit: 'м',
  quantity: '100',
  workPackage: 'ВК',
  category,
});

const signature = name => ({
  normalizedName: name,
  family: 'ppr_pipe',
  dimensions: ['20x3.4'],
  diametersMm: ['20'],
  threadSizes: [],
  threadGenders: [],
  anglesDeg: [],
  pnClasses: ['20'],
  sdrClasses: [],
  reinforcement: [],
  directions: [],
  designFlags: [],
  weightsG: [],
  signatureSha256: 'a'.repeat(64),
});

const report = (overrides = {}) => ({
  ok: true,
  dryRun: true,
  contractVersion: 1,
  companyId: 4,
  projectId: 7,
  requestId: 31,
  sourceKind: 'supplier_offer',
  sourceId: 81,
  file: {
    id: 44,
    contentUrl: '/tenant-files/44/content',
    context: 'supplier-offer',
    originalName: 'offer.pdf',
    contentType: 'application/pdf',
  },
  requestedLineCount: 1,
  offeredLineCount: 1,
  comparisonCount: 1,
  comparisons: [{
    lineNumber: 1,
    required: line('Труба PP-R PN20 20x3,4 мм', 'Трубы PP-R'),
    offered: line('Труба Valfex PP-R PN20 20x3,4 мм'),
    result: {
      contractVersion: 1,
      status: 'ok',
      decision: 'comparable',
      confidence: 0.95,
      confidenceBasisPoints: 9500,
      reasonCodes: ['COMPATIBLE_ENGINEERING_SIGNATURE'],
      reasons: ['Compatible engineering signature'],
      requiredSignature: signature('труба ppr pn20 20x3.4 мм'),
      offeredSignature: signature('труба valfex ppr pn20 20x3.4 мм'),
      comparisonSha256: 'b'.repeat(64),
      writesAttempted: 0,
      modelCalls: 0,
      automaticApprovalAllowed: false,
    },
  }],
  resultSha256: 'c'.repeat(64),
  automaticApprovalAllowed: false,
  writesAttempted: 0,
  modelCalls: 0,
  readOnlyTransaction: true,
  rolledBack: true,
  ...overrides,
});

const response = (body, { ok = true, status = 200 } = {}) => ({
  ok,
  status,
  json: jest.fn().mockResolvedValue(body),
});

const renderPanel = (props = {}) => render(
  <SupplyTechnicalComparisonPanel
    API="/api"
    C={C}
    enabled
    allowedCompanyIds={new Set([4])}
    companyContext={{
      mode: 'company',
      selectedCompany: { companyId: 4, role: 'снабженец' },
    }}
    projectId={7}
    requestId={31}
    sourceKind="supplier_offer"
    sourceId={81}
    fileId={44}
    {...props}
  />,
);

describe('SupplyTechnicalComparisonPanel', () => {
  const originalFetch = global.fetch;

  beforeEach(() => {
    global.fetch = jest.fn();
  });

  afterEach(() => {
    global.fetch = originalFetch;
    jest.clearAllMocks();
  });

  it('parses only an exact company allowlist and exact protected file URL', () => {
    expect(parseSupplyTechnicalComparisonCompanyIds('4,7')).toEqual(new Set([4, 7]));
    expect(parseSupplyTechnicalComparisonCompanyIds('4,4')).toBeNull();
    expect(parseSupplyTechnicalComparisonCompanyIds('4, 7')).toBeNull();
    expect(parseSupplyTechnicalComparisonCompanyIds('')).toBeNull();

    expect(protectedTenantFileId('/tenant-files/44/content')).toBe(44);
    expect(protectedTenantFileId('/tenant-files/044/content')).toBeNull();
    expect(protectedTenantFileId('/tenant-files/44/content/')).toBeNull();
    expect(protectedTenantFileId('https://evil.test/tenant-files/44/content')).toBeNull();
  });

  it('resolves a project only by one exact name and company owner', () => {
    const projects = [
      { id: 7, companyId: 4, name: 'Лицей' },
      { id: 8, companyId: 5, name: 'Лицей' },
      { id: 9, companyId: 4, name: 'Школа' },
    ];
    expect(uniqueScopedProjectId(projects, 'Лицей', 4)).toBe(7);
    expect(uniqueScopedProjectId([...projects, { id: 10, companyId: 4, name: 'Лицей' }], 'Лицей', 4)).toBeNull();
    expect(uniqueScopedProjectId(projects, 'лицей', 4)).toBeNull();
    expect(uniqueScopedProjectId(projects, 'Лицей', 6)).toBeNull();
  });

  it('is default-closed for the flag, allowlist, role, mode and selectors', () => {
    const { rerender } = renderPanel({ enabled: false });
    expect(screen.queryByRole('button', { name: 'Проверить характеристики' })).not.toBeInTheDocument();

    rerender(<SupplyTechnicalComparisonPanel
      API="/api" C={C} enabled allowedCompanyIds={new Set([4])}
      companyContext={{ mode: 'all_companies', selectedCompany: { companyId: 4, role: 'снабженец' } }}
      projectId={7} requestId={31} sourceKind="supplier_offer" sourceId={81} fileId={44}
    />);
    expect(screen.queryByRole('button', { name: 'Проверить характеристики' })).not.toBeInTheDocument();

    rerender(<SupplyTechnicalComparisonPanel
      API="/api" C={C} enabled allowedCompanyIds={new Set([4])}
      companyContext={{ mode: 'company', selectedCompany: { companyId: 4, role: 'прораб' } }}
      projectId={7} requestId={31} sourceKind="supplier_offer" sourceId={81} fileId={44}
    />);
    expect(screen.queryByRole('button', { name: 'Проверить характеристики' })).not.toBeInTheDocument();

    rerender(<SupplyTechnicalComparisonPanel
      API="/api" C={C} enabled allowedCompanyIds={new Set([4])}
      companyContext={{ mode: 'company', selectedCompany: { companyId: 4, role: 'директор' } }}
      projectId={null} requestId={31} sourceKind="supplier_offer" sourceId={81} fileId={44}
    />);
    expect(screen.queryByRole('button', { name: 'Проверить характеристики' })).not.toBeInTheDocument();
    expect(global.fetch).not.toHaveBeenCalled();
  });

  it('loads only after one explicit click and renders the narrow read-only result', async () => {
    global.fetch.mockResolvedValueOnce(response(report()));
    renderPanel();

    expect(global.fetch).not.toHaveBeenCalled();
    expect(screen.getByText('Только проверка. Поставщик не выбирается.')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Проверить характеристики' }));

    await waitFor(() => expect(global.fetch).toHaveBeenCalledTimes(1));
    expect(global.fetch).toHaveBeenCalledWith(
      '/api/supply-requests/31/technical-comparisons/supplier_offer/81?projectId=7&fileId=44',
      { credentials: 'include', cache: 'no-store', signal: expect.any(AbortSignal) },
    );
    expect(await screen.findByText('Сопоставимо')).toBeInTheDocument();
    expect(screen.getByText('Труба PP-R PN20 20x3,4 мм')).toBeInTheDocument();
    expect(screen.getByText('Труба Valfex PP-R PN20 20x3,4 мм')).toBeInTheDocument();
    expect(screen.getByText('95%')).toBeInTheDocument();
    expect(screen.getByText('Технические характеристики совместимы.')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /выбрать|утвердить|оплатить|согласовать/i })).not.toBeInTheDocument();
  });

  it('fails closed on a response with a mismatched selector or write permission', async () => {
    global.fetch.mockResolvedValueOnce(response(report({
      sourceId: 82,
      automaticApprovalAllowed: true,
    })));
    renderPanel();
    fireEvent.click(screen.getByRole('button', { name: 'Проверить характеристики' }));

    expect(await screen.findByText('Сервер не подтвердил безопасный результат. Повторите проверку.')).toBeInTheDocument();
    expect(screen.queryByText('Сопоставимо')).not.toBeInTheDocument();
  });

  it('drops an in-flight response after company scope changes', async () => {
    let resolveRequest;
    global.fetch.mockImplementationOnce(() => new Promise(resolve => { resolveRequest = resolve; }));
    const { rerender } = renderPanel();
    fireEvent.click(screen.getByRole('button', { name: 'Проверить характеристики' }));

    rerender(<SupplyTechnicalComparisonPanel
      API="/api" C={C} enabled allowedCompanyIds={new Set([5])}
      companyContext={{ mode: 'company', selectedCompany: { companyId: 5, role: 'снабженец' } }}
      projectId={8} requestId={31} sourceKind="supplier_offer" sourceId={81} fileId={44}
    />);
    resolveRequest(response(report()));

    await waitFor(() => expect(global.fetch).toHaveBeenCalledTimes(1));
    expect(screen.queryByText('Сопоставимо')).not.toBeInTheDocument();
  });

  it('embeds one read-only check in the existing supplier offer card with exact derived selectors', async () => {
    global.fetch.mockResolvedValueOnce(response(report()));
    const request = {
      id: 31,
      status: 'КП запрошены',
      materialName: 'Труба PP-R PN20 20x3,4 мм',
      quantity: 100,
      unit: 'м',
      project: 'Лицей',
      createdBy: 'Директор',
    };
    render(
      <SupplyRequestCard
        API="/api" C={C} card={{}} inp={{}} btnO={{}} btnG={{}} btnB={{}}
        btnGr={{}} btnR={{}} badge={() => ({})} request={request}
        user={{ id: 7, name: 'Директор', role: 'директор' }}
        companyContext={{ mode: 'company', selectedCompany: { companyId: 4, role: 'директор' } }}
        projects={[{ id: 7, companyId: 4, name: 'Лицей' }]}
        technicalComparisonEnabled
        technicalComparisonAllowedCompanyIds={new Set([4])}
        statusColors={() => [C.info, C.infoLight, C.infoBorder]}
        parseSupplyItems={() => [{ materialName: request.materialName, quantity: 100, unit: 'м' }]}
        renderSupplyRequestOrigin={() => null} supplyRequestOrigin={() => null}
        supplyExpandedId={null} setSupplyExpandedId={jest.fn()}
        canConfirmProrab={false} canApprove confirmSupplyAsProrab={jest.fn()}
        approveSupplyAsDirector={jest.fn()} openRequestKpModal={jest.fn()}
        loadSupplyStockCheck={jest.fn()} setSupplyRejectId={jest.fn()}
        supplyRejectId={null} supplyRejectReason="" setSupplyRejectReason={jest.fn()}
        rejectSupply={jest.fn()} cancelSupply={jest.fn()} supplyStockCheck={null}
        askSupplyAi={jest.fn()} supplyAiLoading={false} supplyAiText=""
        supplierOffers={[{
          id: 81, requestId: 31, supplierId: 51, status: 'Получено',
          pdfUrl: '/tenant-files/44/content', pricePerUnit: 100,
        }]}
        compareResultByReq={{}} compareLoadingReqId={null} runCompareKp={jest.fn()}
        suppliers={[{ id: 51, name: 'ООО «Трубы»' }]}
        fileSrc={value => value} parseOfferItems={() => []}
        selectSupplierOffer={jest.fn()} rejectSupplierOffer={jest.fn()}
        withdrawSupplierOffer={jest.fn()} onOpenSupplierLink={jest.fn()}
      />,
    );

    expect(screen.getByRole('link', { name: /PDF/ })).toHaveAttribute('href', '/tenant-files/44/content');
    fireEvent.click(screen.getByRole('button', { name: 'Проверить характеристики' }));
    await waitFor(() => expect(global.fetch).toHaveBeenCalledWith(
      '/api/supply-requests/31/technical-comparisons/supplier_offer/81?projectId=7&fileId=44',
      expect.objectContaining({ credentials: 'include', cache: 'no-store' }),
    ));
    expect(await screen.findByText('Сопоставимо')).toBeInTheDocument();
  });
});
