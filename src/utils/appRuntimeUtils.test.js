import {doPrint, loadStoredUser} from './appRuntimeUtils';

describe('loadStoredUser cookie session boundary', () => {
  afterEach(() => localStorage.clear());

  test('loads the public user without requiring a browser bearer token', () => {
    localStorage.setItem('user', JSON.stringify({id: 7, role: 'директор', email: 'director@example.test'}));

    expect(loadStoredUser()).toEqual(expect.objectContaining({id: 7, role: 'директор'}));
  });

  test('removes a legacy browser bearer token while preserving a valid public user', () => {
    localStorage.setItem('authToken', 'legacy-token');
    localStorage.setItem('user', JSON.stringify({id: 7, role: 'директор', email: 'director@example.test'}));

    expect(loadStoredUser()).toEqual(expect.objectContaining({id: 7, role: 'директор'}));
    expect(localStorage.getItem('authToken')).toBeNull();
  });
});

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
