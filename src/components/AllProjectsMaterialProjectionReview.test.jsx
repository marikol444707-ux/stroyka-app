import { fireEvent, render, screen } from '@testing-library/react';
import AllProjectsMaterialProjectionReview from './AllProjectsMaterialProjectionReview';

const colors = {
  bgWhite: '#ffffff', border: '#d5dbe1', text: '#17212b', textSec: '#52606d',
  warning: '#9c6500', warningLight: '#fff9db', warningBorder: '#ffe066', info: '#1864ab',
  success: '#2b8a3e', successLight: '#ebfbee', successBorder: '#b2f2bb',
};

const materialRow = (name, qty, detail) => ({
  key: name,
  materialKey: name.toLowerCase(),
  name,
  unit: 'шт',
  workPackage: 'Электрика',
  planQty: qty,
  planDetails: [detail],
});

test('opens an all-project read-only review and filters projects needing attention', () => {
  const sourceA = {estimateId: 10, packageName: 'Электрика', sectionName: 'Крепёж', materialName: 'Дюбель распорный 8х60', qty: 100, unit: 'шт'};
  const sourceB = {estimateId: 10, packageName: 'Электрика', sectionName: 'Крепёж', materialName: 'Шуруп самонарезающий 3,5х35', qty: 200, unit: 'шт'};
  const projects = [{id: 1, name: 'Лицей'}, {id: 2, name: 'Школа'}];
  const rowsByProject = {
    Лицей: [materialRow('Кабель ВВГ 3х1,5', 80, {estimateId: 11, packageName: 'Электрика', materialName: 'Кабель ВВГ 3х1,5', qty: 80, unit: 'шт'})],
    Школа: [materialRow('Дюбель распорный 8х60', 100, sourceA), materialRow('Шуруп самонарезающий 3,5х35', 200, sourceB)],
  };

  render(
    <AllProjectsMaterialProjectionReview
      projects={projects}
      materialReconciliationRows={name => rowsByProject[name] || []}
      supplyRequests={[{id: 31, project: 'Школа', status: 'Новая', materialName: 'Дюбель распорный 8х60', quantity: 300, unit: 'шт', workPackage: 'Электрика', notes: 'Создано из контроля материалов'}]}
      parseSupplyItems={request => [{materialName:request.materialName,quantity:request.quantity,unit:request.unit,workPackage:request.workPackage}]}
      C={colors}
    />,
  );

  expect(screen.getByText('Проверка всех объектов')).toBeInTheDocument();
  expect(screen.queryByText('Объектов проверить: 1')).not.toBeInTheDocument();

  fireEvent.click(screen.getByRole('button', {name: 'Открыть проверку всех объектов'}));

  expect(screen.getByText('Только просмотр')).toBeInTheDocument();
  expect(screen.getByText('Объектов проверить: 1')).toBeInTheDocument();
  expect(screen.getByText('Школа')).toBeInTheDocument();
  expect(screen.getByText('Лицей')).toBeInTheDocument();

  fireEvent.click(screen.getByRole('button', {name: 'Показать только объекты, требующие проверки'}));

  expect(screen.getByText('Школа')).toBeInTheDocument();
  expect(screen.queryByText('Лицей')).not.toBeInTheDocument();
  expect(screen.queryByRole('button', {name: /применить|исправить|удалить/i})).not.toBeInTheDocument();
});
