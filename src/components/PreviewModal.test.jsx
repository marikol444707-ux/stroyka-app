import React from 'react';
import { act, fireEvent, render, screen } from '@testing-library/react';
import PreviewModal from './PreviewModal';
import { notifyQualityJournalMutation } from '../utils/qualityJournalEvents';
import usePreviewInvalidation from '../hooks/usePreviewInvalidation';

afterEach(() => localStorage.clear());

test.each(['mutation', 'scope', 'storage'])('cached HTML cannot be printed after %s changes', change => {
  localStorage.setItem('user', JSON.stringify({ id: 1 }));
  localStorage.setItem('stroyka.companyContext.v1.1', JSON.stringify({ mode: 'company', companyId: 2 }));
  const print = jest.fn();
  const close = jest.fn();
  render(<PreviewModal content="<p>Old private HTML</p>" title="Journal" onPrint={print} onClose={close} />);
  if (change === 'mutation') act(() => notifyQualityJournalMutation());
  else {
    localStorage.setItem('stroyka.companyContext.v1.1', JSON.stringify({ mode: 'company', companyId: 3 }));
    if (change === 'storage') act(() => window.dispatchEvent(new Event('storage')));
  }
  fireEvent.click(screen.getByRole('button', { name: /Распечатать/ }));
  expect(print).not.toHaveBeenCalled();
  expect(close).toHaveBeenCalled();
  expect(screen.queryByText('Old private HTML')).not.toBeInTheDocument();
  expect(screen.getByRole('button', { name: /Распечатать/ })).toBeDisabled();
});

test('failed load invalidates already rendered HTML even if parent close does not unmount immediately', () => {
  const print = jest.fn();
  const clear = jest.fn();
  function Harness({ status }) {
    usePreviewInvalidation({ user: { id: 1 }, companyContext: {}, qualityJournalLoadState: { cables: { status } }, setPreviewContent: clear });
    return <PreviewModal content="<p>Old private HTML</p>" title="Journal" onPrint={print} onClose={clear} />;
  }
  const { rerender } = render(<Harness status="ready" />);
  rerender(<Harness status="error" />);
  fireEvent.click(screen.getByRole('button', { name: /Распечатать/ }));
  expect(print).not.toHaveBeenCalled();
  expect(screen.queryByText('Old private HTML')).not.toBeInTheDocument();
});

describe('PreviewModal HTML boundary', () => {
  test('removes executable markup before previewing or printing', () => {
    const onPrint = jest.fn();
    const {container} = render(
      <PreviewModal
        content={'<p>Безопасный текст</p><img src="x" onerror="window.__xss=1"><script>window.__xss=2</script>'}
        title="Смета"
        onClose={jest.fn()}
        onPrint={onPrint}
      />,
    );

    expect(screen.getByText('Безопасный текст')).toBeInTheDocument();
    // Script nodes have no accessible role; inspect the HTML security boundary.
    // eslint-disable-next-line testing-library/no-container, testing-library/no-node-access
    expect(container.querySelector('script')).toBeNull();
    expect(screen.getByRole('img')).not.toHaveAttribute('onerror');

    fireEvent.click(screen.getByRole('button', {name:/распечатать/i}));
    expect(onPrint).toHaveBeenCalledTimes(1);
    expect(onPrint.mock.calls[0][0]).not.toMatch(/<script|onerror/i);
  });
});
