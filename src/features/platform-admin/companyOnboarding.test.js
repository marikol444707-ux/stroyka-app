import {
  buildCompanyOnboardingResult,
  describeClientCardConfidence,
} from './companyOnboarding';


describe('client company onboarding presentation', () => {
  test('does not present a missing confidence score as zero percent', () => {
    expect(describeClientCardConfidence({source: 'ai', confidence: 0})).toEqual({
      label: 'Проверьте распознанные поля',
      level: 'warning',
    });
  });

  test('shows a real confidence score when the provider returned one', () => {
    expect(describeClientCardConfidence({source: 'ai', confidence: 0.86})).toEqual({
      label: 'уверенность 86%',
      level: 'success',
    });
  });

  test('builds the director handoff from the enriched API response', () => {
    expect(buildCompanyOnboardingResult({
      id: 42,
      inviteCode: 'DIRECT01',
      onboarding: {
        companyName: 'ООО Новая компания',
        recipientName: 'Иван Петров',
        recipientEmail: 'director@example.test',
        roleLabel: 'Директор компании',
        expiresAt: '2026-10-01 12:30:00',
      },
    }, {}, 'https://stroyka26.pro')).toEqual({
      companyId: 42,
      companyName: 'ООО Новая компания',
      recipientName: 'Иван Петров',
      recipientEmail: 'director@example.test',
      roleLabel: 'Директор компании',
      expiresAt: '2026-10-01 12:30:00',
      inviteCode: 'DIRECT01',
      inviteLink: 'https://stroyka26.pro/?invite=DIRECT01',
    });
  });
});
