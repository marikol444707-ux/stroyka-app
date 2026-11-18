import React from 'react';
import { fireEvent, render, screen } from '@testing-library/react';
import ProjectEconomyPanel from './ProjectEconomyPanel';
import { createMaterialRuntime } from '../features/material-control/materialRuntime';
import { createProjectDashboardRuntime } from '../features/dashboard/projectDashboardRuntime';

const project = { id: 12, companyId: 2, name: 'Корпус с частичной приёмкой' };
const C = { text: '#111', border: '#ddd', bg: '#fff' };

function economyFor(receivedQuantity, receiptTotal) {
  const item = { name: 'Кабель', unit: 'м', quantity: receivedQuantity,
    total: receiptTotal, price: 100, deliveryId: 32, workPackage: 'Основная' };
  const runtime = createMaterialRuntime({
    projects: [project], companyContext: { mode: 'company', selectedCompanyId: 2 },
    materialAliasesError: '', materialAliases: [],
    activeEstimatesForProject: () => [], estimateWorkNormRequirementRows: () => [],
    supplyDeliveries: [{ id: 32, companyId: 2, project: project.name,
      materialName: 'Кабель', unit: 'м', workPackage: 'Основная', status: 'Проблема',
      shippedQuantity: 10, receivedQuantity, pricePerUnit: 100, totalPrice: 1000 }],
    invoices: receiptTotal === undefined ? [] : [{ id: 52, companyId: 2,
      project: project.name, status: 'Принята', supplyDeliveryId: 32, items: [item] }],
    history: [], materials: [], warehouseMain: [], materialInspections: [],
    warehouseMovements: [], materialTransfers: [], supplyHistory: [],
    workJournal: [], supplyRequests: [], parseSupplyItems: () => [],
  });
  const dashboard = createProjectDashboardRuntime({
    materialControlSummaryForProject: runtime.materialControlSummaryForProject,
    activeEstimatesForProject: () => [], projectPlanDone: () => ({ plan: 5000, done: 0 }),
    estimatePackage: () => 'Основная', workJournal: [],
  });
  return dashboard.projectEconomy(project);
}

test.each([[4, undefined, 400], [4, 480, 480], [0, undefined, 0], [4, 0, 0]])(
  'accepted quantity %s and saved amount %s reach economy and the management report as %s',
  (received, saved, expected) => {
    const showPreview = jest.fn();
    render(<ProjectEconomyPanel C={C} project={project}
      economy={economyFor(received, saved)} showPreview={showPreview} />);
    expect(screen.getByText('Материалы факт').parentElement).toHaveTextContent(`${expected} ₽`);
    expect(screen.getByText('Фактические затраты').parentElement).toHaveTextContent(`${expected} ₽`);
    fireEvent.click(screen.getByRole('button', { name: 'Отчет' }));
    const report = new DOMParser().parseFromString(showPreview.mock.calls[0][0], 'text/html');
    const row = [...report.querySelectorAll('tr')].find(tr => tr.cells[0].textContent === 'Материалы факт');
    expect(row.cells[1].textContent).toBe(`${expected} ₽`);
  },
);
