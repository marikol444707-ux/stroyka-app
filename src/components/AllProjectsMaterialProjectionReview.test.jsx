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
  expect(screen.getByText('Список заявок на проверку')).toBeInTheDocument();
  expect(screen.getByText('Заявка #31')).toBeInTheDocument();
  expect(screen.getByText('Старая объединённая позиция')).toBeInTheDocument();
  expect(screen.getByText('300 шт · Электрика')).toBeInTheDocument();
  expect(screen.getByText(/Сверить с: Дюбель распорный 8х60; Шуруп самонарезающий 3,5х35/)).toBeInTheDocument();
  expect(screen.getByText('Школа')).toBeInTheDocument();
  expect(screen.getByText('Лицей')).toBeInTheDocument();

  fireEvent.click(screen.getByRole('button', {name: 'Показать только объекты, требующие проверки'}));

  expect(screen.getByText('Школа')).toBeInTheDocument();
  expect(screen.queryByText('Лицей')).not.toBeInTheDocument();
  expect(screen.queryByRole('button', {name: /применить|исправить|удалить/i})).not.toBeInTheDocument();
});

test('renders a large request review list in bounded batches and resets after data changes', () => {
  const requests = Array.from({length: 51}, (_, index) => ({
    id: 100 + index,
    project: 'Большой объект',
    status: 'Новая',
    materialName: `Старый материал ${index + 1}`,
    quantity: index + 1,
    unit: 'шт',
    workPackage: 'Общестрой',
    notes: 'Создано из контроля материалов',
  }));

  const uniqueCandidates = [{id: 3, name: 'Большой объект'}];
  const renderReview = (currentRequests, projectIdentityCandidates = uniqueCandidates) => (
    <AllProjectsMaterialProjectionReview
      projects={[{id: 3, name: 'Большой объект'}]}
      projectIdentityCandidates={projectIdentityCandidates}
      materialReconciliationRows={() => [materialRow('Текущий материал', 1, {estimateId: 12, packageName: 'Общестрой', materialName: 'Текущий материал', qty: 1, unit: 'шт'})]}
      supplyRequests={currentRequests}
      parseSupplyItems={request => [{materialName:request.materialName,quantity:request.quantity,unit:request.unit,workPackage:request.workPackage}]}
      C={colors}
    />
  );
  const {rerender} = render(renderReview(requests));

  fireEvent.click(screen.getByRole('button', {name: 'Открыть проверку всех объектов'}));

  expect(screen.getAllByTestId('request-review-row')[0]).toHaveStyle('grid-template-columns: repeat(auto-fit,minmax(180px,1fr))');
  expect(screen.getByText('Заявка #149')).toBeInTheDocument();
  expect(screen.queryByText('Заявка #150')).not.toBeInTheDocument();
  fireEvent.click(screen.getByRole('button', {name: 'Показать ещё заявки на проверку'}));
  expect(screen.getByText('Заявка #150')).toBeInTheDocument();

  rerender(renderReview([...requests]));
  expect(screen.getByText('Заявка #150')).toBeInTheDocument();

  const requestsWithReadyItem = [...requests, {
    id: 999,
    project: 'Большой объект',
    status: 'Новая',
    materialName: 'Текущий материал',
    quantity: 1,
    unit: 'шт',
    workPackage: 'Электрика',
    notes: 'Создано из контроля материалов',
  }];
  rerender(renderReview(requestsWithReadyItem));
  expect(screen.getByText('Сметных заявок: 52')).toBeInTheDocument();
  expect(screen.queryByText('Заявка #150')).not.toBeInTheDocument();
  fireEvent.click(screen.getByRole('button', {name: 'Показать ещё заявки на проверку'}));
  expect(screen.getByText('Заявка #150')).toBeInTheDocument();

  rerender(renderReview(requests));
  expect(screen.queryByText('Заявка #150')).not.toBeInTheDocument();

  const ambiguousCandidates = [...uniqueCandidates, {id: 4, name: 'Большой объект'}];
  rerender(renderReview(requests, ambiguousCandidates));
  expect(screen.queryByText('Заявка #150')).not.toBeInTheDocument();
  expect(screen.getAllByText('Возможные объекты: #3; #4').length).toBeGreaterThan(0);
  fireEvent.click(screen.getByRole('button', {name: 'Показать ещё заявки на проверку'}));
  expect(screen.getByText('Заявка #150')).toBeInTheDocument();

  rerender(renderReview(requests, uniqueCandidates));
  expect(screen.queryByText('Заявка #150')).not.toBeInTheDocument();

  const refreshedRequests = Array.from({length: 51}, (_, index) => ({
    ...requests[index],
    id: 200 + index,
  }));
  rerender(renderReview(refreshedRequests));

  expect(screen.getByText('Заявка #249')).toBeInTheDocument();
  expect(screen.queryByText('Заявка #250')).not.toBeInTheDocument();
});

test('shows malformed and ambiguous project references without guessing an owner', () => {
  render(
    <AllProjectsMaterialProjectionReview
      projects={[{id: 7, name: 'Повтор'}, {id: 8, name: 'Повтор'}]}
      materialReconciliationRows={() => [materialRow('Текущий материал', 1, {estimateId: 12, packageName: 'Общестрой', materialName: 'Текущий материал', qty: 1, unit: 'шт'})]}
      supplyRequests={[{project:'Повтор',status:'Новая',materialName:'Безымянная заявка',quantity:1,unit:'шт',notes:'Создано из контроля материалов'}]}
      parseSupplyItems={request => [{materialName:request.materialName,quantity:request.quantity,unit:request.unit}]}
      C={colors}
    />,
  );

  fireEvent.click(screen.getByRole('button', {name: 'Открыть проверку всех объектов'}));

  expect(screen.getByText('Заявка без ID')).toBeInTheDocument();
  expect(screen.getByText('У заявки нет ID')).toBeInTheDocument();
  expect(screen.queryByText(/#undefined/)).not.toBeInTheDocument();
});

test('shows an explicit unavailable state instead of a false zero for roles without request access', () => {
  render(
    <AllProjectsMaterialProjectionReview
      projects={[{id: 7, name: 'Лицей'}]}
      materialReconciliationRows={() => [materialRow('Материал', 1, {estimateId: 12})]}
      supplyRequests={[]}
      canReviewSupplyRequests={false}
      C={colors}
    />,
  );

  fireEvent.click(screen.getByRole('button', {name: 'Открыть проверку всех объектов'}));

  expect(screen.getByText('Проверка заявок недоступна для этой роли.')).toBeInTheDocument();
  expect(screen.getByText('Только просмотр')).toBeInTheDocument();
  expect(screen.getByText('Объектов проверить: 1')).toBeInTheDocument();
  expect(screen.getByText('Изменений расчёта: 1')).toBeInTheDocument();
});

test('keeps pagination open across close and reopen when review content is unchanged', () => {
  const requests = Array.from({length: 51}, (_, index) => ({
    id: 300 + index,
    project: 'Большой объект',
    status: 'Новая',
    materialName: `Старый материал ${index + 1}`,
    quantity: index + 1,
    unit: 'шт',
    workPackage: 'Общестрой',
    notes: 'Создано из контроля материалов',
  }));
  render(
    <AllProjectsMaterialProjectionReview
      projects={[{id: 3, name: 'Большой объект'}]}
      materialReconciliationRows={() => [materialRow('Текущий материал', 1, {estimateId: 12, packageName: 'Общестрой', materialName: 'Текущий материал', qty: 1, unit: 'шт'})]}
      supplyRequests={requests}
      C={colors}
    />,
  );

  fireEvent.click(screen.getByRole('button', {name: 'Открыть проверку всех объектов'}));
  fireEvent.click(screen.getByRole('button', {name: 'Показать ещё заявки на проверку'}));
  expect(screen.getByText('Заявка #350')).toBeInTheDocument();

  fireEvent.click(screen.getByRole('button', {name: 'Закрыть проверку всех объектов'}));
  fireEvent.click(screen.getByRole('button', {name: 'Открыть проверку всех объектов'}));

  expect(screen.getByText('Заявка #350')).toBeInTheDocument();
});
