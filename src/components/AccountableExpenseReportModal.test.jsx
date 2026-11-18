import { fireEvent, render, screen, waitFor } from '@testing-library/react';

import AccountableExpenseReportModal from './AccountableExpenseReportModal';


describe('AccountableExpenseReportModal ownership payload', () => {
  beforeEach(() => {
    global.fetch = jest.fn().mockResolvedValue({ok: true, json: async () => ({ok:true,id:7})});
    global.alert = jest.fn();
  });

  afterEach(() => {
    jest.restoreAllMocks();
  });

  it('inherits the parent project and does not submit client-authored ownership', async () => {
    render(
      <AccountableExpenseReportModal
        reportingPayment={{id: 4, projectId: 19, projectName: 'Лицей', amount: 1000, spentAmount: 0}}
        setReportingPayment={jest.fn()}
        C={{text: '#111', textSec: '#666', border: '#ddd', bg: '#fff', accent: '#f60', textMuted: '#999'}}
        card={{}}
        inp={{}}
        btnO={{}}
        btnG={{}}
        projects={[{id: 99, name: 'Чужой объект'}]}
        expenseCategories={[{id: 'accountable', label: 'Подотчёт'}]}
        newExpense={{description: 'Бензин', amount: '300', photoUrl: '', projectName: 'Чужой объект'}}
        setNewExpense={jest.fn()}
        appendPhotos={jest.fn()}
        fileSrc={value => value}
        expenseSubmitting={false}
        setExpenseSubmitting={jest.fn()}
        API=""
        user={{name: 'Клиентская подмена'}}
        loadAll={jest.fn()}
      />,
    );

    expect(screen.getByText('Объект: Лицей')).toBeInTheDocument();
    expect(screen.queryByRole('option', {name: 'Чужой объект'})).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', {name: /Отправить/}));

    await waitFor(() => expect(global.fetch).toHaveBeenCalledTimes(1));
    const [, request] = global.fetch.mock.calls[0];
    const body = JSON.parse(request.body);
    expect(body).toEqual(expect.objectContaining({
      paymentId: 4,
      description: 'Бензин',
      amount: 300,
    }));
    expect(body).not.toHaveProperty('projectName');
    expect(body).not.toHaveProperty('projectId');
    expect(body).not.toHaveProperty('addedBy');
  });
});

const draftProps = () => ({
  reportingPayment:{id:4,companyId:4,projectName:'Лицей',amount:1000},
  setReportingPayment:jest.fn(),C:{},card:{},inp:{},btnO:{},btnG:{},expenseCategories:[],
  newExpense:{description:'Чек на материалы',amount:'300',photoUrl:'receipt.jpg'},setNewExpense:jest.fn(),
  appendPhotos:jest.fn(),fileSrc:v=>v,expenseSubmitting:false,setExpenseSubmitting:jest.fn(),API:'',loadAll:jest.fn(),
});

test('refused expense retains the receipt and does not report success or refresh',async()=>{
  global.fetch=jest.fn().mockResolvedValue({ok:false,status:409,json:async()=>({detail:'Сначала подтвердите тип выдачи'})});
  global.alert=jest.fn();const props=draftProps();render(<AccountableExpenseReportModal {...props}/>);
  fireEvent.click(screen.getByRole('button',{name:/Отправить/}));
  expect(await screen.findByRole('alert')).toHaveTextContent('тип выдачи');
  expect(screen.getByPlaceholderText('За что потрачено *')).toHaveValue('Чек на материалы');
  expect(screen.getByAltText('')).toHaveAttribute('src','receipt.jpg');
  expect(props.setNewExpense).not.toHaveBeenCalled();expect(props.setReportingPayment).not.toHaveBeenCalled();
  expect(props.loadAll).not.toHaveBeenCalled();expect(global.alert).not.toHaveBeenCalled();
});

test('late expense result cannot reset a reopened draft for the same payment',async()=>{
  const {act}=require('@testing-library/react');let finish;
  global.fetch=jest.fn().mockReturnValue(new Promise(resolve=>{finish=resolve;}));
  const props=draftProps();const {rerender}=render(<AccountableExpenseReportModal {...props}/>);
  fireEvent.click(screen.getByRole('button',{name:/Отправить/}));
  rerender(<AccountableExpenseReportModal {...props} reportingPayment={null}/>);
  rerender(<AccountableExpenseReportModal {...props} newExpense={{...props.newExpense,description:'Новый чек'}}/>);
  props.setExpenseSubmitting.mockClear();
  await act(async()=>finish({ok:true,json:async()=>({ok:true,id:8})}));
  expect(screen.getByPlaceholderText('За что потрачено *')).toHaveValue('Новый чек');
  expect(props.setNewExpense).not.toHaveBeenCalled();expect(props.setReportingPayment).not.toHaveBeenCalled();
  expect(props.loadAll).not.toHaveBeenCalled();expect(props.setExpenseSubmitting).not.toHaveBeenCalled();
});
