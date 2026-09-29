import React from 'react';
import {render,screen,fireEvent,waitFor} from '@testing-library/react';
import Button from './PublishContractButton';
const props={API:'',companyId:1,row:{sourceId:9,offerId:71,title:'Договор 362 версия 2',supplierName:'ВИСТ'},onPublished:jest.fn()};
afterEach(()=>jest.restoreAllMocks());
test('explicit addressed confirmation posts only the selected version',async()=>{
 global.fetch=jest.fn().mockResolvedValue({ok:true,json:async()=>({contractId:9,offerId:71,companyId:1,published:true})});
 render(<Button {...props}/>);
 fireEvent.click(screen.getByText('Передать поставщику'));
 expect(global.fetch).not.toHaveBeenCalled();
 expect(screen.getByText(/поставщику ВИСТ/)).not.toBeNull();
 fireEvent.click(screen.getByText('Подтвердить передачу'));
 await waitFor(()=>expect(props.onPublished).toHaveBeenCalled());
 expect(global.fetch.mock.calls[0][0]).toBe('/supplier-offers/71/contracts/9/publish');
 expect(global.fetch.mock.calls[0][1].headers['X-Company-Id']).toBe('1');
});
test('foreign response never confirms publication',async()=>{
 const callback=jest.fn();global.fetch=jest.fn().mockResolvedValue({ok:true,json:async()=>({contractId:9,offerId:71,companyId:2,published:true})});
 render(<Button {...props} onPublished={callback}/>);
 fireEvent.click(screen.getByText('Передать поставщику'));fireEvent.click(screen.getByText('Подтвердить передачу'));
 await screen.findByRole('alert');expect(callback).not.toHaveBeenCalled();
});
