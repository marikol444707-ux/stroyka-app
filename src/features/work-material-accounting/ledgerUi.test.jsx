import React from 'react';
import { act, fireEvent, render, screen } from '@testing-library/react';
import { useLedger } from './ledgerUi';
import { clearWorkBatch, sendWorkBatch } from './workCommands';
jest.mock('./workCommands', () => ({ workBatchScope: () => ({}), sendWorkBatch: jest.fn(), clearWorkBatch: jest.fn() }));

function Harness({ companyId = 2, path = '/brigade-contracts/1/settlement', onChanged }) {
  const ledger = useLedger({ API: '/api', path, companyContext: { selectedCompanyId: companyId }, user: { id: 7 }, onChanged });
  return <><p>{ledger.error || ledger.data?.label || 'loading'}</p><button onClick={() => ledger.submit('/brigade-payments', {})}>submit</button></>;
}

test.each(['company', 'contract'])('ignores an old %s response after navigation', async change => {
  const pending = [];
  global.fetch = jest.fn(() => new Promise(resolve => pending.push(resolve)));
  const view = render(<Harness />);
  view.rerender(<Harness companyId={change === 'company' ? 3 : 2} path={change === 'contract' ? '/brigade-contracts/2/settlement' : '/brigade-contracts/1/settlement'} />);
  await act(async () => pending[1]({ ok: true, json: async () => ({ label: 'current' }) }));
  await act(async () => pending[0]({ ok: true, json: async () => ({ label: 'old private calculation' }) }));
  expect(screen.getByText('current')).toBeTruthy();
  expect(screen.queryByText('old private calculation')).toBeNull();
});

test('a submission completed after unmount preserves recovery and does not refresh parent state', async () => {
  const onChanged = jest.fn();
  let complete;
  sendWorkBatch.mockImplementation(() => new Promise(resolve => { complete = resolve; }));
  global.fetch = jest.fn(async () => ({ ok: true, json: async () => ({ label: 'current' }) }));
  const view = render(<Harness onChanged={onChanged} />);
  await screen.findByText('current');
  fireEvent.click(screen.getByText('submit'));
  view.unmount();
  await act(async () => complete({ commands: [] }));
  expect(fetch).toHaveBeenCalledTimes(1);
  expect(onChanged).not.toHaveBeenCalled();
  expect(clearWorkBatch).not.toHaveBeenCalled();
});

test('a failed old request cannot replace the current calculation with an error', async () => {
  const pending = [];
  global.fetch = jest.fn(() => new Promise((resolve, reject) => pending.push({ resolve, reject })));
  const view = render(<Harness />);
  view.rerender(<Harness companyId={3} />);
  await act(async () => pending[1].resolve({ ok: true, json: async () => ({ label: 'current' }) }));
  await act(async () => pending[0].reject(new Error('old failure')));
  expect(screen.getByText('current')).toBeTruthy();
  expect(screen.queryByText('old failure')).toBeNull();
});
