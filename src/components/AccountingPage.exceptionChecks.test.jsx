import React from 'react';
import { render, screen } from '@testing-library/react';

import AccountingPage from './AccountingPage';

const mockPanelProps = jest.fn();

jest.mock('./AccountingTabsNav', () => () => <nav>Бухгалтерские вкладки</nav>);
jest.mock('./AccountingSummaryPanel', () => () => <div>Финансовая сводка</div>);
jest.mock('../features/accounting-exception-checks/AccountingExceptionChecksPanel', () => props => {
  mockPanelProps(props);
  return <div>Панель безопасной проверки</div>;
});

describe('AccountingPage accounting exception checks integration', () => {
  beforeEach(() => mockPanelProps.mockClear());

  test('places the read-only panel above the company summary with exact context', () => {
    const companyContext = { mode: 'company', selectedCompanyId: 4 };
    const user = { id: 7, role: 'бухгалтер' };
    const C = { text: '#111827' };
    const card = { borderRadius: '12px' };
    const projects = [{ id: 19, name: 'ЖК Северный' }];
    const invoices = [{ id: 21, project: 'ЖК Северный' }];
    const supplierInvoices = [{ id: 22, projectName: 'ЖК Северный' }];
    const refreshData = jest.fn();

    render(
      <AccountingPage
        API="/api"
        C={C}
        accountingTab="summary"
        card={card}
        companyContext={companyContext}
        invoices={invoices}
        isMobile
        projects={projects}
        refreshData={refreshData}
        supplierInvoices={supplierInvoices}
        user={user}
      />,
    );

    expect(screen.getByText('Панель безопасной проверки')).toBeInTheDocument();
    expect(screen.getByText('Финансовая сводка')).toBeInTheDocument();
    expect(mockPanelProps).toHaveBeenCalledTimes(1);
    expect(mockPanelProps.mock.calls[0][0]).toEqual(expect.objectContaining({
      API: '/api',
      C,
      card,
      companyMode: 'company',
      invoices,
      isMobile: true,
      projects,
      refreshData,
      selectedCompanyId: 4,
      supplierInvoices,
      user,
    }));
  });
});
