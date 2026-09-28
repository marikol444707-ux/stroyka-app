import React from 'react';
import {fireEvent,render,screen} from '@testing-library/react';
import InvoiceLineTaxFields from './InvoiceLineTaxFields';

test('maps tax amounts to source quote positions and retains exact input',()=>{
  const onChange=jest.fn();
  render(<InvoiceLineTaxFields items={[{materialName:'Кабель',quotePosition:7},{materialName:'Труба',quotePosition:2}]}
    values={[{sourceOfferPosition:7,vatAmount:'12.34'},{sourceOfferPosition:2,vatAmount:'0'}]} onChange={onChange}/>);
  expect(screen.getByLabelText('НДС, ₽ — 1. Кабель')).toHaveValue(12.34);
  fireEvent.change(screen.getByLabelText('НДС, ₽ — 2. Труба'),{target:{value:'0.01'}});
  expect(onChange).toHaveBeenCalledWith([{sourceOfferPosition:7,vatAmount:'12.34'},{sourceOfferPosition:2,vatAmount:'0.01'}]);
});

test('missing tax stays empty and is never guessed as zero',()=>{
  render(<InvoiceLineTaxFields items={[{materialName:'А'},{materialName:'Б'}]} onChange={()=>{}}/>);
  expect(screen.getByLabelText('НДС, ₽ — 1. А')).toHaveValue(null);
  expect(screen.getByLabelText('НДС, ₽ — 2. Б')).toBeRequired();
});

test('one line uses the invoice tax field instead of duplicate entry',()=>{
  const {container}=render(<InvoiceLineTaxFields items={[{materialName:'А'}]} onChange={()=>{}}/>);
  expect(container).toBeEmptyDOMElement();
});
