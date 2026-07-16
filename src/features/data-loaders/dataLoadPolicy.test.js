import {
  ESTIMATES_SUMMARY_PATH,
  createDataLoadPolicy,
} from './dataLoadPolicy';

const flags = (role, overrides = {}) => ({
  role,
  isLeadershipRole: false,
  isFinanceRole: false,
  isWarehouseRole: false,
  isSupplyRole: false,
  canSeeSupplierInvoices: false,
  isInternalRole: true,
  canSeeProjectDocs: false,
  ...overrides,
});

describe('createDataLoadPolicy', () => {
  it.each([
    ['директор', true, true, true],
    ['зам_директора', true, true, true],
    ['бухгалтер', true, true, true],
    ['прораб', true, true, true],
    ['главный_инженер', true, true, true],
    ['сметчик', true, true, false],
    ['кладовщик', true, false, false],
    ['снабженец', true, false, false],
    ['стройконтроль', true, false, false],
    ['мастер', false, false, false],
    ['поставщик', false, false, false],
  ])('preserves people, directory, and accounting access for %s', (role, people, directory, accounting) => {
    const policy = createDataLoadPolicy({ flags: flags(role) });

    expect(policy.canLoadPeopleData).toBe(people);
    expect(policy.canLoadUserDirectory).toBe(directory);
    expect(policy.canLoadAccountingData).toBe(accounting);
  });

  it.each(['мастер', 'субподрядчик', 'бригадир'])('loads full estimates and brigade data for worker role %s', (role) => {
    const policy = createDataLoadPolicy({
      flags: flags(role),
      canAccessEstimates: true,
    });

    expect(policy.isWorkerRole).toBe(true);
    expect(policy.estimatesLoadPath).toBe('/estimates');
    expect(policy.canLoadBrigadeData).toBe(true);
  });

  it('uses summary estimates and system assignments for leadership', () => {
    const policy = createDataLoadPolicy({
      flags: flags('директор', {
        isLeadershipRole: true,
        isFinanceRole: true,
        canSeeProjectDocs: true,
      }),
    });

    expect(policy.canLoadEstimates).toBe(true);
    expect(policy.estimatesLoadPath).toBe(ESTIMATES_SUMMARY_PATH);
    expect(policy.assignmentsPath).toBe('/assignments?include_system=true');
  });

  it('keeps regular assignments and denies estimates when neither access path is available', () => {
    const policy = createDataLoadPolicy({ flags: flags('поставщик') });

    expect(policy.canLoadEstimates).toBe(false);
    expect(policy.assignmentsPath).toBe('/assignments');
  });
});
