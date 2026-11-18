import React, { useState } from 'react';
import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import ProjectSafetyJournalPanel from './ProjectSafetyJournalPanel';
import { createProjectOperationActions } from '../features/project-operations/projectOperationActions';

const project = { id: 11, companyId: 2, name: 'Same project' };
const draft = { type: 'Первичный', instructionText: 'Manual draft', program: '', date: '2026-11-09', participants: [] };
const deferred = () => { let resolve; const promise = new Promise(r => { resolve = r; }); return { promise, resolve }; };
function Harness({ selected = project, save = async () => null, rows = [] }) {
  const [show, setShow] = useState('tb');
  const [entry, setEntry] = useState(draft);
  return <ProjectSafetyJournalPanel project={selected} projectName={selected.name} C={{}} tbJournal={rows}
    showForm={show} setShowForm={setShow} newTbEntry={entry} setNewTbEntry={setEntry}
    newParticipant="" setNewParticipant={() => {}} listSearch="" setListSearch={() => {}}
    tbTypes={[{value:'Первичный'}]} matchSearch={() => true} saveTbEntry={save}
    buildTBContent={() => ''} showPreview={() => {}} />;
}
afterEach(() => jest.restoreAllMocks());

test.each([403,409,500])('HTTP %s cannot create a fake locally saved entry', async status => {
  jest.spyOn(window,'alert').mockImplementation(() => {});
  jest.spyOn(console,'error').mockImplementation(() => {});
  const setTbJournal = jest.fn();
  global.fetch = jest.fn(async () => ({ok:false,status,json:async () => ({detail:'Denied'})}));
  localStorage.setItem('tbJournal','unchanged');
  const actions=createProjectOperationActions({API:'/api',user:{name:'Test'},tbJournal:[],setTbJournal});
  await expect(actions.saveTbEntry({...draft,project:project.name,projectId:11,companyId:2})).resolves.toBeNull();
  expect(setTbJournal).not.toHaveBeenCalled();
  expect(localStorage.getItem('tbJournal')).toBe('unchanged');
});

test('failed save keeps the form and its text', async () => {
  render(<Harness />);
  fireEvent.click(screen.getByRole('button',{name:'Сохранить'}));
  await act(async () => {});
  expect(screen.getByDisplayValue('Manual draft')).toBeInTheDocument();
});

test('list excludes foreign and unowned rows with the same name', () => {
  const row={id:1,companyId:2,projectId:11,project:'Renamed',type:'OWN',date:'2026-11-09',participants:[]};
  render(<Harness rows={[row,{...row,id:2,companyId:3,project:project.name,type:'FOREIGN'},
    {id:3,project:project.name,type:'UNOWNED',participants:[]}]} />);
  expect(screen.getByText('OWN')).toBeInTheDocument();
  expect(screen.queryByText('FOREIGN')).not.toBeInTheDocument();
  expect(screen.queryByText('UNOWNED')).not.toBeInTheDocument();
});

test('late AI answer preserves edits made after generation began', async () => {
  const pending=deferred();global.fetch=jest.fn(() => pending.promise);
  render(<Harness />);
  fireEvent.click(screen.getByTitle('Сгенерировать текст по ГОСТ через ИИ'));
  fireEvent.change(screen.getByPlaceholderText('Текст инструктажа (можно сгенерировать ИИ →)'),{target:{value:'New manual text'}});
  await act(async () => pending.resolve({ok:true,json:async () => ({instructionText:'Old AI answer'})}));
  expect(screen.getByDisplayValue('New manual text')).toBeInTheDocument();
});

test('late successful save cannot close a newer project form', async () => {
  const pending=deferred();const save=jest.fn(() => pending.promise);
  const view=render(<Harness save={save} />);
  fireEvent.click(screen.getByRole('button',{name:'Сохранить'}));
  view.rerender(<Harness save={save} selected={{id:22,companyId:2,name:'Other'}} />);
  fireEvent.change(screen.getByPlaceholderText('Текст инструктажа (можно сгенерировать ИИ →)'),{target:{value:'Other project draft'}});
  await act(async () => pending.resolve({id:4,companyId:2,projectId:11}));
  expect(screen.getByDisplayValue('Other project draft')).toBeInTheDocument();
});

test('old AI response cannot change a closed and reopened form', async () => {
  const first=deferred(), second=deferred();
  global.fetch=jest.fn().mockImplementationOnce(() => first.promise).mockImplementationOnce(() => second.promise);
  render(<Harness />);
  fireEvent.click(screen.getByTitle('Сгенерировать текст по ГОСТ через ИИ'));
  fireEvent.click(screen.getByRole('button',{name:'Отмена'}));
  fireEvent.click(screen.getByRole('button',{name:'Добавить',exact:true}));
  fireEvent.click(screen.getByTitle('Сгенерировать текст по ГОСТ через ИИ'));
  await act(async () => second.resolve({ok:true,json:async () => ({instructionText:'Current suggestion'})}));
  await act(async () => first.resolve({ok:true,json:async () => ({instructionText:'Obsolete suggestion'})}));
  expect(screen.getByDisplayValue('Current suggestion')).toBeInTheDocument();
});

test('successful save preserves edits made while it was pending', async () => {
  const pending=deferred();render(<Harness save={() => pending.promise} />);
  fireEvent.click(screen.getByRole('button',{name:'Сохранить'}));
  fireEvent.change(screen.getByPlaceholderText('Текст инструктажа (можно сгенерировать ИИ →)'),{target:{value:'New unsaved text'}});
  await act(async () => pending.resolve({id:4,companyId:2,projectId:11}));
  expect(screen.getByDisplayValue('New unsaved text')).toBeInTheDocument();
  expect(screen.getByRole('button',{name:'Сохранить'})).toBeEnabled();
});

test('successful action uses only the confirmed record and preserves newer list rows', async () => {
  const saved={id:5,companyId:2,projectId:11,projectName:project.name,instructionType:'Первичный',participants:[]};
  global.fetch=jest.fn(async () => ({ok:true,json:async () => saved}));
  let rows=[{id:10,companyId:2,projectId:11}];
  const actions=createProjectOperationActions({API:'/api',user:{name:'Test'},setTbJournal:update => { rows=update(rows); }});
  const result=await actions.saveTbEntry({...draft,project:project.name,projectId:11,companyId:2});
  expect(result.id).toBe(5);expect(rows.map(row => row.id)).toEqual([10,5]);
});

test.each([false,true])('save refusal notification respects the opening session (switched=%s)', async switched => {
  const pending=deferred();global.fetch=jest.fn(() => pending.promise);
  const alert=jest.spyOn(window,'alert').mockImplementation(() => {});
  const actions=createProjectOperationActions({API:'/api',user:{name:'Test'},setTbJournal:jest.fn()});
  const view=render(<Harness save={actions.saveTbEntry} />);
  fireEvent.click(screen.getByRole('button',{name:'Сохранить'}));
  if (switched) view.rerender(<Harness save={actions.saveTbEntry} selected={{id:22,companyId:2,name:'Other'}} />);
  await act(async () => pending.resolve({ok:false,status:403,json:async () => ({detail:'Denied'})}));
  if (switched) expect(alert).not.toHaveBeenCalled();
  else expect(alert).toHaveBeenCalledWith(expect.stringContaining('Denied'));
  expect(screen.getByDisplayValue('Manual draft')).toBeInTheDocument();
});
