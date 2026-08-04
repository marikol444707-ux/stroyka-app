import React from 'react';
import { render, screen } from '@testing-library/react';
import AccountingTabsNav from './AccountingTabsNav';

describe('AccountingTabsNav', () => {
  it('renders accounting actions inside the responsive navigation grid', () => {
    const { container } = render(
      <AccountingTabsNav
        accountingTab="summary"
        setAccountingTab={jest.fn()}
        setShowForm={jest.fn()}
        isLeadership
        loadAuditLog={jest.fn()}
        btnO={{}}
        btnG={{}}
      />,
    );

    expect(container.firstChild).toHaveClass('accounting-tabs-nav');
    expect(screen.getByRole('button', { name: /Сводка/ })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Документы поставщиков/ })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Аудит/ })).toBeInTheDocument();
  });
});
