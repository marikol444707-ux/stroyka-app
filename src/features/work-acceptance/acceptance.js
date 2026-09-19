export const workAcceptanceEnabled = () => process.env.REACT_APP_WORK_ACCEPTANCE_ENABLED === '1';
export const usesWorkAcceptance = work => workAcceptanceEnabled() && work?.materialAccountingVersion === 2;
