import React from 'react';
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import WorkAssignmentModal, { performerRows } from './WorkAssignmentModal';

function typeManualBrigade(name) {
  fireEvent.change(screen.getByRole('combobox', {name: 'Исполнитель'}), {target: {value: '__manual__'}});
  fireEvent.change(screen.getByPlaceholderText('Название бригады'), {target: {value: name}});
}

it('mobile steps preserve selected work and prices when going back', async () => {
  const originalFetch = global.fetch;
  const fetchMock = jest.fn().mockResolvedValue({ok: false, json: async () => ({detail: 'Тестовая ошибка'})});
  global.fetch = fetchMock;
  try {
  render(<WorkAssignmentModal show onClose={jest.fn()}
    selectedEstimate={{id:25,sections:[{name:'Стены',items:[
      {name:'Штукатурка',unit:'м2',quantity:2,priceWork:100,estimateItemKey:'work-1'},
      {name:'Грунтовка',unit:'м2',quantity:1,priceWork:100,estimateItemKey:'work-2'},
    ]}]}} users={[{id:11,name:'Мастер Иван',role:'мастер'}]} staff={[]}
    API="/api" loadAll={jest.fn()} C={{}} card={{}} inp={{}} btnO={{}} btnG={{}} btnB={{}} isMobile/>);
  expect(screen.getByRole('combobox',{name:'Исполнитель'})).toHaveValue('user:11');
  expect(screen.queryByRole('checkbox')).not.toBeInTheDocument();
  expect(screen.queryByRole('button',{name:'Выдать в работу'})).not.toBeInTheDocument();
  fireEvent.click(screen.getByRole('button',{name:'Далее'}));
  fireEvent.click(screen.getByRole('checkbox',{name:'Выбрать работу: Грунтовка'}));
  fireEvent.click(screen.getByRole('button',{name:'Далее'}));
  expect(screen.getByRole('button',{name:'Выдать в работу'})).toBeEnabled();
  expect(screen.queryByRole('checkbox',{name:'Выбрать работу: Грунтовка'})).not.toBeInTheDocument();
  fireEvent.click(screen.getByRole('button',{name:'Настроить цену'}));
  fireEvent.change(screen.getByRole('spinbutton',{name:'Цена исполнителю: Штукатурка'}),{target:{value:'75'}});
  fireEvent.click(screen.getByRole('button',{name:'Назад'}));
  expect(screen.getByRole('checkbox',{name:'Выбрать работу: Грунтовка'})).not.toBeChecked();
  expect(screen.getByRole('checkbox',{name:'Выбрать работу: Штукатурка'})).toBeChecked();
  fireEvent.click(screen.getByRole('button',{name:'Далее'}));
  expect(screen.getByRole('spinbutton',{name:'Цена исполнителю: Штукатурка'})).toHaveValue(75);
  fireEvent.click(screen.getByRole('button', {name: 'Выдать в работу'}));
  await waitFor(() => expect(screen.getByRole('alert')).toHaveTextContent('Тестовая ошибка'));
  const payload = JSON.parse(fetchMock.mock.calls[0][1].body);
  expect(payload.assignee.contractorId).toBe(11);
  expect(payload.assignee.contractorRef).toEqual({type:'user',id:11});
  expect(payload.items).toEqual([expect.objectContaining({estimateItemKey: 'work-1', manualPrice: 75})]);
  } finally {
    global.fetch = originalFetch;
  }
});

describe('work assignment performers', () => {
  it('keeps each same-name contract beside the user and submits its exact contract ID',async()=>{
    const original=global.fetch;
    global.fetch=jest.fn().mockResolvedValue({ok:false,json:async()=>({detail:'Проверка договора'})});
    try{
      render(<WorkAssignmentModal show onClose={jest.fn()}
        selectedEstimate={{id:25,projectId:17,workPackage:'Основная',sections:[{name:'Отделка',items:[{name:'Грунтовка',unit:'м²',quantity:5,priceWork:100,estimateItemKey:'contract-work'}]}]}}
        staff={[]} users={[{id:11,name:'Иван',role:'мастер'}]}
        brigadeContracts={[
          {id:70,projectId:17,workPackage:'Основная',brigadeName:'Иван',contractorId:11},
          {id:71,projectId:17,workPackage:'Основная',brigadeName:'Иван',contractorId:11},
          {id:72,projectId:18,workPackage:'Основная',brigadeName:'Чужой объект',contractorId:11},
          {id:73,projectId:17,workPackage:'Электрика',brigadeName:'Другой пакет',contractorId:11},
        ]}
        API="/api" loadAll={jest.fn()} C={{}} card={{}} inp={{}} btnO={{}} btnG={{}} btnB={{}} isMobile={false}/>);
      expect(screen.getByRole('option',{name:'Иван · договор №70'})).toBeInTheDocument();
      expect(screen.getByRole('option',{name:'Иван · договор №71'})).toBeInTheDocument();
      expect(screen.getByRole('option',{name:'Иван · учётная запись'})).toBeInTheDocument();
      expect(screen.queryByRole('option',{name:/Чужой объект|Другой пакет/})).not.toBeInTheDocument();
      fireEvent.change(screen.getByRole('combobox',{name:'Исполнитель'}),{target:{value:'contract:70'}});
      fireEvent.click(screen.getByRole('button',{name:'Выдать в работу'}));
      expect(await screen.findByRole('alert')).toHaveTextContent('Проверка договора');
      expect(JSON.parse(fetch.mock.calls[0][1].body).assignee).toMatchObject({contractorId:11,contractorRef:{type:'contract',id:70}});
    }finally{global.fetch=original;}
  });
  it('submits the selected staff card when another user has the same number and name',async()=>{
    const original=global.fetch;
    global.fetch=jest.fn().mockResolvedValue({ok:false,json:async()=>({detail:'Проверка точного выбора'})});
    try{
      render(<WorkAssignmentModal show onClose={jest.fn()}
        selectedEstimate={{id:25,sections:[{name:'Электрика',items:[{name:'Кабель',unit:'м',quantity:5,priceWork:100,estimateItemKey:'typed-1'}]}]}}
        staff={[{id:23,name:'Иван',role:'мастер'}]} users={[{id:23,name:'Иван',role:'мастер'}]}
        API="/api" loadAll={jest.fn()} C={{}} card={{}} inp={{}} btnO={{}} btnG={{}} btnB={{}} isMobile={false}/>);
      fireEvent.change(screen.getByRole('combobox',{name:'Исполнитель'}),{target:{value:'staff:23'}});
      expect(screen.getByRole('option',{name:'Иван · сотрудник'})).toBeInTheDocument();
      expect(screen.getByRole('option',{name:'Иван · учётная запись'})).toBeInTheDocument();
      fireEvent.click(screen.getByRole('button',{name:'Выдать в работу'}));
      expect(await screen.findByRole('alert')).toHaveTextContent('Проверка точного выбора');
      expect(JSON.parse(fetch.mock.calls[0][1].body).assignee).toMatchObject({contractorId:23,contractorRef:{type:'staff',id:23}});
    }finally{global.fetch=original;}
  });
  it('keeps equal staff/user numbers and names as distinct exact selections', () => {
    const rows=performerRows([{id:23,name:'Иван',role:'мастер',emailWork:'same@local.invalid'}],
      [{id:23,name:'Иван',role:'мастер',email:'same@local.invalid'}]);
    expect(rows).toHaveLength(2);
    expect(rows.map(row=>row.optionId).sort()).toEqual(['staff:23','user:23']);
    expect(rows.map(row=>row.contractorRef)).toEqual(expect.arrayContaining([
      {type:'staff',id:23},{type:'user',id:23},
    ]));
  });

  it('only deduplicates a staff account through the persisted accessUserId', () => {
    const rows=performerRows([{id:23,name:'Иван',role:'мастер',accessUserId:41}],
      [{id:23,name:'Иван',role:'мастер'},{id:41,name:'Другой профиль',role:'мастер'}]);
    expect(rows).toHaveLength(2);
    expect(rows.find(row=>row.optionId==='staff:23').contractorRef).toEqual({type:'staff',id:23});
    expect(rows.find(row=>row.optionId==='user:23').contractorRef).toEqual({type:'user',id:23});
  });
  it('offers a subcontractor as an estimate work assignee', () => {
    const rows = performerRows([], [
      { id: 11, name: 'ИП Исполнитель', role: 'субподрядчик' },
      { id: 12, name: 'Бухгалтер', role: 'бухгалтер' },
    ]);

    expect(rows).toHaveLength(1);
    expect(rows[0]).toMatchObject({
      contractorId: 11,
      name: 'ИП Исполнитель',
      employmentType: 'субподрядчик',
    });
  });

  it('offers an existing brigade contract without forcing manual typing', () => {
    const rows = performerRows([], [], [
      { id: 70, brigadeName: 'Бригада Север', contractorType: 'Своя бригада' },
    ]);

    expect(rows).toEqual([
      expect.objectContaining({
        optionId: 'contract:70',
        contractorId: '',
        name: 'Бригада Север',
      }),
    ]);
  });
});

it('finds a work in a long estimate without changing the selected assignments', () => {
  const items = Array.from({length: 10}, (_, index) => ({
    name: `Монтаж кабеля ${index + 1}`, unit: 'м', quantity: 1, priceWork: 100,
    estimateItemKey: `work-${index + 1}`,
  }));
  render(<WorkAssignmentModal show onClose={jest.fn()}
    selectedEstimate={{id:25, sections:[{name:'Электрика',items}]}}
    staff={[]} users={[{id:11,name:'Мастер Иван',role:'мастер'}]}
    API="/api" loadAll={jest.fn()} C={{}} card={{}} inp={{}} btnO={{}} btnG={{}} btnB={{}} isMobile={false} />);

  fireEvent.change(screen.getByRole('searchbox',{name:'Найти работу'}), {target:{value:'кабеля 10'}});
  expect(screen.getByText('Монтаж кабеля 10')).toBeInTheDocument();
  expect(screen.queryByText('Монтаж кабеля 1')).not.toBeInTheDocument();
  expect(screen.getByText(/Показано: 1 из 10/)).toBeInTheDocument();
  expect(screen.getByText('Выбрано: 10 из 10')).toBeInTheDocument();
  expect(screen.getByText('Ещё 9 выбранных работ скрыты поиском. Они тоже будут выданы исполнителю.')).toBeInTheDocument();
  fireEvent.click(screen.getByRole('button', {name: 'Оставить только найденные'}));
  expect(screen.getByText('Выбрано: 1 из 10')).toBeInTheDocument();
  expect(screen.getByLabelText('Выбрать работу: Монтаж кабеля 10')).toBeChecked();
  expect(screen.queryByRole('button', {name: 'Оставить только найденные'})).not.toBeInTheDocument();
  fireEvent.change(screen.getByRole('searchbox',{name:'Найти работу'}), {target:{value:'неизвестная'}});
  expect(screen.getByText('Работы не найдены. Очистите поиск.')).toBeInTheDocument();
});

it('changes only visible work when selecting or clearing a filtered list', () => {
  const items = Array.from({length: 10}, (_, index) => ({
    name: `Монтаж кабеля ${index + 1}`, unit: 'м', quantity: 1, priceWork: 100,
    estimateItemKey: `work-${index + 1}`,
  }));
  render(<WorkAssignmentModal show onClose={jest.fn()}
    selectedEstimate={{id:25, sections:[{name:'Электрика',items}]}}
    staff={[]} users={[{id:11,name:'Мастер Иван',role:'мастер'}]}
    API="/api" loadAll={jest.fn()} C={{}} card={{}} inp={{}} btnO={{}} btnG={{}} btnB={{}} isMobile={false} />);

  fireEvent.change(screen.getByRole('searchbox', {name:'Найти работу'}), {target:{value:'кабеля 10'}});
  fireEvent.click(screen.getByRole('button', {name:'Снять показанные'}));
  expect(screen.getByText('Выбрано: 9 из 10')).toBeInTheDocument();
  expect(screen.getByLabelText('Выбрать работу: Монтаж кабеля 10')).not.toBeChecked();
  fireEvent.click(screen.getByRole('button', {name:'Выбрать показанные'}));
  expect(screen.getByText('Выбрано: 10 из 10')).toBeInTheDocument();
  fireEvent.change(screen.getByRole('searchbox', {name:'Найти работу'}), {target:{value:'нет совпадений'}});
  expect(screen.getByRole('button', {name:'Выбрать показанные'})).toBeDisabled();
});

describe('work assignment prices', () => {
  beforeEach(() => {
    global.fetch = jest.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ok: true, brigadeName: 'Бригада', items: [{}, {}], contractId: 77}),
    });
    Storage.prototype.getItem = jest.fn(() => 'token');
    window.alert = jest.fn();
  });

  afterEach(() => {
    jest.restoreAllMocks();
  });

  it('uses one performer choice and only asks for a name for a new brigade', () => {
    render(
      <WorkAssignmentModal
        show onClose={jest.fn()}
        selectedEstimate={{id: 25, sections: [{name: 'Монтаж', items: [
          {name: 'Блок управления', unit: 'шт', quantity: 1, priceWork: 2000, estimateItemKey: 'work-1'},
        ]}]}}
        staff={[]} users={[{id: 11, name: 'Мастер Иван', role: 'мастер'}]}
        API="/api" loadAll={jest.fn()}
        C={{}} card={{}} inp={{}} btnO={{}} btnG={{}} btnB={{}} isMobile={false}
      />
    );

    expect(screen.queryByPlaceholderText('Название бригады')).not.toBeInTheDocument();
    expect(screen.getByRole('combobox', {name: 'Исполнитель'})).toHaveValue('user:11');

    typeManualBrigade('Бригада Север');
    expect(screen.getByPlaceholderText('Название бригады')).toHaveValue('Бригада Север');
    fireEvent.change(screen.getByRole('combobox', {name: 'Исполнитель'}), {target: {value: 'user:11'}});
    expect(screen.queryByPlaceholderText('Название бригады')).not.toBeInTheDocument();
  });

  it('applies the coefficient to all rows and sends one edited row as a manual price', async () => {
    render(
      <WorkAssignmentModal
        show
        onClose={jest.fn()}
        selectedEstimate={{
          id: 25,
          projectName: 'Объект',
          sections: [{
            name: 'Монтаж',
            items: [
              {name: 'Блок управления', unit: 'шт', quantity: 1, priceWork: 2000, estimateItemKey: 'work-1'},
              {name: 'Прокладка кабеля', unit: 'м', quantity: 10, priceWork: 100, estimateItemKey: 'work-2'},
            ],
          }],
        }}
        staff={[]}
        users={[]}
        API="/api"
        loadAll={jest.fn()}
        C={{}}
        card={{}}
        inp={{}}
        btnO={{}}
        btnG={{}}
        btnB={{}}
        isMobile={false}
      />
    );

    typeManualBrigade('Бригада');
    fireEvent.click(screen.getByRole('button', {name: 'Настроить цену'}));
    expect(screen.getByLabelText('Доля исполнителя, %')).toHaveValue(60);
    fireEvent.change(screen.getByLabelText('Доля исполнителя, %'), {target: {value: '40'}});
    fireEvent.change(screen.getByLabelText('Цена исполнителю: Блок управления'), {target: {value: '1000'}});
    fireEvent.click(screen.getByRole('button', {name: 'Выдать в работу'}));

    await waitFor(() => expect(global.fetch).toHaveBeenCalledTimes(1));
    const request = global.fetch.mock.calls[0][1];
    const payload = JSON.parse(request.body);

    expect(payload.coefficient).toBe(0.4);
    expect(payload.items).toEqual([
      expect.objectContaining({estimateItemKey: 'work-1', priceMode: 'manual', manualPrice: 1000}),
      expect.objectContaining({estimateItemKey: 'work-2', priceMode: 'coefficient'}),
    ]);
    expect(payload.items[1].manualPrice).toBeUndefined();
  });

  it('reports a saved assignment as successful when the follow-up refresh fails', async () => {
    const onClose = jest.fn();
    const loadAll = jest.fn().mockRejectedValue(new Error('refresh unavailable'));
    render(
      <WorkAssignmentModal
        show
        onClose={onClose}
        selectedEstimate={{id: 25, projectName: 'Объект', sections: [{name: 'Монтаж', items: [
          {name: 'Блок управления', unit: 'шт', quantity: 1, priceWork: 2000, estimateItemKey: 'work-1'},
        ]}]}}
        staff={[]}
        users={[]}
        API="/api"
        loadAll={loadAll}
        C={{}}
        card={{}}
        inp={{}}
        btnO={{}}
        btnG={{}}
        btnB={{}}
        isMobile={false}
      />
    );

    typeManualBrigade('Бригада');
    fireEvent.click(screen.getByRole('button', {name: 'Выдать в работу'}));

    await waitFor(() => expect(onClose).toHaveBeenCalledTimes(1));
    expect(global.fetch).toHaveBeenCalledTimes(1);
    expect(loadAll).toHaveBeenCalledTimes(1);
    expect(window.alert).toHaveBeenCalledWith(expect.stringContaining('Работы выданы'));
    expect(window.alert).toHaveBeenCalledWith(expect.stringContaining('Обновите страницу'));
    expect(window.alert).not.toHaveBeenCalledWith(expect.stringContaining('Не удалось назначить работы'));
  });

  it('keeps the draft open when the assignment request itself fails', async () => {
    global.fetch.mockResolvedValueOnce({ok: false, json: async () => ({detail: 'Работы уже назначены'})});
    const onClose = jest.fn();
    const loadAll = jest.fn();
    render(
      <WorkAssignmentModal
        show onClose={onClose}
        selectedEstimate={{id: 25, sections: [{name: 'Монтаж', items: [
          {name: 'Блок управления', unit: 'шт', quantity: 1, priceWork: 2000, estimateItemKey: 'work-1'},
        ]}]}}
        staff={[]} users={[]} API="/api" loadAll={loadAll}
        C={{}} card={{}} inp={{}} btnO={{}} btnG={{}} btnB={{}} isMobile={false}
      />
    );

    typeManualBrigade('Бригада');
    fireEvent.click(screen.getByRole('button', {name: 'Выдать в работу'}));

    await waitFor(() => expect(screen.getByRole('alert')).toHaveTextContent('Работы уже назначены'));
    expect(window.alert).not.toHaveBeenCalled();
    expect(onClose).not.toHaveBeenCalled();
    expect(loadAll).not.toHaveBeenCalled();
    expect(screen.getByPlaceholderText('Название бригады')).toHaveValue('Бригада');
  });

  it('explains why issue is unavailable before sending', () => {
    render(<WorkAssignmentModal show onClose={jest.fn()}
      selectedEstimate={{id:25,sections:[{name:'Монтаж',items:[
        {name:'Блок управления',unit:'шт',quantity:1,priceWork:2000,estimateItemKey:'work-1'},
      ]}]}}
      staff={[]} users={[]} API="/api" loadAll={jest.fn()}
      C={{}} card={{}} inp={{}} btnO={{}} btnG={{}} btnB={{}} isMobile={false} />);

    expect(screen.getByText('Сначала выберите исполнителя.')).toBeInTheDocument();
    typeManualBrigade('Бригада');
    expect(screen.queryByText('Сначала выберите исполнителя.')).not.toBeInTheDocument();
    fireEvent.click(screen.getByLabelText('Выбрать работу: Блок управления'));
    expect(screen.getByText('Отметьте хотя бы одну работу.')).toBeInTheDocument();
  });

  it('preserves an in-progress assignment when performer data refreshes', () => {
    const selectedEstimate = {
      id: 25,
      projectName: 'Объект',
      sections: [{name: 'Монтаж', items: [
        {name: 'Блок управления', unit: 'шт', quantity: 1, priceWork: 2000, estimateItemKey: 'work-1'},
        {name: 'Прокладка кабеля', unit: 'м', quantity: 10, priceWork: 100, estimateItemKey: 'work-2'},
      ]}],
    };
    const props = {
      show: true, onClose: jest.fn(), selectedEstimate, brigadeContracts: [],
      brigadeContractItems: [], staff: [], users: [], API: '/api', loadAll: jest.fn(),
      C: {}, card: {}, inp: {}, btnO: {}, btnG: {}, btnB: {}, isMobile: false,
    };
    const {rerender} = render(<WorkAssignmentModal {...props} />);
    typeManualBrigade('Бригада Север');
    fireEvent.click(screen.getByLabelText('Выбрать работу: Прокладка кабеля'));
    fireEvent.click(screen.getByRole('button', {name: 'Настроить цену'}));
    fireEvent.change(screen.getByLabelText('Доля исполнителя, %'), {target: {value: '40'}});
    fireEvent.change(screen.getByLabelText('Цена исполнителю: Блок управления'), {target: {value: '950'}});

    rerender(<WorkAssignmentModal {...props} users={[{id: 11, name: 'Новый мастер', role: 'мастер'}]} />);

    expect(screen.getByPlaceholderText('Название бригады')).toHaveValue('Бригада Север');
    expect(screen.getByLabelText('Выбрать работу: Прокладка кабеля')).not.toBeChecked();
    expect(screen.getByLabelText('Доля исполнителя, %')).toHaveValue(40);
    expect(screen.getByLabelText('Цена исполнителю: Блок управления')).toHaveValue(950);

    const changedEstimate = {
      ...selectedEstimate,
      sections: [{...selectedEstimate.sections[0], items: [
        {...selectedEstimate.sections[0].items[0], quantity: 2},
        selectedEstimate.sections[0].items[1],
      ]}],
    };
    rerender(<WorkAssignmentModal {...props} selectedEstimate={changedEstimate} />);
    expect(screen.queryByPlaceholderText('Название бригады')).not.toBeInTheDocument();
    expect(screen.getByLabelText('Выбрать работу: Прокладка кабеля')).toBeChecked();

    rerender(<WorkAssignmentModal {...props} show={false} />);
    rerender(<WorkAssignmentModal {...props} />);
    expect(screen.queryByPlaceholderText('Название бригады')).not.toBeInTheDocument();
    expect(screen.getByLabelText('Выбрать работу: Прокладка кабеля')).toBeChecked();
  });

  it('selects only unassigned work by default and sends it in one action', async () => {
    render(
      <WorkAssignmentModal
        show
        onClose={jest.fn()}
        selectedEstimate={{
          id: 25,
          projectName: 'Объект',
          workPackage: 'Основная',
          sections: [{
            name: 'Монтаж',
            items: [
              {name: 'Уже выданная работа', unit: 'шт', quantity: 1, priceWork: 2000, estimateItemKey: 'work-1'},
              {name: 'Новая работа', unit: 'м', quantity: 10, priceWork: 100, estimateItemKey: 'work-2'},
            ],
          }],
        }}
        brigadeContracts={[{id: 70, projectName: 'Объект', workPackage: 'Основная', brigadeName: 'Бригада 1'}]}
        brigadeContractItems={[{
          id: 701,
          contractId: 70,
          projectName: 'Объект',
          workPackage: 'Основная',
          estimateItemKey: 'work-1',
        }]}
        staff={[]}
        users={[]}
        API="/api"
        loadAll={jest.fn()}
        C={{}}
        card={{}}
        inp={{}}
        btnO={{}}
        btnG={{}}
        btnB={{}}
        isMobile={false}
      />
    );

    expect(screen.queryByText('Уже выданная работа')).not.toBeInTheDocument();
    expect(screen.getByText('Новая работа')).toBeInTheDocument();
    expect(screen.getByText('Уже назначено: 1')).toBeInTheDocument();
    fireEvent.click(screen.getByText('Уже назначено: 1'));
    const assignedList = screen.getByRole('region', {name: 'Уже назначенные работы'});
    expect(within(assignedList).getByText('Уже выданная работа')).toBeInTheDocument();
    expect(within(assignedList).getByText('Бригада 1')).toBeInTheDocument();
    expect(screen.queryByLabelText('Выбрать работу: Уже выданная работа')).not.toBeInTheDocument();
    expect(screen.getByText('Выбрано: 1 из 1')).toBeInTheDocument();
    expect(screen.getByRole('button', {name: 'Настроить цену'})).toBeInTheDocument();
    expect(screen.queryByRole('button', {name: 'Своя цена'})).not.toBeInTheDocument();

    typeManualBrigade('Бригада 2');
    fireEvent.click(screen.getByRole('button', {name: 'Выдать в работу'}));

    await waitFor(() => expect(global.fetch).toHaveBeenCalledTimes(1));
    const payload = JSON.parse(global.fetch.mock.calls[0][1].body);
    expect(payload.coefficient).toBe(0.6);
    expect(payload.items).toEqual([
      expect.objectContaining({estimateItemKey: 'work-2'}),
    ]);
  });

  it('explains when every estimate row is already assigned', () => {
    render(
      <WorkAssignmentModal
        show
        onClose={jest.fn()}
        selectedEstimate={{
          id: 25,
          projectName: 'Объект',
          workPackage: 'Основная',
          sections: [{name: 'Монтаж', items: [
            {name: 'Монтаж шкафа', unit: 'шт', quantity: 1, priceWork: 2000, estimateItemKey: 'work-1'},
          ]}],
        }}
        brigadeContracts={[{id: 70, projectName: 'Объект', workPackage: 'Основная', brigadeName: 'Бригада 1'}]}
        brigadeContractItems={[{
          id: 701,
          contractId: 70,
          projectName: 'Объект',
          workPackage: 'Основная',
          estimateItemKey: 'work-1',
        }]}
        API="/api"
        loadAll={jest.fn()}
        C={{}}
        card={{}}
        inp={{}}
        btnO={{}}
        btnG={{}}
        btnB={{}}
        isMobile={false}
      />
    );

    expect(screen.getByText('Все работы этой сметы уже назначены')).toBeInTheDocument();
    expect(screen.queryByRole('button', {name: 'Снять все'})).not.toBeInTheDocument();
    expect(screen.getByRole('button', {name: 'Выдать в работу'})).toBeDisabled();
  });
});


it('filters exact estimate sections without losing selections from another section', () => {
  render(<WorkAssignmentModal show onClose={jest.fn()}
    selectedEstimate={{id:25, sections:[
      {name:'Монтаж', items:[{name:'Монтаж кабеля',unit:'м',quantity:10,priceWork:100,estimateItemKey:'electrical'}]},
      {name:'Монтаж', items:[{name:'Монтаж трубы',unit:'м',quantity:5,priceWork:200,estimateItemKey:'plumbing'}]},
    ]}} staff={[]} users={[{id:11,name:'Мастер Иван',role:'мастер'}]}
    API="/api" loadAll={jest.fn()} C={{}} card={{}} inp={{}} btnO={{}} btnG={{}} btnB={{}} isMobile />);
  fireEvent.click(screen.getByRole('button', {name:'Далее'}));
  fireEvent.change(screen.getByRole('combobox', {name:'Раздел сметы'}), {target:{value:'0'}});
  expect(screen.getByRole('checkbox', {name:'Выбрать работу: Монтаж кабеля'})).toBeChecked();
  expect(screen.queryByRole('checkbox', {name:'Выбрать работу: Монтаж трубы'})).not.toBeInTheDocument();
  expect(screen.getByText('Выбрано: 2 из 2')).toBeInTheDocument();
  fireEvent.click(screen.getByRole('button', {name:'Снять показанные'}));
  expect(screen.getByText('Выбрано: 1 из 2')).toBeInTheDocument();
  fireEvent.click(screen.getByRole('button', {name:'Далее'}));
  expect(screen.getByRole('checkbox', {name:'Выбрать работу: Монтаж трубы'})).toBeChecked();
  expect(screen.queryByRole('checkbox', {name:'Выбрать работу: Монтаж кабеля'})).not.toBeInTheDocument();
  fireEvent.click(screen.getByRole('button', {name:'Назад'}));
  expect(screen.getByRole('combobox', {name:'Раздел сметы'})).toHaveValue('0');
});

it('combines section and text filters when retaining only found work', () => {
  render(<WorkAssignmentModal show onClose={jest.fn()}
    selectedEstimate={{id:25, sections:[
      {name:'Электрика', items:[{name:'Монтаж кабеля',unit:'м',quantity:10,priceWork:100,estimateItemKey:'cable'}]},
      {name:'Отделка', items:[{name:'Монтаж панели',unit:'м2',quantity:5,priceWork:200,estimateItemKey:'panel'}]},
    ]}} staff={[]} users={[{id:11,name:'Мастер Иван',role:'мастер'}]}
    API="/api" loadAll={jest.fn()} C={{}} card={{}} inp={{}} btnO={{}} btnG={{}} btnB={{}} isMobile={false} />);
  fireEvent.change(screen.getByRole('combobox', {name:'Раздел сметы'}), {target:{value:'1'}});
  fireEvent.change(screen.getByRole('searchbox', {name:'Найти работу'}), {target:{value:'Монтаж'}});
  fireEvent.click(screen.getByRole('button', {name:'Оставить только найденные'}));
  expect(screen.getByText('Выбрано: 1 из 2')).toBeInTheDocument();
  fireEvent.change(screen.getByRole('combobox', {name:'Раздел сметы'}), {target:{value:''}});
  expect(screen.getByRole('checkbox', {name:'Выбрать работу: Монтаж кабеля'})).not.toBeChecked();
  expect(screen.getByRole('checkbox', {name:'Выбрать работу: Монтаж панели'})).toBeChecked();
});
