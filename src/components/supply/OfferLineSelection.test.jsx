import React from 'react';
import {render,screen,fireEvent,waitFor} from '@testing-library/react';
import OfferLineSelection from './OfferLineSelection';
const lines=[{materialName:'Труба',quantity:2,unit:'м',requestPosition:0,pricePerUnit:100,totalPrice:200},{materialName:'Крепёж',quantity:5,unit:'шт',requestPosition:1,pricePerUnit:10,totalPrice:50}];
it('locks already ordered positions and submits only selected request positions',async()=>{
 const onSelect=jest.fn().mockResolvedValue();
 const offer={id:7,requestedItemsJson:JSON.stringify(lines),itemsKpJson:JSON.stringify(lines)};
 render(<OfferLineSelection offer={offer} offers={[offer,{awardedItemsJson:JSON.stringify([lines[0]])}]} onSelect={onSelect} C={{}}/>);
 expect(screen.getByRole('checkbox',{name:'Заказать Труба'})).toBeDisabled();
 expect(screen.getByText('Выбрано: 1 · 50 ₽')).toBeInTheDocument();
 fireEvent.click(screen.getByRole('button',{name:'Утвердить выбранные позиции'}));
 await waitFor(()=>expect(onSelect).toHaveBeenCalledWith(7,[1]));
});
it('supports choosing one line from a multi-line quote',()=>{
 const offer={id:7,requestedItemsJson:JSON.stringify(lines),itemsKpJson:JSON.stringify(lines)};
 render(<OfferLineSelection offer={offer} offers={[offer]} onSelect={jest.fn()} C={{}}/>);
 fireEvent.click(screen.getByRole('checkbox',{name:'Заказать Крепёж'}));
 expect(screen.getByText('Выбрано: 1 · 200 ₽')).toBeInTheDocument();
});
