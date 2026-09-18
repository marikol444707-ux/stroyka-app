import { act, renderHook } from '@testing-library/react';
import usePreviewInvalidation from './usePreviewInvalidation';
import { notifyQualityJournalMutation } from '../utils/qualityJournalEvents';

const context = { mode: 'company', selectedCompanyId: 2, companies: [{ companyId: 2, role: 'директор' }] };
const ready = { inspections: { status: 'ready', complete: true }, cables: { status: 'ready', complete: true } };

test.each(['company', 'user', 'loading', 'failure', 'membership'])('clears cached HTML on %s invalidation', change => {
  const clear = jest.fn();
  const props = { user: { id: 1 }, companyContext: context, qualityJournalLoadState: ready, setPreviewContent: clear };
  const { rerender } = renderHook(value => usePreviewInvalidation(value), { initialProps: props });
  clear.mockClear();
  const next = { ...props };
  if (change === 'company') next.companyContext = { ...context, selectedCompanyId: 3 };
  if (change === 'user') next.user = { id: 2 };
  if (change === 'membership') next.companyContext = { ...context, companies: [] };
  if (change === 'loading' || change === 'failure') next.qualityJournalLoadState = { ...ready, cables: { status: change === 'failure' ? 'error' : 'loading', complete: false } };
  rerender(next);
  expect(clear).toHaveBeenCalledWith(null);
});

test('mutation clears synchronously; identical state does not repeatedly clear; unmount removes listener', () => {
  const clear = jest.fn();
  const props = { user: { id: 1 }, companyContext: context, qualityJournalLoadState: ready, setPreviewContent: clear };
  const { rerender, unmount } = renderHook(value => usePreviewInvalidation(value), { initialProps: props });
  clear.mockClear();
  rerender({ ...props, qualityJournalLoadState: { ...ready } });
  expect(clear).not.toHaveBeenCalled();
  act(() => notifyQualityJournalMutation());
  expect(clear).toHaveBeenCalledWith(null);
  clear.mockClear();
  unmount();
  act(() => notifyQualityJournalMutation());
  expect(clear).not.toHaveBeenCalled();
});
