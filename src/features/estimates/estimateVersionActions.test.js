import { createEstimateVersionActions } from './estimateVersionActions';


const deferred = () => {
  let resolve;
  const promise = new Promise((resolvePromise) => {
    resolve = resolvePromise;
  });
  return { promise, resolve };
};

describe('estimateVersionActions', () => {
  test('ignores version history that arrives after the estimate context changed', async () => {
    const pending = deferred();
    const requestRef = { current: 0 };
    const alertFn = jest.fn();
    const setEstimateVersions = jest.fn();
    const setSelectedVersionsToCompare = jest.fn();
    const setShowVersionHistory = jest.fn();
    const actions = createEstimateVersionActions({
      API: '',
      alertFn,
      estimateVersionRequestRef: requestRef,
      fetchFn: jest.fn(() => pending.promise),
      readApiResult: jest.fn(async (response) => response.data),
      selectedEstimate: { id: 7 },
      setEstimateVersions,
      setSelectedVersionsToCompare,
      setShowVersionHistory,
    });

    const opening = actions.handleOpenSelectedEstimateHistory();
    requestRef.current += 1;
    pending.resolve({ data: [{ id: 31, versionLabel: '2.0' }] });

    expect(await opening).toBe(false);
    expect(setEstimateVersions).toHaveBeenCalledTimes(1);
    expect(setEstimateVersions).toHaveBeenCalledWith([]);
    expect(setSelectedVersionsToCompare).toHaveBeenCalledWith([]);
    expect(setShowVersionHistory).not.toHaveBeenCalled();
    expect(alertFn).not.toHaveBeenCalled();
  });

  test('keeps the existing error message for a current request failure', async () => {
    const alertFn = jest.fn();
    const actions = createEstimateVersionActions({
      API: '',
      alertFn,
      estimateVersionRequestRef: { current: 0 },
      fetchFn: jest.fn(async () => { throw new Error('network'); }),
      readApiResult: jest.fn(),
      selectedEstimate: { id: 7 },
      setEstimateVersions: jest.fn(),
      setSelectedVersionsToCompare: jest.fn(),
      setShowVersionHistory: jest.fn(),
    });

    expect(await actions.handleOpenSelectedEstimateHistory()).toBe(false);
    expect(alertFn).toHaveBeenCalledWith('Не удалось загрузить историю');
  });
});
