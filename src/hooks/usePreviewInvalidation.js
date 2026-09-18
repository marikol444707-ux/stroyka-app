import { useLayoutEffect } from 'react';
import { journalScopeKey } from './useJournalMutation';
import { qualityJournalScopeKey } from '../utils/qualityJournalScope';
import { QUALITY_JOURNAL_MUTATED } from '../utils/qualityJournalEvents';

export const PREVIEW_INVALIDATED = 'stroyka:preview-invalidated';

// Conservative by design: cached HTML has no per-document ownership metadata.
// Main calls this once; all preview hosts share setPreviewContent.
export function usePreviewInvalidation({ user, companyContext = {}, qualityJournalLoadState, setPreviewContent }) {
  const scope = JSON.stringify([user?.id, user?.email, user?.role,
    companyContext.mode, companyContext.selectedCompanyId,
    qualityJournalScopeKey(companyContext, user)]);
  const loads = JSON.stringify(qualityJournalLoadState || {});

  useLayoutEffect(() => {
    const invalidate = () => {
      setPreviewContent(null);
      window.dispatchEvent(new Event(PREVIEW_INVALIDATED));
    };
    invalidate();
    let storedScope = journalScopeKey();
    const storageChanged = () => {
      const next = journalScopeKey();
      if (next !== storedScope) {
        storedScope = next;
        invalidate();
      }
    };
    window.addEventListener(QUALITY_JOURNAL_MUTATED, invalidate);
    window.addEventListener('storage', storageChanged);
    return () => {
      window.removeEventListener(QUALITY_JOURNAL_MUTATED, invalidate);
      window.removeEventListener('storage', storageChanged);
    };
  }, [scope, loads, setPreviewContent]);
}

export default usePreviewInvalidation;
