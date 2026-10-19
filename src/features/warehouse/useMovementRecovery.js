import {useEffect, useRef, useState} from 'react';
import {matchesMovementScope, movementRequest, movementScope} from './movementRecovery';

export default function useMovementRecovery({API, user, companyContext, enabled = true}) {
  const scope = enabled ? movementScope(user, companyContext) : null;
  const key = scope?.key || '';
  const latest = useRef({key, generation: 0});
  if (latest.current.key !== key) latest.current = {key, generation: latest.current.generation + 1};
  const generation = latest.current.generation;
  const sequence = useRef(0);
  const mounted = useRef(true);
  useEffect(() => { mounted.current = true; return () => { mounted.current = false; sequence.current += 1; }; }, []);
  const [state, setState] = useState({generation: -1, loading: true, drafts: [], error: ''});
  const current = () => mounted.current && latest.current.key === key && latest.current.generation === generation;
  const refresh = async () => {
    // Must guard BEFORE sequence increment or state mutation: a captured old
    // callback must not invalidate the new company's in-flight request.
    if (!current()) return;
    const request = ++sequence.current;
    if (!scope) { setState({generation, loading: false, drafts: [], error: 'Выберите компанию'}); return; }
    setState(previous => ({...previous, generation, loading: true, error: '', drafts: previous.generation === generation ? previous.drafts : []}));
    try {
      const result = await movementRequest(API, `/warehouse-movement-drafts?expectedActorUserId=${scope.actorUserId}`, scope);
      if (!matchesMovementScope(result, scope) || !Array.isArray(result.drafts)
        || result.drafts.some(draft => !matchesMovementScope(draft, scope))) throw new Error('Ответ относится к другой компании или пользователю');
      if (current() && request === sequence.current) setState({generation, loading: false, drafts: result.drafts.filter(draft => !draft.complete), error: ''});
    } catch (error) {
      if (current() && request === sequence.current) setState(previous => ({...previous, generation, loading: false, error: error.message}));
    }
  };
  const cancel = async draft => {
    if (!current() || !scope || !matchesMovementScope(draft, scope)) return;
    const request = ++sequence.current;
    setState(previous => ({...previous, loading: true, error: ''}));
    try {
      const result = await movementRequest(API, `/warehouse-movement-drafts/${encodeURIComponent(draft.draftId)}/cancel`, scope, {expectedActorUserId: scope.actorUserId});
      if (!matchesMovementScope(result, scope)) throw new Error('Ответ относится к другой компании или пользователю');
      if (current() && request === sequence.current) await refresh();
    } catch (error) {
      if (current() && request === sequence.current) setState(previous => ({...previous, loading: false, error: error.message}));
    }
  };
  useEffect(() => {
    refresh();
    // Scope generation fences all requests; no payload or credentials persisted in browser.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key]);
  const visible = state.generation === generation ? state : {loading: true, drafts: [], error: ''};
  return {...visible, key, blocked: !scope || visible.loading || Boolean(visible.error) || visible.drafts.length > 0, refresh, cancel};
}
