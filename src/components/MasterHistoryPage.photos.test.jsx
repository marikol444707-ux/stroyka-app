import React from 'react';
import {fireEvent, render, screen, waitFor} from '@testing-library/react';
import MasterHistoryPage from './MasterHistoryPage';

test('history opens each protected journal photo as an authenticated blob, not a raw URL', async () => {
  const originalFetch = global.fetch;
  const create = URL.createObjectURL, revoke = URL.revokeObjectURL;
  let count = 0;
  URL.createObjectURL = jest.fn(() => 'blob:photo-' + (++count));
  URL.revokeObjectURL = jest.fn();
  global.fetch = jest.fn(async () => ({ok: true, blob: async () => new Blob(['photo'], {type:'image/png'})}));
  const open = jest.fn();
  try {
    const {unmount} = render(<MasterHistoryPage C={{}} btnG={{}} card={{}} user={{id:11}} piecework={[]}
      expandedProject="2026-11-08" setExpandedProject={jest.fn()} listSearch="" matchSearch={()=>true}
      fmtMeasure={(n,u)=>`${n} ${u}`} setListSearch={jest.fn()} setShowPhotoModal={open}
      fileSrc={value=>'/api'+value}
      myJournal={[{id:1,date:'2026-11-08',project:'Объект',description:'Работа',quantity:3,unit:'м2',
        status:'На проверке',photoUrl:'/tenant-files/1/content,/tenant-files/2/content'}]}/>);
    await waitFor(() => expect(fetch).toHaveBeenCalledTimes(2));
    const buttons = await screen.findAllByRole('button', {name:/Фото работы/});
    fireEvent.click(buttons[0]);fireEvent.click(buttons[1]);
    expect(open.mock.calls).toEqual([['blob:photo-1'],['blob:photo-2']]);
    expect(fetch).toHaveBeenCalledWith('/api/tenant-files/1/content', expect.objectContaining({credentials:'include'}));
    unmount();
  } finally {
    global.fetch = originalFetch;URL.createObjectURL=create;URL.revokeObjectURL=revoke;
  }
});
