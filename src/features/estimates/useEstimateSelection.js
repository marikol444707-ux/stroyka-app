import { useCallback, useEffect, useLayoutEffect, useRef, useState } from 'react';

// Track transitions synchronously: React can batch closing and reopening the same ID.
export function useEstimateSelection(companyContextKey = '') {
  const [selectedEstimate, setValue] = useState(null);
  const [estimateSaveState, setEstimateSaveState] = useState({status: 'idle', error: ''});
  const saveRequestRef = useRef(0);
  const listSaveRequestsRef = useRef(new Map());
  const dirtyRef = useRef(false);
  const estimateSelectionRef = useRef({estimate: null, id: null, session: 0, revision: 0});
  const setSelectedEstimate = useCallback((update, {fromServer = false} = {}) => {
    const current = estimateSelectionRef.current;
    const estimate = typeof update === 'function' ? update(current.estimate) : update;
    if (estimate === current.estimate) return;
    const id = estimate?.id ?? null;
    estimateSelectionRef.current = {
      estimate, id,
      session: current.session + (id !== current.id ? 1 : 0),
      revision: current.revision + 1,
    };
    dirtyRef.current = id === current.id && !fromServer;
    setValue(estimate);
    setEstimateSaveState(previous => id !== current.id || fromServer
      ? {status: 'idle', error: ''}
      : previous.status === 'conflict' ? previous : {status: 'dirty', error: ''});
  }, []);
  const beginEstimateSave = useCallback((estimate, {fullSnapshot = true, source = 'editor'} = {}) => {
    const listOnly = source === 'list' && estimateSelectionRef.current.id !== estimate.id;
    const token = captureEstimateSelection(estimateSelectionRef, listOnly ? estimateSelectionRef.current.id : estimate.id);
    let request = -1;
    if (isEstimateSelectionCurrent(estimateSelectionRef, token)) {
      if (listOnly) {
        request = (listSaveRequestsRef.current.get(estimate.id) || 0) + 1;
        listSaveRequestsRef.current.set(estimate.id, request);
      } else request = ++saveRequestRef.current;
    }
    const isCurrent = () => request === (listOnly ? listSaveRequestsRef.current.get(estimate.id) : saveRequestRef.current)
      && isEstimateSelectionCurrent(estimateSelectionRef, token);
    if (isCurrent() && !listOnly) setEstimateSaveState({status: 'saving', error: ''});
    return {
      isCurrent,
      finish(result) {
        if (!isCurrent()) return false;
        if (listOnly) return true;
        if (result.status === 'saved') {
          // Acknowledge only this unchanged draft; never replace newer edits.
          const next = {...(result.estimate || estimateSelectionRef.current.estimate), revision: result.revision};
          estimateSelectionRef.current = {...estimateSelectionRef.current, estimate: next, revision: estimateSelectionRef.current.revision + 1};
          // Invalidate older loads too, while keeping this save's review token current.
          token.revision = estimateSelectionRef.current.revision;
          if (fullSnapshot) dirtyRef.current = false;
          setValue(next);
        }
        setEstimateSaveState({status: result.status === 'saved' && dirtyRef.current ? 'dirty' : result.status, error: result.error || ''});
        return true;
      },
    };
  }, []);
  const markEstimateDeleted = useCallback(id => {
    if (estimateSelectionRef.current.id !== id) return;
    // Deletion is a new server fact, not an acknowledgement of this draft.
    // Invalidate outstanding responses without replacing or closing local data.
    saveRequestRef.current += 1;
    estimateSelectionRef.current = {...estimateSelectionRef.current, revision: estimateSelectionRef.current.revision + 1};
    dirtyRef.current = true;
    setEstimateSaveState({status: 'conflict', error: 'Смета удалена на сервере. Локальный черновик сохранён в открытом редакторе. Скопируйте его отдельно перед закрытием; сохранить в удалённую смету нельзя.'});
  }, []);
  useLayoutEffect(() => {
    const current = estimateSelectionRef.current;
    estimateSelectionRef.current = {estimate: null, id: null, session: current.session + 1, revision: current.revision + 1};
    saveRequestRef.current += 1;
    dirtyRef.current = false;
    setValue(null);
    setEstimateSaveState({status: 'idle', error: ''});
  }, [companyContextKey]);
  useEffect(() => () => {
    estimateSelectionRef.current = {...estimateSelectionRef.current, session: estimateSelectionRef.current.session + 1};
  }, []);
  return {selectedEstimate, setSelectedEstimate, estimateSelectionRef, estimateSaveState, beginEstimateSave, markEstimateDeleted, hasUnsavedEstimateChanges: dirtyRef.current};
}

export function captureEstimateSelection(ref, id) {
  return ref ? {id, session: ref.current.session, revision: ref.current.revision} : null;
}

export function isEstimateSelectionCurrent(ref, token) {
  if (!ref) return true; // Legacy action callers without an editor selection.
  return Boolean(token && ref.current.id === token.id
    && ref.current.session === token.session && ref.current.revision === token.revision);
}
