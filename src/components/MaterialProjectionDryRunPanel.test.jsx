import { fireEvent, render, screen } from '@testing-library/react';
import MaterialProjectionDryRunPanel from './MaterialProjectionDryRunPanel';

const colors = {
  bg: '#f4f6f8', bgWhite: '#ffffff', border: '#d5dbe1', text: '#17212b', textSec: '#52606d',
  textMuted: '#7b8794', accent: '#087f5b', accentLight: '#e6fcf5', accentBorder: '#96f2d7',
  warning: '#9c6500', warningLight: '#fff9db', warningBorder: '#ffe066', info: '#1864ab',
  infoLight: '#e7f5ff', infoBorder: '#a5d8ff', success: '#2b8a3e', successLight: '#ebfbee', successBorder: '#b2f2bb',
};

const materialRow = (name, qty) => ({
  key: name,
  materialKey: name.toLowerCase(),
  name,
  unit: 'шт',
  workPackage: 'Электрика',
  planQty: qty,
  planDetails: [{estimateId: 10, packageName: 'Электрика', sectionName: 'Крепёж', materialName: name, qty, unit: 'шт'}],
});

test('shows a read-only material calculation comparison and expands details', () => {
  render(
    <MaterialProjectionDryRunPanel
      projectName="Лицей"
      rows={[materialRow('Дюбель распорный 8х60', 100), materialRow('Шуруп самонарезающий 3,5х35', 200)]}
      supplyRequests={[{
        id: 21,
        project: 'Лицей',
        status: 'Новая',
        materialName: 'Дюбель распорный 8х60',
        quantity: 300,
        unit: 'шт',
        workPackage: 'Электрика',
        notes: 'Создано из контроля материалов: строка `Докупить`.',
      }]}
      parseSupplyItems={request => [{materialName:request.materialName,quantity:request.quantity,unit:request.unit,workPackage:request.workPackage}]}
      C={colors}
      fmtMeasure={(qty, unit) => `${qty} ${unit}`}
    />,
  );

  expect(screen.getByText('Проверка расчёта материалов')).toBeInTheDocument();
  expect(screen.getByRole('region', {name: 'Проверка расчёта материалов'})).toHaveTextContent('Строк текущего расчёта: 2');
  expect(screen.queryByText('Старый общий расчёт')).not.toBeInTheDocument();

  fireEvent.click(screen.getByRole('button', {name: 'Открыть проверку расчёта'}));

  expect(screen.getByRole('region', {name: 'Проверка расчёта материалов'})).toHaveTextContent('1 изменение');
  expect(screen.getByText('Старый общий расчёт')).toBeInTheDocument();
  expect(screen.getAllByText('Дюбель распорный 8х60').length).toBeGreaterThanOrEqual(2);
  expect(screen.getByText('Шуруп самонарезающий 3,5х35')).toBeInTheDocument();
  expect(screen.getByText('100 шт')).toBeInTheDocument();
  expect(screen.getByText('200 шт')).toBeInTheDocument();
  expect(screen.getByText('Только просмотр')).toBeInTheDocument();
  expect(screen.getByText('Проверка действующих заявок')).toBeInTheDocument();
  expect(screen.getByText('Заявка #21')).toBeInTheDocument();
  expect(screen.getByText('Старая объединённая позиция')).toBeInTheDocument();
  expect(screen.queryByRole('button', {name: /применить|исправить/i})).not.toBeInTheDocument();
});
