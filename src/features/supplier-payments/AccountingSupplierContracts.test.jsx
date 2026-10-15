import React from 'react';
import {fireEvent, render, screen} from '@testing-library/react';
import AccountingSupplierContracts from './AccountingSupplierContracts';

jest.mock('./SupplierContracts', () => props => <div data-testid="contracts">{JSON.stringify(props)}</div>);
jest.mock('../../components/supply/SupplyTechnicalComparisonPanel', () => ({
  ...jest.requireActual('../../components/supply/SupplyTechnicalComparisonPanel'),
  __esModule: true,
  default: props => <div data-testid="technical">{JSON.stringify(props)}</div>,
}));
const props = {API: '/api', user: {id: 9, role: 'директор'}, companyContext: {mode: 'company', selectedCompanyId: 2,
  selectedCompany: {companyId: 2, role: 'директор'}}, suppliers: [{id: 11, companyId: 2, name: 'Наш поставщик'},
  {id: 12, companyId: 3, name: 'Чужой поставщик'}]};

test('accounting offers exact-company contracts without requiring an invoice or quotation', () => {
  render(<AccountingSupplierContracts {...props}/>);
  expect(screen.queryByRole('option', {name: 'Чужой поставщик'})).not.toBeInTheDocument();
  expect(screen.queryByTestId('contracts')).not.toBeInTheDocument();
  fireEvent.change(screen.getByLabelText('Поставщик'), {target: {value: '11'}});
  expect(JSON.parse(screen.getByTestId('contracts').textContent)).toEqual({API: '/api', companyId: 2, supplierId: 11, userId: 9});
});

test('changing company clears the previous supplier selection', () => {
  const {rerender} = render(<AccountingSupplierContracts {...props}/>);
  fireEvent.change(screen.getByLabelText('Поставщик'), {target: {value: '11'}});
  rerender(<AccountingSupplierContracts {...props} companyContext={{mode: 'company', selectedCompanyId: 3, selectedCompany: {role: 'директор'}}}/>);
  expect(screen.queryByTestId('contracts')).not.toBeInTheDocument();
  expect(screen.queryByRole('option', {name: 'Наш поставщик'})).not.toBeInTheDocument();
});

test('does not expose contract management in all-companies mode', () => {
  render(<AccountingSupplierContracts {...props} companyContext={{mode: 'all_companies'}}/>);
  expect(screen.queryByRole('region')).not.toBeInTheDocument();
});

test('moves technical checks to accounting with exact company request, offer and file', () => {
  const previousEnabled = process.env.REACT_APP_SUPPLY_TECHNICAL_COMPARISON_ENABLED;
  const previousCompanies = process.env.REACT_APP_SUPPLY_TECHNICAL_COMPARISON_COMPANY_IDS;
  process.env.REACT_APP_SUPPLY_TECHNICAL_COMPARISON_ENABLED = 'true';
  process.env.REACT_APP_SUPPLY_TECHNICAL_COMPARISON_COMPANY_IDS = '2';
  try {
    render(<AccountingSupplierContracts {...props} projects={[{id: 7, companyId: 2, name: 'Лицей'}]}
      supplyRequests={[{id: 21, companyId: 2, project: 'Лицей'}, {id: 22, companyId: 3, project: 'Чужой объект'}]}
      supplierOffers={[{id: 31, requestId: 21, supplierId: 11, companyId: 2, pdfUrl: '/tenant-files/44/content'},
        {id: 32, requestId: 22, supplierId: 11, companyId: 3, pdfUrl: '/tenant-files/45/content'}]}/>);
    fireEvent.change(screen.getByLabelText('Поставщик'), {target: {value: '11'}});
    expect(screen.getAllByTestId('technical')).toHaveLength(1);
    expect(JSON.parse(screen.getByTestId('technical').textContent)).toMatchObject({projectId: 7, requestId: 21, sourceId: 31, fileId: 44});
  } finally {
    if (previousEnabled === undefined) delete process.env.REACT_APP_SUPPLY_TECHNICAL_COMPARISON_ENABLED;
    else process.env.REACT_APP_SUPPLY_TECHNICAL_COMPARISON_ENABLED = previousEnabled;
    if (previousCompanies === undefined) delete process.env.REACT_APP_SUPPLY_TECHNICAL_COMPARISON_COMPANY_IDS;
    else process.env.REACT_APP_SUPPLY_TECHNICAL_COMPARISON_COMPANY_IDS = previousCompanies;
  }
});
