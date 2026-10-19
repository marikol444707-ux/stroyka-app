import {useEffect, useRef, useState} from 'react';
import {createWarehouseMovementForm} from './warehouseInitialForms';
import {movementScope} from './movementRecovery';

// Scope identity changes on logout too. Old async callbacks cannot write into a
// new account's form, including logout/login of the same account.
export default function useScopedMovementDraft(user, companyContext) {
  const scope = movementScope(user, companyContext);
  const key = scope?.key || '';
  const latest = useRef({key, generation: 0});
  if (latest.current.key !== key) latest.current = {key, generation: latest.current.generation + 1};
  const generation = latest.current.generation;
  const mounted = useRef(true);
  useEffect(() => { mounted.current = true; return () => { mounted.current = false; }; }, []);
  const [state, setState] = useState(() => ({generation, draft: createWarehouseMovementForm()}));
  const current = () => mounted.current && latest.current.key === key && latest.current.generation === generation;
  const draft = state.generation === generation ? state.draft : createWarehouseMovementForm();
  return {
    newMovement: draft,
    setNewMovement: update => {
      if (!current()) return;
      setState(previous => ({generation, draft: typeof update === 'function'
        ? update(previous.generation === generation ? previous.draft : createWarehouseMovementForm()) : update}));
    },
    movementScope: scope,
    isMovementScopeCurrent: current,
  };
}
