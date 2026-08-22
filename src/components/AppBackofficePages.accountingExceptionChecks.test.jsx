import React from 'react';
import { render } from '@testing-library/react';

import AppBackofficePages from './AppBackofficePages';

const mockAccountingPageProps = jest.fn();

jest.mock('../app/lazyComponents', () => ({
  AccountingPage: props => {
    mockAccountingPageProps(props);
    return <div>Бухгалтерия</div>;
  },
  PersonnelPage: () => null,
}));

describe('AppBackofficePages accounting exception checks context', () => {
  beforeEach(() => mockAccountingPageProps.mockClear());

  test('forwards API and selected company context to AccountingPage', () => {
    const companyContext = { mode: 'company', selectedCompanyId: 4 };
    render(
      <AppBackofficePages
        activePage="accounting"
        actions={{ isLeadership: () => true }}
        constants={{}}
        state={{ companyContext }}
        ui={{ API: '/api' }}
      />,
    );

    expect(mockAccountingPageProps).toHaveBeenCalledTimes(1);
    expect(mockAccountingPageProps.mock.calls[0][0]).toEqual(expect.objectContaining({
      API: '/api',
      companyContext,
    }));
  });
});
