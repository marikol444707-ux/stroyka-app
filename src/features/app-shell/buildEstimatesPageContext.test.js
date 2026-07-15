import { buildEstimatesPageContext } from './buildEstimatesPageContext';

describe('buildEstimatesPageContext', () => {
  it('forwards authenticated user and selected company context to the estimates screen', () => {
    const user = { id: 7, role: 'директор' };
    const companyContext = {
      mode: 'company',
      selectedCompany: { companyId: 1, role: 'директор' },
    };

    const result = buildEstimatesPageContext({ user, companyContext });

    expect(result.user).toBe(user);
    expect(result.companyContext).toBe(companyContext);
  });
});
