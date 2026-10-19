import React from 'react';
import {fireEvent,render,screen,waitFor} from '@testing-library/react';
import MovementRecoveryNotice from './MovementRecoveryNotice';
test('restricted metadata allows cancellation without exposing or resuming hidden commands',async()=>{
 const cancel=jest.fn(async()=>{});const onResume=jest.fn();
 const draft={draftId:'a',restricted:true,commands:[]};
 render(<MovementRecoveryNotice recovery={{key:'12:2',blocked:true,drafts:[draft],cancel,refresh:jest.fn()}} onResume={onResume}/>);
 expect(screen.queryByText('Продолжить перемещение')).not.toBeInTheDocument();
 fireEvent.click(screen.getByText('Отменить неисполненные позиции'));
 await waitFor(()=>expect(cancel).toHaveBeenCalledWith(draft));expect(onResume).not.toHaveBeenCalled();
});
test('pending recovery offers resume and repeat check, never a silent discard',()=>{
 const draft={draftId:'a',commands:[]};const onResume=jest.fn();
 render(<MovementRecoveryNotice recovery={{key:'12:2',blocked:true,drafts:[draft],cancel:jest.fn(),refresh:jest.fn()}} onResume={onResume}/>);
 fireEvent.click(screen.getByText('Продолжить перемещение'));expect(onResume).toHaveBeenCalledWith(draft);
});
