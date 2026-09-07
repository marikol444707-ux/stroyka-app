import React from 'react';
import { fireEvent, render, screen } from '@testing-library/react';
import { RecipientDiagnosticsPanel } from './SupplyRequestsListParts';

const renderRecipients = (rows, onOpenSupplierLink = jest.fn()) => render(
  <RecipientDiagnosticsPanel C={{}} badge={() => ({})} btnB={{}} rows={rows} onOpenSupplierLink={onOpenSupplierLink} />,
);

describe('recipient notification diagnostics', () => {
  it('distinguishes account access, SMTP handoff and MAX queueing without a read receipt', () => {
    renderRecipients([{
      id: 1, targetSupplierId: 51, targetSupplierName: 'ООО Трубы',
      visibleToSupplier: true, supplierUserId: 7, approvalComplete: true,
      emailNotificationStatus: 'Отправлено', emailSentAt: '2026-09-06T10:00:00Z',
      maxNotificationStatus: 'В очереди MAX', maxOutboxId: 88, maxQueuedAt: '2026-09-06T10:00:00Z',
    }]);
    expect(screen.getByText('Кабинет связан')).toBeInTheDocument();
    expect(screen.queryByText('видит')).not.toBeInTheDocument();
    expect(screen.getByText('Email: Передано SMTP')).toBeInTheDocument();
    expect(screen.getByText('MAX: В очереди MAX')).toBeInTheDocument();
    expect(screen.getByText('Доступ к запросу: разрешён')).toBeInTheDocument();
    expect(screen.getByText(/Запись очереди MAX #88/)).toBeInTheDocument();
    expect(screen.getByText(/Доставка и прочтение не подтверждены/)).toBeInTheDocument();
  });

  it('renders missing legacy notification evidence as unknown instead of inferring it from visibility or timestamps', () => {
    renderRecipients([{
      id: 1, visibleToSupplier: true, supplierUserId: 7,
      emailSentAt: '2026-09-06T10:00:00Z', maxOutboxId: 88,
    }]);
    expect(screen.getByText('Email: Статус неизвестен')).toBeInTheDocument();
    expect(screen.getByText('MAX: Статус неизвестен')).toBeInTheDocument();
    expect(screen.queryByText(/Передано SMTP/)).not.toBeInTheDocument();
    expect(screen.getByText('Доступ к запросу: не подтверждён')).toBeInTheDocument();
  });

  it('does not grant access based on a legacy visible flag when approvals are incomplete', () => {
    renderRecipients([{
      id: 1, visibleToSupplier: true, supplierUserId: 7, approvalComplete: false,
      approvalBlockReason: 'Нет подтверждения прораба',
    }]);
    expect(screen.getByText('Кабинет связан')).toBeInTheDocument();
    expect(screen.getByText('Доступ к запросу: не подтверждён')).toBeInTheDocument();
    expect(screen.queryByText('Доступ к запросу: разрешён')).not.toBeInTheDocument();
  });

  it('shows the current outbox failure instead of the stale queued notification snapshot', () => {
    renderRecipients([{
      id: 1, visibleToSupplier: true,
      emailNotificationStatus: 'SMTP не настроен',
      maxNotificationStatus: 'В очереди MAX', actualMaxQueueStatus: 'failed',
    }]);
    expect(screen.getByText('Email: SMTP не настроен')).toBeInTheDocument();
    expect(screen.getByText('MAX: Ошибка отправки в MAX')).toBeInTheDocument();
    expect(screen.queryByText('MAX: В очереди MAX')).not.toBeInTheDocument();
  });

  it('does not confuse an approval block with a missing supplier account', () => {
    const openLink = jest.fn();
    renderRecipients([{
      id: 1, targetSupplierId: 51, supplierUserId: 7, visibleToSupplier: false,
      approvalComplete: false, approvalBlockReason: 'Нет подтверждения прораба',
      emailNotificationStatus: 'Ошибка отправки', maxNotificationStatus: 'MAX не привязан',
    }], openLink);
    expect(screen.getByText('Нет подтверждения прораба')).toBeInTheDocument();
    expect(screen.getByText('Кабинет связан')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Связать кабинет' })).not.toBeInTheDocument();
    expect(screen.queryByText(/Нужно связать карточку/)).not.toBeInTheDocument();
  });

  it('keeps the linking action for a genuinely missing account', () => {
    const openLink = jest.fn();
    renderRecipients([{
      id: 1, supplierId: 51, targetSupplierId: 51, visibleToSupplier: false,
      supplierEmail: 'supplier@example.test',
    }], openLink);
    expect(screen.getByText('Кабинет не связан')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Связать кабинет' }));
    expect(openLink).toHaveBeenCalledTimes(1);
  });
});
