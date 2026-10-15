// This chooses a screen and avoids unrelated loads; the server still checks every read.
export const isSupportWorkspaceUser = user => user?.role === 'platform_support'
  && process.env.REACT_APP_PARTICIPANT_SUPPORT_ACCESS_ENABLED === '1';
