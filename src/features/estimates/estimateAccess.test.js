import {
  canManageEstimateForContext,
  estimateRoleForContext,
} from './estimateAccess';

describe('estimate company access', () => {
  it('uses the role from the selected company for a multi-company account', () => {
    const user = { role: 'client_account_owner' };
    const companyContext = {
      mode: 'company',
      selectedCompany: { companyId: 1, role: 'директор' },
    };

    expect(estimateRoleForContext(user, companyContext)).toBe('директор');
    expect(canManageEstimateForContext(user, companyContext)).toBe(true);
  });

  it('does not inherit leadership from another company', () => {
    const user = { role: 'директор' };
    const companyContext = {
      mode: 'company',
      selectedCompany: { companyId: 2, role: 'сметчик' },
    };

    expect(estimateRoleForContext(user, companyContext)).toBe('сметчик');
    expect(canManageEstimateForContext(user, companyContext)).toBe(false);
  });

  it('keeps mutation controls hidden in all-companies mode', () => {
    expect(canManageEstimateForContext(
      { role: 'директор' },
      { mode: 'all_companies', selectedCompany: null },
    )).toBe(false);
  });

  it('falls back to the authenticated role before company context loads', () => {
    expect(estimateRoleForContext({ role: 'зам_директора' }, null)).toBe('зам_директора');
    expect(canManageEstimateForContext({ role: 'зам_директора' }, null)).toBe(true);
  });
});
