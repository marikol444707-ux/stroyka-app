import React from 'react';
import {render, screen} from '@testing-library/react';
import ClientsPage from './ClientsPage';
import {createClientForm} from '../features/projects/projectInitialForms';

const colors={text:'#111',textSec:'#555',textMuted:'#777',border:'#ccc',bg:'#fff'};
const props={
  C:colors,card:{},inp:{},btnO:{},btnG:{},btnR:{},clients:[],projects:[],showForm:true,
  setShowForm:jest.fn(),editingItem:null,setEditingItem:jest.fn(),newClient:createClientForm(),
  setNewClient:jest.fn(),saveClient:jest.fn(),listSearch:'',setListSearch:jest.fn(),
  expandedClient:null,setExpandedClient:jest.fn(),deleteClient:jest.fn(),matchSearch:()=>true,
};

test('customer form separates identification, signer and bank details', () => {
  render(<ClientsPage {...props}/>);
  expect(screen.getByLabelText('Название заказчика')).toBeInTheDocument();
  expect(screen.getByLabelText('ИНН заказчика')).toBeInTheDocument();
  expect(screen.getByText('Адрес и подписант договора')).toBeInTheDocument();
  expect(screen.getByText('Банковские реквизиты')).toBeInTheDocument();
  expect(screen.queryByText('Плательщик')).not.toBeInTheDocument();
});
