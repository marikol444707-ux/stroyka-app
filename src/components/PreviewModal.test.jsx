import React from 'react';
import { act, fireEvent, render, screen } from '@testing-library/react';
import PreviewModal from './PreviewModal';
import { notifyQualityJournalMutation } from '../utils/qualityJournalEvents';
import usePreviewInvalidation from '../hooks/usePreviewInvalidation';
import { buildPerformerContractHtml } from '../utils/contractTemplates';

afterEach(() => localStorage.clear());

test('contract work table has its own accessible scroll area and retains full print data', () => {
  const content = buildPerformerContractHtml({
    contract: { id: 23, project: 'Школа' },
    items: [{ name: 'Монтаж кабеля в защитных трубах', quantity: 2000, unit: 'м', priceBrigade: 29 }],
  });
  const print = jest.fn();
  const close = jest.fn();
  render(<PreviewModal content={content} title="Договор" onPrint={print} onClose={close} />);
  const region = screen.getByRole('region', { name: 'Перечень работ договора' });
  expect(region).toHaveAttribute('tabindex', '0');
  expect(screen.getByRole('cell', { name: 'Монтаж кабеля в защитных трубах' })).toBeInTheDocument();
  expect(screen.getByRole('cell', { name: /^58\s000$/ })).toBeInTheDocument();
  fireEvent.click(screen.getByRole('button', { name: 'Распечатать' }));
  expect(print).toHaveBeenCalledWith(expect.stringContaining('Монтаж кабеля в защитных трубах'));
  fireEvent.click(screen.getByRole('button', { name: 'Закрыть' }));
  expect(close).toHaveBeenCalledTimes(1);
});

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
