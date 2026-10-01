import { applyCompanyContextSelection } from './CompanyContextSwitcher';

describe('company context switching', () => {
  test('persists the new company before forcing a clean app reload', () => {
    const calls = [];
    const setSelectedCompanyId = jest.fn((value) => calls.push(['select', value]));
    const reload = jest.fn(() => calls.push(['reload']));

    const changed = applyCompanyContextSelection({
      currentValue: '4',
      nextValue: '7',
      setSelectedCompanyId,
      reload,
    });

    expect(changed).toBe(true);
    expect(calls).toEqual([['select', '7'], ['reload']]);
  });

  test('does not reload when selection did not change', () => {
    const setSelectedCompanyId = jest.fn();
    const reload = jest.fn();

    const changed = applyCompanyContextSelection({
      currentValue: '4',
      nextValue: '4',
      setSelectedCompanyId,
      reload,
    });

    expect(changed).toBe(false);
    expect(setSelectedCompanyId).not.toHaveBeenCalled();
    expect(reload).not.toHaveBeenCalled();
  });
});
