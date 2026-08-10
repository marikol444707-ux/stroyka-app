import React from 'react';
import { act, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import MaterialCapabilityProofPanel from './MaterialCapabilityProofPanel';
import { SupplyRequestCard } from './SupplyRequestsListParts';

const FLAG = 'REACT_APP_SUPPLIER_MATERIAL_CAPABILITY_RUNTIME_ENABLED';
const subjectSha256 = 'b'.repeat(64);

const C = {
  bg: '#f4f6f8', bgWhite: '#fff', border: '#d5dbe1', text: '#17212b',
  textSec: '#52606d', textMuted: '#7b8794', accent: '#087f5b',
  accentLight: '#e6fcf5', accentBorder: '#96f2d7', warning: '#9c6500',
  warningLight: '#fff9db', warningBorder: '#ffe066', info: '#1864ab',
  infoLight: '#e7f5ff', infoBorder: '#a5d8ff', success: '#2b8a3e',
  successLight: '#ebfbee', successBorder: '#b2f2bb', danger: '#c92a2a',
  dangerLight: '#fff5f5', dangerBorder: '#ffc9c9',
};

const proof = (proofState, overrides = {}) => ({
  publicProofVersion: 1,
  state: proofState === 'confirmed' ? 'proof_complete' : 'confirmation_required',
  requestId: 21,
  requestItemIndex: 2,
  subjectCount: 1,
  subjects: [{
    companySupplierLinkId: 41,
    supplierId: 51,
    confirmationSubjectSha256: subjectSha256,
    proofState,
    confirmationAssertionId: proofState === 'missing' ? null : 501,
    revocationAssertionId: proofState === 'revoked' ? 601 : null,
  }],
  materialEligibilityProven: proofState === 'confirmed',
  selectionAllowed: false,
  sendAllowed: false,
  blockers: proofState === 'confirmed'
    ? []
    : ['supply_supplier_material_confirmation_required'],
  ...overrides,
});

const receipt = (eventKind, state = eventKind) => ({
  writeVersion: 1,
  eventKind,
  state,
  companySupplierLinkId: 41,
  supplierId: 51,
  confirmationSubjectSha256: subjectSha256,
  assertionId: eventKind === 'confirmed' ? 501 : 601,
  revokesAssertionId: eventKind === 'revoked' ? 501 : null,
  writesAttempted: state.startsWith('already_') ? 0 : 1,
  committed: !state.startsWith('already_'),
});

const response = (body, { ok = true, status = 200 } = {}) => ({
  ok,
  status,
  json: jest.fn().mockResolvedValue(body),
});

const renderPanel = (props = {}) => render(
  <MaterialCapabilityProofPanel
    API="/api"
    C={C}
    requestId={21}
    requestItemIndex={2}
    materialName="Кабель ВВГнг 3×2,5"
    suppliers={[{ id: 51, name: 'ООО «Электроснаб»' }]}
    user={{ id: 7, role: 'директор' }}
    companyContext={{
      mode: 'company',
      selectedCompany: { companyId: 4, role: 'директор' },
    }}
    {...props}
  />,
);

describe('MaterialCapabilityProofPanel', () => {
  const originalFlag = process.env[FLAG];
  const originalFetch = global.fetch;

  beforeEach(() => {
    process.env[FLAG] = 'true';
    global.fetch = jest.fn();
  });

  afterEach(() => {
    if (originalFlag === undefined) delete process.env[FLAG];
    else process.env[FLAG] = originalFlag;
    global.fetch = originalFetch;
    jest.clearAllMocks();
  });

  it('is visible only for the exact enabled flag and exact director role, without automatic loading', () => {
    process.env[FLAG] = 'TRUE';
    const { rerender } = renderPanel();

    expect(screen.queryByRole('region', { name: 'Доказуемость поставщика по материалу' })).not.toBeInTheDocument();

    process.env[FLAG] = 'true';
    rerender(
      <MaterialCapabilityProofPanel
        API="/api"
        C={C}
        requestId={21}
        requestItemIndex={2}
        materialName="Кабель ВВГнг 3×2,5"
        suppliers={[{ id: 51, name: 'ООО «Электроснаб»' }]}
        user={{ id: 8, role: 'директор' }}
        companyContext={{
          mode: 'company',
          selectedCompany: { companyId: 4, role: 'зам_директора' },
        }}
      />,
    );
    expect(screen.queryByRole('region', { name: 'Доказуемость поставщика по материалу' })).not.toBeInTheDocument();

    rerender(
      <MaterialCapabilityProofPanel
        API="/api"
        C={C}
        requestId={21}
        requestItemIndex={2}
        materialName="Кабель ВВГнг 3×2,5"
        suppliers={[{ id: 51, name: 'ООО «Электроснаб»' }]}
        user={{ id: 7, role: 'зам_директора' }}
        companyContext={{
          mode: 'company',
          selectedCompany: { companyId: 4, role: 'директор' },
        }}
      />,
    );

    expect(screen.getByRole('region', { name: 'Доказуемость поставщика по материалу' })).toBeInTheDocument();
    expect(screen.getByText('Кабель ВВГнг 3×2,5')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Проверить доказуемость' })).toBeInTheDocument();
    expect(global.fetch).not.toHaveBeenCalled();
  });

  it('confirms one missing subject only after acknowledgement, blocks double submit and reloads proof', async () => {
    let resolveConfirmation;
    global.fetch
      .mockResolvedValueOnce(response(proof('missing')))
      .mockImplementationOnce(() => new Promise(resolve => { resolveConfirmation = resolve; }))
      .mockResolvedValueOnce(response(proof('confirmed')));

    renderPanel();
    expect(global.fetch).not.toHaveBeenCalled();

    fireEvent.click(screen.getByRole('button', { name: 'Проверить доказуемость' }));
    expect(await screen.findByText('ООО «Электроснаб»')).toBeInTheDocument();
    expect(global.fetch.mock.calls[0][0]).toBe('/api/supply-requests/21/items/2/material-capability-proof');
    expect(screen.queryByRole('textbox')).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /подтвердить всех|выбрать поставщика|отправить запрос|ранжировать/i })).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: 'Подтвердить поставщика' }));
    const cancelledDialog = screen.getByRole('dialog', { name: 'Подтверждение возможности поставщика' });
    expect(within(cancelledDialog).getByText(/не выбирает поставщика и не отправляет запрос КП/i)).toBeInTheDocument();
    fireEvent.click(within(cancelledDialog).getByRole('button', { name: 'Отмена' }));
    expect(screen.queryByRole('dialog', { name: 'Подтверждение возможности поставщика' })).not.toBeInTheDocument();
    expect(global.fetch).toHaveBeenCalledTimes(1);

    fireEvent.click(screen.getByRole('button', { name: 'Подтвердить поставщика' }));
    const dialog = screen.getByRole('dialog', { name: 'Подтверждение возможности поставщика' });
    const submit = within(dialog).getByRole('button', { name: 'Подтвердить доказуемость' });
    expect(submit).toBeDisabled();
    fireEvent.click(within(dialog).getByRole('checkbox', {
      name: /подтверждаю возможность поставки этого точного материала/i,
    }));
    fireEvent.click(submit);
    fireEvent.click(submit);

    expect(global.fetch).toHaveBeenCalledTimes(2);
    expect(submit).toBeDisabled();
    const [confirmationUrl, confirmationOptions] = global.fetch.mock.calls[1];
    expect(confirmationUrl).toBe('/api/supply-requests/21/items/2/material-capability-confirmations');
    expect(confirmationOptions.method).toBe('POST');
    expect(JSON.parse(confirmationOptions.body)).toEqual({
      companySupplierLinkId: 41,
      supplierId: 51,
      confirmationSubjectSha256: subjectSha256,
    });
    expect(confirmationOptions.headers || {}).not.toHaveProperty('Authorization');

    await act(async () => {
      resolveConfirmation(response(receipt('confirmed', 'already_confirmed')));
    });
    await waitFor(() => expect(global.fetch).toHaveBeenCalledTimes(3));
    expect(global.fetch.mock.calls[2][0]).toBe('/api/supply-requests/21/items/2/material-capability-proof');
    expect(await screen.findByText('Подтверждение #501')).toBeInTheDocument();
  });

  it('appends an exact empty-body revocation, refreshes, and renders revoked as terminal', async () => {
    global.fetch
      .mockResolvedValueOnce(response(proof('confirmed')))
      .mockResolvedValueOnce(response(receipt('revoked'), { status: 201 }))
      .mockResolvedValueOnce(response(proof('revoked', {
        state: 'needs_review',
        materialEligibilityProven: false,
      })));

    renderPanel();
    fireEvent.click(screen.getByRole('button', { name: 'Проверить доказуемость' }));
    expect(await screen.findByText('Подтверждение #501')).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: 'Отозвать подтверждение' }));
    const dialog = screen.getByRole('dialog', { name: 'Отзыв подтверждения' });
    expect(within(dialog).getByText(/новое неизменяемое событие.*исходное подтверждение не удаляется/i)).toBeInTheDocument();
    fireEvent.click(within(dialog).getByRole('button', { name: 'Подтвердить отзыв' }));

    await waitFor(() => expect(global.fetch).toHaveBeenCalledTimes(3));
    const [revocationUrl, revocationOptions] = global.fetch.mock.calls[1];
    expect(revocationUrl).toBe('/api/supplier-material-capability-confirmations/501/revocations');
    expect(revocationOptions.method).toBe('POST');
    expect(JSON.parse(revocationOptions.body)).toEqual({});
    expect(Object.keys(JSON.parse(revocationOptions.body))).toHaveLength(0);
    expect(revocationOptions.headers || {}).not.toHaveProperty('Authorization');
    expect(global.fetch.mock.calls[2][0]).toBe('/api/supply-requests/21/items/2/material-capability-proof');

    expect(await screen.findByText('Подтверждение отозвано')).toBeInTheDocument();
    expect(screen.getByText(/подтверждение #501/i)).toBeInTheDocument();
    expect(screen.getByText(/событие отзыва #601/i)).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Подтвердить поставщика' })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Отозвать подтверждение' })).not.toBeInTheDocument();
  });

  it('closes the action and reloads authoritative proof after a stale conflict', async () => {
    global.fetch
      .mockResolvedValueOnce(response(proof('missing')))
      .mockResolvedValueOnce(response(
        { detail: 'supply_supplier_material_writer_subject_stale' },
        { ok: false, status: 409 },
      ))
      .mockResolvedValueOnce(response(proof('missing')));

    renderPanel();
    fireEvent.click(screen.getByRole('button', { name: 'Проверить доказуемость' }));
    expect(await screen.findByText('ООО «Электроснаб»')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Подтвердить поставщика' }));
    const dialog = screen.getByRole('dialog', { name: 'Подтверждение возможности поставщика' });
    fireEvent.click(within(dialog).getByRole('checkbox', {
      name: /подтверждаю возможность поставки этого точного материала/i,
    }));
    fireEvent.click(within(dialog).getByRole('button', { name: 'Подтвердить доказуемость' }));

    await waitFor(() => expect(global.fetch).toHaveBeenCalledTimes(3));
    expect(global.fetch.mock.calls[2][0]).toBe('/api/supply-requests/21/items/2/material-capability-proof');
    expect(screen.queryByRole('dialog', { name: 'Подтверждение возможности поставщика' })).not.toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Подтвердить поставщика' })).toBeInTheDocument();
  });

  it('drops loaded and pending proof when the selected company changes', async () => {
    let resolveOldCompany;
    global.fetch.mockImplementationOnce(
      () => new Promise(resolve => { resolveOldCompany = resolve; }),
    );
    const { rerender } = renderPanel();

    fireEvent.click(screen.getByRole('button', { name: 'Проверить доказуемость' }));
    rerender(
      <MaterialCapabilityProofPanel
        API="/api"
        C={C}
        requestId={21}
        requestItemIndex={2}
        materialName="Кабель ВВГнг 3×2,5"
        suppliers={[{ id: 51, name: 'ООО «Электроснаб»' }]}
        user={{ id: 7, role: 'директор' }}
        companyContext={{
          mode: 'company',
          selectedCompany: { companyId: 5, role: 'директор' },
        }}
      />,
    );

    await act(async () => {
      resolveOldCompany(response(proof('missing')));
    });

    expect(screen.queryByText('ООО «Электроснаб»')).not.toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Проверить доказуемость' })).toBeInTheDocument();
    expect(global.fetch).toHaveBeenCalledTimes(1);
  });

  it('mounts the exact-item panel before the existing supplier offers block', () => {
    const request = {
      id: 21,
      status: 'КП запрошены',
      materialName: 'Кабель ВВГнг 3×2,5',
      quantity: 20,
      unit: 'м',
      project: 'Лицей',
      createdBy: 'Директор',
    };

    render(
      <SupplyRequestCard
        API="/api"
        C={C}
        card={{}}
        inp={{}}
        btnO={{}}
        btnG={{}}
        btnB={{}}
        btnGr={{}}
        btnR={{}}
        badge={() => ({})}
        request={request}
        user={{ id: 7, name: 'Директор', role: 'директор' }}
        companyContext={{
          mode: 'company',
          selectedCompany: { companyId: 4, role: 'директор' },
        }}
        statusColors={() => [C.info, C.infoLight, C.infoBorder]}
        parseSupplyItems={() => [{ materialName: request.materialName, quantity: 20, unit: 'м' }]}
        renderSupplyRequestOrigin={() => null}
        supplyRequestOrigin={() => null}
        supplyExpandedId={null}
        setSupplyExpandedId={jest.fn()}
        canConfirmProrab={false}
        canApprove
        confirmSupplyAsProrab={jest.fn()}
        approveSupplyAsDirector={jest.fn()}
        openRequestKpModal={jest.fn()}
        loadSupplyStockCheck={jest.fn()}
        setSupplyRejectId={jest.fn()}
        supplyRejectId={null}
        supplyRejectReason=""
        setSupplyRejectReason={jest.fn()}
        rejectSupply={jest.fn()}
        cancelSupply={jest.fn()}
        supplyStockCheck={null}
        askSupplyAi={jest.fn()}
        supplyAiLoading={false}
        supplyAiText=""
        supplierOffers={[{ id: 71, requestId: 21, supplierId: 51, status: 'Ожидает ответа' }]}
        compareResultByReq={{}}
        compareLoadingReqId={null}
        runCompareKp={jest.fn()}
        suppliers={[{ id: 51, name: 'ООО «Электроснаб»' }]}
        fileSrc={value => value}
        parseOfferItems={() => []}
        selectSupplierOffer={jest.fn()}
        rejectSupplierOffer={jest.fn()}
        withdrawSupplierOffer={jest.fn()}
        onOpenSupplierLink={jest.fn()}
      />,
    );

    const panel = screen.getByRole('region', { name: 'Доказуемость поставщика по материалу' });
    const offersHeading = screen.getByText(/КП от поставщиков/);
    expect(panel.compareDocumentPosition(offersHeading) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    expect(global.fetch).not.toHaveBeenCalled();
  });
});
