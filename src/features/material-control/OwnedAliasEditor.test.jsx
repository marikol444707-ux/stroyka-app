import React from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import OwnedAliasEditor from './OwnedAliasEditor';

const project = {id: 7, companyId: 2, name: 'Школа'};
const companyContext = {mode: 'company', selectedCompanyId: 2, selectedCompany: {companyId: 2, companyName: 'Компания А', role: 'директор', source: 'membership', membershipId: 5, active: true, companyActive: true}};
const row = {id: 'cma:1', companyId: 2, projectId: 7, aliasName: 'Марка', canonicalName: 'Цемент', canonicalUnit: 'шт', createdById: 9, createdAt: '2026-09-16T10:00:00Z', active: true};
const response = (data, status = 200) => ({ok: status < 400, status, json: async () => data});
const page = items => response({items, limit: 25, offset: 0});

test('create carries exact scope and null precondition', async () => {
  global.fetch = jest.fn().mockResolvedValueOnce(page([])).mockResolvedValueOnce(response(row, 201)).mockResolvedValueOnce(page([row]));
  const invalidateOwnedAliases = jest.fn();
  const reloadOwnedAliases = jest.fn();
  render(<OwnedAliasEditor API="/api" project={project} companyContext={companyContext} invalidateOwnedAliases={invalidateOwnedAliases} reloadOwnedAliases={reloadOwnedAliases}/>);
  await screen.findByText('В этой области соответствий пока нет.');
  fireEvent.change(screen.getByLabelText('Название поставщика'), {target: {value: 'Марка'}});
  fireEvent.change(screen.getByLabelText('Название в смете'), {target: {value: 'Цемент'}});
  fireEvent.click(screen.getByText('Сохранить соответствие'));
  await screen.findByText('Изменения сохранены');
  expect(JSON.parse(global.fetch.mock.calls[1][1].body)).toMatchObject({companyId: 2, projectId: 7, expectedAliasId: null});
  await waitFor(() => expect(reloadOwnedAliases).toHaveBeenCalledTimes(1));
  expect(invalidateOwnedAliases).toHaveBeenCalledTimes(1);
});

test('conflict preserves draft and never retries a mutation automatically', async () => {
  global.fetch = jest.fn().mockResolvedValueOnce(page([row])).mockResolvedValueOnce(response({detail: 'Conflict'}, 409));
  render(<OwnedAliasEditor API="/api" project={project} companyContext={companyContext}/>);
  fireEvent.click(await screen.findByText('Изменить'));
  fireEvent.change(screen.getByLabelText('Название в смете'), {target: {value: 'Новый цемент'}});
  fireEvent.click(screen.getByText('Сохранить соответствие'));
  await screen.findByText(/Черновик сохранён/);
  expect(screen.getByLabelText('Название в смете').value).toBe('Новый цемент');
  expect(JSON.parse(global.fetch.mock.calls[1][1].body).expectedAliasId).toBe('cma:1');
  expect(global.fetch).toHaveBeenCalledTimes(2);
});

test('deactivation requires confirmation and preserves branded ID', async () => {
  global.fetch = jest.fn().mockResolvedValueOnce(page([row])).mockResolvedValueOnce(response({ok: true})).mockResolvedValueOnce(page([]));
  render(<OwnedAliasEditor API="/api" project={project} companyContext={companyContext}/>);
  fireEvent.click(await screen.findByText('Отключить'));
  expect(global.fetch).toHaveBeenCalledTimes(1);
  fireEvent.click(screen.getByText('Подтвердить отключение'));
  await screen.findByText('Изменения сохранены');
  expect(global.fetch.mock.calls[1][0]).toContain('/cma%3A1?companyId=2');
});

test('aggregate view never loads or mutates the directory', () => {
  global.fetch = jest.fn();
  render(<OwnedAliasEditor API="/api" project={project} companyContext={{mode: 'all_companies'}}/>);
  expect(screen.getByText(/Выберите компанию объекта/)).toBeTruthy();
  expect(global.fetch).not.toHaveBeenCalled();
});

test.each([{loading: true}, {error: 'Нет связи'}, {selectedCompany: {...companyContext.selectedCompany, active: false}}])('unverified membership clears visible aliases and draft: %o', async change => {
  global.fetch = jest.fn().mockResolvedValue(page([row]));
  const {rerender} = render(<OwnedAliasEditor API="/api" project={project} companyContext={companyContext}/>);
  fireEvent.click(await screen.findByText('Изменить'));
  rerender(<OwnedAliasEditor API="/api" project={project} companyContext={{...companyContext, ...change}}/>);
  expect(screen.queryByText('→ Цемент')).toBeNull();
  expect(screen.queryByText('Сохранить соответствие')).toBeNull();
  expect(global.fetch).toHaveBeenCalledTimes(1);
});

test('read-only role gets list without mutation controls', async () => {
  global.fetch = jest.fn().mockResolvedValue(page([row]));
  render(<OwnedAliasEditor API="/api" project={project} companyContext={{...companyContext, selectedCompany: {...companyContext.selectedCompany, role: 'бухгалтер'}}}/>);
  await screen.findByText('→ Цемент');
  expect(screen.queryByText('Изменить')).toBeNull();
  expect(screen.queryByText('Сохранить соответствие')).toBeNull();
});

test('switching scope discards a late previous-scope response', async () => {
  let finish;
  global.fetch = jest.fn().mockImplementationOnce(() => new Promise(resolve => {finish = resolve;})).mockResolvedValueOnce(page([]));
  render(<OwnedAliasEditor API="/api" project={project} companyContext={companyContext}/>);
  fireEvent.change(screen.getByLabelText('Область действия'), {target: {value: 'company'}});
  await screen.findByText('В этой области соответствий пока нет.');
  finish(page([row]));
  await waitFor(() => expect(screen.queryByText('→ Цемент')).toBeNull());
  expect(global.fetch.mock.calls[1][0]).not.toContain('projectId');
});
