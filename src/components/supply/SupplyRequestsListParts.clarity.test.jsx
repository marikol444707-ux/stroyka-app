import React from 'react';
import { fireEvent, render, screen, within } from '@testing-library/react';
import SupplyRequestsList from '../SupplyRequestsList';
import { SupplyRequestCard } from './SupplyRequestsListParts';
import { parseSupplyItems, supplyRequestOrigin } from '../../utils/supplyUtils';
import { createSupplyPlanningUi } from '../../features/supply/supplyPlanningUi';

const workName = 'Установка сплит-систем мощностью 3,5 кВт';
const compositeName = 'Материалы по позиции: ' + workName;
const control = {
  status: 'within_estimate_need', plannedQty: 12, stockQty: 2, requestedQty: 3,
  remainingQty: 7, remainingAfterRequest: 5, plannedSum: 12000,
  controlMessage: 'Расчёт по активной смете',
};
const item = (materialName, extra = {}) => ({
  materialName, quantity: 2, unit: 'компл', estimateControl: { ...control }, ...extra,
});
const request = (items, extra = {}) => ({
  id: 101, status: 'Новая', project: 'Лицей', createdBy: 'Прораб',
  date: '2026-09-07', itemsJson: items, ...extra,
});
const cardProps = (extra = {}) => ({
  C: {}, badge: () => ({}), user: { id: 7, name: 'Директор' },
  statusColors: () => [], parseSupplyItems, supplyRequestOrigin,
  renderSupplyRequestOrigin: () => null, supplyExpandedId: null,
  supplyRejectId: null, supplierOffers: [], compareResultByReq: {},
  supplyCollapsedProjects: {}, setSupplyCollapsedProjects: jest.fn(),
  ...extra,
});

describe('supply request card clarity', () => {
  it('shows a single item name once while retaining all estimate figures and warnings', () => {
    render(<SupplyRequestCard {...cardProps()} request={request([item('Кабель')])} />);

    expect(screen.getAllByText('Кабель')).toHaveLength(1);
    expect(screen.getByText('Заявка #101')).toBeVisible();
    for (const text of ['План:', 'На объекте:', 'В заявках:', 'Остаток:', 'После заявки:', 'По смете:']) {
      expect(screen.getByText(text, { exact: false })).toBeInTheDocument();
    }
    for (const value of ['12 компл', '2 компл', '3 компл', '7 компл', '5 компл']) {
      expect(screen.getByText(value)).toBeInTheDocument();
    }
    expect(screen.getByText('12 000 ₽')).toBeInTheDocument();
    expect(screen.getByText(control.controlMessage)).toBeInTheDocument();
    expect(screen.getByText('В потребности')).toBeInTheDocument();
  });

  it('does not repeat the composite source work already included in its material title', () => {
    render(<SupplyRequestCard {...cardProps()} request={request([
      item(compositeName, { estimateControl: { ...control, status: 'composite_work_material', workName, sectionName: 'Вентиляция' } }),
    ])} />);

    expect(screen.getAllByText(compositeName)).toHaveLength(1);
    expect(screen.getByRole('article', { name: 'Заявка #101' }).textContent.split(workName)).toHaveLength(2);
    expect(screen.getByText('Комплектация работы')).toBeInTheDocument();
    expect(screen.getByText('Вентиляция')).toBeInTheDocument();
  });

  it('retains a genuinely different source work instead of hiding a substring match', () => {
    render(<SupplyRequestCard {...cardProps()} request={request([
      item('Материалы по позиции: ' + workName + ' и пусконаладка', {
        estimateControl: { ...control, status: 'composite_work_material', workName },
      }),
    ])} />);

    expect(screen.getByText(workName)).toBeInTheDocument();
    expect(screen.getByText(/Работа:/)).toBeInTheDocument();
    expect(screen.getByRole('article', { name: 'Заявка #101' }).textContent.split(workName)).toHaveLength(3);
  });

  it('preserves the full server explanation even when prose references the same work', () => {
    const message = 'Материал не найден отдельной ресурсной строкой сметы, но привязан к укрупненной работе «'
      + workName + '» в разделе «Вентиляция». Учитывать как фактическую комплектацию работы, не как отдельную сметную потребность.';
    render(<SupplyRequestCard {...cardProps()} request={request([
      item(compositeName, { estimateControl: {
        ...control, status: 'composite_work_material', workName, controlMessage: message,
      } }),
    ])} />);

    expect(screen.getAllByText(compositeName)).toHaveLength(1);
    expect(screen.getByText(message)).toBeInTheDocument();
    expect(screen.getByRole('article', { name: 'Заявка #101' }).textContent.split(workName)).toHaveLength(3);
  });

  it('keeps every item and links control rows to their original list positions', () => {
    const source = request([
      item('Крепёж', { estimateControl: undefined }),
      item('Труба', { quantity: 4 }),
      item('Кабель', { quantity: 9, estimateControl: { ...control, status: 'over_estimate_need' } }),
    ]);
    const before = JSON.stringify(source);
    render(<SupplyRequestCard {...cardProps()} request={source} />);

    expect(screen.getAllByRole('listitem')).toHaveLength(3);
    for (const name of ['Крепёж', 'Труба', 'Кабель']) {
      expect(screen.getAllByText(name)).toHaveLength(1);
    }
    expect(screen.getByText('Позиция 2')).toBeInTheDocument();
    expect(screen.getByText('Позиция 3')).toBeInTheDocument();
    expect(screen.queryByText('Позиция 1')).not.toBeInTheDocument();
    expect(screen.getByText('Сверх сметы')).toBeInTheDocument();
    expect(JSON.stringify(source)).toBe(before);
  });

  it('keeps legacy name fields visible after removing the repeated control title', () => {
    render(<SupplyRequestCard {...cardProps()} request={request([
      { name: 'Старое наименование', quantity: 2, unit: 'шт', estimate_control: { ...control } },
    ])} />);

    expect(screen.getAllByText('Старое наименование')).toHaveLength(1);
    expect(screen.getByText('Старое наименование')).toHaveStyle({ fontSize: '14px' });
  });

  it('retains separate same-name requests with visible IDs and their own action targets', () => {
    const confirm = jest.fn();
    const requests = [request([item('Кабель')]), request([item('Кабель')], { id: 102 })];
    render(<SupplyRequestsList {...cardProps({ canConfirmProrab: true, confirmSupplyAsProrab: confirm })} list={requests} />);

    expect(screen.getAllByText('Кабель')).toHaveLength(2);
    const first = screen.getByRole('article', { name: 'Заявка #101' });
    const second = screen.getByRole('article', { name: 'Заявка #102' });
    expect(within(first).getByText('Заявка #101')).toBeVisible();
    expect(within(second).getByText('Заявка #102')).toBeVisible();
    fireEvent.click(within(first).getByRole('button', { name: 'Подтвердить' }));
    fireEvent.click(within(second).getByRole('button', { name: 'Подтвердить' }));
    expect(confirm.mock.calls).toEqual([[101], [102]]);
  });

  it.each([compositeName, 'Комплект крепления для кондиционера'])(
    'shows the source work once with real material-control notes for %s', (materialName) => {
      const source = request([
        item(materialName, { estimateControl: { ...control, status: 'composite_work_material', workName } }),
      ], {
        notes: [
          'MATERIAL_CONTROL_REQUEST:fixture', 'Объект: Лицей', 'Материал: ' + materialName,
          'Сметных строк: 1', 'Разделы: Вентиляция', 'Работы: ' + workName,
          'План по смете: 12 компл', 'Поставлено/перемещено: 2 компл', 'В заявках и пути: 3 компл',
        ].join('\n'),
      });
      const before = JSON.stringify(source);
      const { renderSupplyRequestOrigin } = createSupplyPlanningUi({ C: {}, supplyRequestOrigin });
      render(<SupplyRequestCard {...cardProps({ renderSupplyRequestOrigin })} request={source} />);

      expect(screen.getByRole('article', { name: 'Заявка #101' }).textContent.split(workName)).toHaveLength(2);
      const origin = screen.getByRole('group', { name: 'Из контроля материалов' });
      expect(origin).toHaveTextContent('Сметных строк: 1');
      expect(origin).toHaveTextContent('Разделы: Вентиляция');
      expect(origin).toHaveTextContent('План: 12 компл');
      expect(origin).toHaveTextContent('Поставлено: 2 компл');
      expect(origin).toHaveTextContent('Заявки/путь: 3 компл');
      expect(JSON.stringify(source)).toBe(before);
    },
  );

  it('keeps different or combined origin work names and does not change other renderer callers', () => {
    const { renderSupplyRequestOrigin } = createSupplyPlanningUi({ C: {}, supplyRequestOrigin });
    const source = request([item(compositeName, {
      estimateControl: { ...control, status: 'composite_work_material', workName },
    })], { notes: 'MATERIAL_CONTROL_REQUEST:fixture\nРаботы: ' + workName + '; Прокладка трассы' });
    const { rerender } = render(<SupplyRequestCard {...cardProps({ renderSupplyRequestOrigin })} request={source} />);
    expect(screen.getByText(workName + '; Прокладка трассы')).toBeInTheDocument();

    rerender(renderSupplyRequestOrigin({ ...source, notes: 'MATERIAL_CONTROL_REQUEST:fixture\nРаботы: ' + workName }));
    expect(screen.getByText(workName)).toBeInTheDocument();
  });
});
