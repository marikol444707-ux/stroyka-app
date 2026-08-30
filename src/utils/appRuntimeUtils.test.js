import {doPrint} from './appRuntimeUtils';

describe('doPrint HTML boundary', () => {
  beforeEach(() => {
    jest.useFakeTimers();
  });

  afterEach(() => {
    jest.clearAllTimers();
    jest.useRealTimers();
    document.querySelectorAll('iframe').forEach(frame => frame.remove());
  });

  test('removes executable markup before writing the print document', () => {
    doPrint('<p>Документ</p><img src="x" onerror="window.__xss=1"><script>window.__xss=2</script>');

    const frame = document.querySelector('iframe');
    expect(frame).not.toBeNull();
    expect(frame.contentDocument.body).toHaveTextContent('Документ');
    expect(frame.contentDocument.querySelector('script')).toBeNull();
    expect(frame.contentDocument.querySelector('img')).not.toHaveAttribute('onerror');
  });
});
