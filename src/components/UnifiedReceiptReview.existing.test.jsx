import React from 'react';
import {render, screen, fireEvent} from '@testing-library/react';
import UnifiedReceiptReview from './UnifiedReceiptReview';

test('repeat scan of proven standalone receipt opens saved receipt without a posting action',async()=>{
  const previous=global.fetch;
  const open=jest.fn();
  global.fetch=jest.fn().mockResolvedValue({ok:true,json:async()=>({status:'existing_receipt',warehouseInvoiceIds:[91],receipts:[{id:91,number:'A1',date:'2026-10-18',project:'School',lines:[{materialName:'Brick',quantity:2,unit:'шт'}]}]})});
  try {
    render(<UnifiedReceiptReview API="/api" scan={{parsed:{},originalUrls:['/tenant-files/1/content'],location:'School'}} onOpenReceipt={open}/>);
    fireEvent.click(await screen.findByText('Открыть существующий приход #91'));
    expect(open).toHaveBeenCalledWith(91);
    expect(screen.queryByText('Оформить отдельный документ')).not.toBeInTheDocument();
    expect(screen.queryByText('Подтвердить фактическую приёмку')).not.toBeInTheDocument();
    expect(global.fetch).toHaveBeenCalledTimes(1);
  } finally {global.fetch=previous;}
});
