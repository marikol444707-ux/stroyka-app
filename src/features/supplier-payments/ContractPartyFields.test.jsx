import React from 'react';
import {render,screen,fireEvent} from '@testing-library/react';
import ContractPartyFields from './ContractPartyFields';
import {legalDraft} from './contractReviewClient';

test('conflicting bank sources stay visible and recognition requires explicit application',()=>{
 const onApply=jest.fn();
 const profile=legalDraft({bankName:'Банк карточки',inn:'7701234567'});
 const value={...profile,bankName:'Введённый банк'};
 render(<ContractPartyFields side="supplier" value={value} profile={profile}
   recognized={{status:'matched',fields:{bankName:{value:'Банк договора',quote:'Банк: Банк договора'}}}}
   onChange={jest.fn()} onApply={onApply}/>);
 expect(screen.getByLabelText('Банк').value).toBe('Введённый банк');
 expect(screen.getByText('Отличается от карточки')).not.toBeNull();
 expect(screen.getByText('Банк карточки')).not.toBeNull();
 expect(screen.getByText('Банк: Банк договора')).not.toBeNull();
 expect(onApply).not.toHaveBeenCalled();
 fireEvent.click(screen.getByText('Подставить из договора'));
 expect(onApply).toHaveBeenCalledWith('bankName','Банк договора');
});
