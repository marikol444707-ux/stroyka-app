import React from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';

import ReimburseModal from './ReimburseModal';


describe('ReimburseModal ownership payload', () => {
  beforeEach(() => {
    global.fetch = jest.fn().mockResolvedValue({ok: true});
  });

  afterEach(() => {
    jest.restoreAllMocks();
  });

  it('submits only the status and lets the server derive the approver', async () => {
    render(
      <ReimburseModal
        showReimburseModal
        setShowReimburseModal={jest.fn()}
        C={{text:'#111',textSec:'#666',textMuted:'#888',warning:'#a60',warningLight:'#fff',warningBorder:'#ddd',accent:'#f60',bg:'#fff',bgWhite:'#fff',border:'#ddd'}}
        card={{}}
        btnG={{}}
        btnO={{}}
        btnR={{}}
        ownExpenses={[{id:9,status:'Ожидает',employeeId:23,employeeName:'Мастер',description:'Бензин',amount:500,projectName:''}]}
        users={[]}
        staff={[]}
        roleLabels={{}}
        expenseCategories={[]}
        fileSrc={value => value}
        setShowPhotoModal={jest.fn()}
        API=""
        user={{name:'Клиентская подмена'}}
        loadAll={jest.fn()}
      />
    );
    fireEvent.click(screen.getByRole('button', {name:'✅'}));

    await waitFor(() => expect(global.fetch).toHaveBeenCalledTimes(1));
    const [, request] = global.fetch.mock.calls[0];
    expect(JSON.parse(request.body)).toEqual({status:'Возмещено'});
    expect(request.body).not.toContain('Клиентская подмена');
  });
});
