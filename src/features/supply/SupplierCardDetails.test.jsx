import React from 'react';
import {render,screen,fireEvent} from '@testing-library/react';
import SupplierCardDetails from './SupplierCardDetails';
const C={border:'#ddd',textSec:'#666',text:'#111',bg:'#fff'};
test('shows company terms and never invents absent requisites',()=>{
 render(<SupplierCardDetails C={C} supplier={{paymentTerms:'Отсрочка 30 дней',deliveryTerms:'До объекта',inn:'1234567890'}}/>);
 expect(screen.getByText('Отсрочка 30 дней')).toBeInTheDocument();
 expect(screen.getByText('До объекта')).toBeInTheDocument();
 expect(screen.getByText('1234567890')).toBeInTheDocument();
 expect(screen.getAllByText('Не указано')).toHaveLength(9);
 expect(screen.queryByRole('button')).not.toBeInTheDocument();
});
test('switching supplier replaces terms rather than retaining another company values',()=>{
 const {rerender}=render(<SupplierCardDetails C={C} supplier={{paymentTerms:'Условия компании А'}}/>);
 rerender(<SupplierCardDetails C={C} supplier={{paymentTerms:'Условия компании Б'}}/>);
 expect(screen.queryByText('Условия компании А')).not.toBeInTheDocument();
 expect(screen.getByText('Условия компании Б')).toBeInTheDocument();
});
test('edit is an explicit action and notes are displayed as text',()=>{
 const onEdit=jest.fn();
 render(<SupplierCardDetails C={C} onEdit={onEdit} supplier={{notes:'<script>test</script>'}}/>);
 fireEvent.click(screen.getByRole('button',{name:'Изменить карточку'}));
 expect(onEdit).toHaveBeenCalledTimes(1);
 expect(screen.getByText('<script>test</script>')).toBeInTheDocument();
});
test('reads the requisites returned by the company directory API',()=>{
 render(<SupplierCardDetails C={C} supplier={{legal_address:'Адрес из каталога',kor_account:'30101810452500000411',director_name:'Иванов Иван',director_position:'Директор'}}/>);
 for(const text of ['Адрес из каталога','30101810452500000411','Иванов Иван','Директор']) expect(screen.getByText(text)).toBeInTheDocument();
});
