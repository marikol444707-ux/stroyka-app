import { act, fireEvent, render, screen } from '@testing-library/react';

import SupplyRequestForm from './SupplyRequestForm';
import SuppliersPage from './SuppliersPage';
import { C, card, inp, btnO, btnG, btnR } from '../constants/uiTheme';
import { createRequestForm, createSupplyRequestForm } from '../features/supply/supplyInitialForms';

const item = {materialName: 'Цемент', quantity: '10', unit: 'шт', workPackage: 'Основная'};
const common = {
  C, card, inp, btnO, btnG, btnR,
  projects: [{id: 1, name: 'Объект'}],
  getProjectWorkPackageOptions: () => ['Основная'],
};

function deferred() {
  let resolve;
  let reject;
  const promise = new Promise((resolvePromise, rejectPromise) => {
    resolve = resolvePromise;
    reject = rejectPromise;
  });
  return {promise, resolve, reject};
}

const forms = [
  {
    name: 'SupplyRequestForm',
    build(action, close = jest.fn()) {
      return <SupplyRequestForm {...common}
        role="директор" isLeadership
        supplyTemplates={[]} priceHints={{}} UNITS={['шт']}
        newSupplyReq={createSupplyRequestForm({project: 'Объект', items: [item], notes: 'Сохранить черновик'})}
        setNewSupplyReq={jest.fn()} fetchPriceHint={jest.fn()}
        renderSupplyPlanningHint={() => null}
        createSupplyReq={action} saveSupplyTemplate={jest.fn()}
        setShowSupplyForm={close}
      />;
    },
  },
  {
    name: 'SuppliersPage',
    build(action, close = jest.fn()) {
      return <SuppliersPage {...common}
        suppliersTab="requests" setSuppliersTab={jest.fn()}
        showForm setShowForm={close} suppliers={[]} supplierCategories={[]} units={['шт']}
        newRequest={createRequestForm({project: 'Объект', items: [item], notes: 'Сохранить черновик'})}
        setNewRequest={jest.fn()} saveRequest={action} supplyRequests={[]}
      />;
    },
  },
];

describe.each(forms)('$name request submission', ({build}) => {
  test('allows one submission and keeps fields/cancel locked across rerenders until completion', async () => {
    const pending = deferred();
    const action = jest.fn(() => pending.promise);
    const close = jest.fn();
    const view = render(build(action, close));
    const submit = screen.getByRole('button', {name: /Создать/});

    fireEvent.click(submit);
    fireEvent.click(submit);

    expect(action).toHaveBeenCalledTimes(1);
    expect(screen.getByRole('button', {name: 'Создание…'})).toBeDisabled();
    expect(submit).toHaveAttribute('aria-busy', 'true');
    expect(screen.getByPlaceholderText('Материал *')).toBeDisabled();
    expect(screen.getByRole('button', {name: 'Отмена'})).toBeDisabled();
    fireEvent.click(screen.getByRole('button', {name: 'Отмена'}));
    expect(close).not.toHaveBeenCalled();

    const replacementAction = jest.fn();
    view.rerender(build(replacementAction, close));
    fireEvent.click(screen.getByRole('button', {name: 'Создание…'}));
    expect(replacementAction).not.toHaveBeenCalled();
    expect(screen.getByPlaceholderText('Материал *')).toHaveValue('Цемент');

    await act(async () => pending.resolve());

    expect(screen.getByRole('button', {name: 'Создать заявку'})).toBeEnabled();
    expect(screen.getByPlaceholderText('Материал *')).toBeEnabled();
    expect(screen.getByRole('button', {name: 'Отмена'})).toBeEnabled();
  });

  test('handles rejection, retains the draft and allows retry', async () => {
    const pending = deferred();
    const action = jest.fn().mockReturnValueOnce(pending.promise).mockResolvedValueOnce({id: 2});
    render(build(action));
    fireEvent.click(screen.getByRole('button', {name: /Создать/}));

    await act(async () => pending.reject(new Error('Сеть недоступна')));

    expect(screen.getByRole('alert')).toHaveTextContent('Сеть недоступна');
    expect(screen.getByRole('button', {name: 'Создать заявку'})).toBeEnabled();
    expect(screen.getByPlaceholderText('Материал *')).toHaveValue('Цемент');
    expect(screen.getByText('Сохранить черновик')).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', {name: 'Создать заявку'}));
    expect(await screen.findByRole('button', {name: 'Создать заявку'})).toBeEnabled();
    expect(screen.queryByRole('alert')).not.toBeInTheDocument();
    expect(action).toHaveBeenCalledTimes(2);
  });

  test('unknown failure asks to check existing requests before submitting again', async () => {
    render(build(jest.fn().mockRejectedValue(undefined)));
    fireEvent.click(screen.getByRole('button', {name: 'Создать заявку'}));

    expect(await screen.findByRole('alert')).toHaveTextContent(
      'Проверьте список заявок перед повторной отправкой',
    );
    expect(screen.getByRole('alert')).not.toHaveTextContent('Попробуйте ещё раз');
    expect(screen.getByPlaceholderText('Материал *')).toHaveValue('Цемент');
  });
});

test('leadership creation explains actual approvals instead of automatic approval', () => {
  render(forms[0].build(jest.fn()));
  expect(screen.queryByText(/утверждена автоматически/)).not.toBeInTheDocument();
  expect(screen.queryByText(/главного инженера/)).not.toBeInTheDocument();
  expect(screen.getByText(/подтверждения прораба.*утверждения директора/)).toBeInTheDocument();
});

test('supplier creation does not promise immediate RFQ and cannot be hidden while pending', async () => {
  const pending = deferred();
  const close = jest.fn();
  render(forms[1].build(() => pending.promise, close));
  expect(screen.queryByRole('button', {name: 'Создать и запросить КП'})).not.toBeInTheDocument();
  fireEvent.click(screen.getByRole('button', {name: 'Создать заявку'}));
  for (const name of ['Новая заявка', 'Поставщики', 'Заявки', 'КП', 'История']) {
    expect(screen.getByRole('button', {name})).toBeDisabled();
  }
  expect(close).not.toHaveBeenCalled();
  await act(async () => pending.resolve());
});
