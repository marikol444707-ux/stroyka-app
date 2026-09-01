export function describeClientCardConfidence(recognition = {}) {
  const confidence = Number(recognition.confidence);
  if (!Number.isFinite(confidence) || confidence <= 0) {
    return {label: 'Проверьте распознанные поля', level: 'warning'};
  }
  const percent = Math.round(Math.min(1, confidence) * 100);
  return {
    label: `уверенность ${percent}%`,
    level: confidence >= 0.7 ? 'success' : 'warning',
  };
}


export function buildCompanyOnboardingResult(response = {}, draft = {}, origin = '') {
  const onboarding = response.onboarding || {};
  const inviteCode = response.inviteCode || onboarding.code || '';
  return {
    companyId: response.id || onboarding.companyId || null,
    companyName: onboarding.companyName || draft.name || '',
    recipientName: onboarding.recipientName || draft.contactName || '',
    recipientEmail: onboarding.recipientEmail || draft.contactEmail || '',
    roleLabel: onboarding.roleLabel || 'Директор компании',
    expiresAt: onboarding.expiresAt || '',
    inviteCode,
    inviteLink: inviteCode ? `${String(origin).replace(/\/$/, '')}/?invite=${inviteCode}` : '',
  };
}
