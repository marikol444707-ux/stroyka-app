import React from 'react';
import {render, screen} from '@testing-library/react';
import MaterialReconciliationPanel from './MaterialReconciliationPanel';
import WarehouseMaterialControlOverview from './WarehouseMaterialControlOverview';

const summary = () => ({unavailable: true, error: 'Нет соединения'});

test('object control shows unavailable instead of empty movements and print', () => {
  render(<MaterialReconciliationPanel project={{id: 7}} materialControlSummaryForProject={summary}/>);
  expect(screen.getByRole('alert').textContent).toContain('Нет соединения');
  expect(screen.queryByRole('button')).toBeNull();
  expect(screen.queryByText('Нет сметных материалов и движений по объекту.')).toBeNull();
});

test('warehouse hides green zero totals and exports when any owner snapshot is unavailable', () => {
  render(<WarehouseMaterialControlOverview projects={[{id: 7}]} visibleActiveProjects={rows => rows} materialControlSummaryForProject={summary}/>);
  expect(screen.getByRole('alert').textContent).toContain('Нет соединения');
  expect(screen.queryByRole('button')).toBeNull();
  expect(screen.queryByText('Докупить: 0')).toBeNull();
});
