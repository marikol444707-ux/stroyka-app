import React from 'react';
import {render,screen} from '@testing-library/react';
import AccountingPerformerClosingPanel from './AccountingPerformerClosingPanel';
import {actRemaining} from '../utils/actSettlement';
import {buildMasterActDocContent} from '../utils/print/contractorActDocumentBuilders';

// Unconfirmed historical acts have zero retention; confirmed amounts come from the server.
test.each([[0,0,0],[2000,0,0],[0,500,0],[2000,500,200]])('closing and printed act must show the same remaining balance (advance %i, retention %i, released %i)',(advanceAmount,retentionAmount,retentionReleased)=>{
 const month=new Date().toISOString().slice(0,7);
 const end=new Date(Date.UTC(Number(month.slice(0,4)),Number(month.slice(5,7)),0)).toISOString().slice(0,10);
 const work={id:1,companyId:4,masterId:100,masterName:'Тестовый подрядчик',project:'Объект',
  workPackage:'Отделка',roomName:'Комната',status:'Подтверждено',date:month+'-01',quantity:1,executionTotal:10000};
 const savedAct={id:10,companyId:4,masterId:100,masterName:work.masterName,project:work.project,
  workPackage:work.workPackage,periodStart:month+'-01',periodEnd:end,totalAmount:10000,paidAmount:0,
  advanceAmount,retentionAmount,retentionReleased,remainingAmount:10000-advanceAmount-retentionAmount+retentionReleased,workJournalIds:[1]};
 render(<AccountingPerformerClosingPanel C={{}} card={{}} inp={{}} projects={[]} listSearch=""
  staff={[{id:100,name:work.masterName,role:'подрядчик'}]} workJournal={[work]} interimActs={[savedAct]}/>);
 const ui=screen.getByText('К выплате',{exact:true}).parentElement.querySelector('b').textContent;
 const toMoney=text=>Number(text.replace(/[^\d-]/g,''));
 const doc=document.createElement('div');doc.innerHTML=buildMasterActDocContent(savedAct,{workJournal:[work]});
 const remainingRow=[...doc.querySelectorAll('tr')].find(row=>row.textContent.includes('Остаток к выплате:'));
 const printed=toMoney(remainingRow.lastElementChild.textContent);
 expect(printed).toBe(actRemaining(savedAct));
 expect({closing:toMoney(ui),printed}).toEqual({closing:printed,printed});
});
