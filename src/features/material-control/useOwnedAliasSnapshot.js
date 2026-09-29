import { useCallback, useEffect, useRef } from 'react';
import { immutableStoredProjectOwner } from '../estimates/projectEstimateOwnership';
import { aliasMembershipKey, loadAliasScope, ownedAliasesEnabled } from './ownedAliases';

export async function loadOwnedAliasSnapshot(API, companyId, projects, signal) {
  const owners = (projects || []).map(immutableStoredProjectOwner).filter(owner => owner?.companyId === companyId);
  const scopes = [{companyId, projectId: null}, ...new Map(owners.map(owner => [owner.projectId, owner])).values()];
  const result = new Map();
  const version = {};
  for (const owner of scopes) {
    const rows = await loadAliasScope(API, owner, signal, version);
    for (const row of rows) {
      const previous = result.get(row.id);
      if (previous && JSON.stringify(previous) !== JSON.stringify(row)) throw new Error('Справочник изменился во время загрузки. Повторите загрузку');
      result.set(row.id, row);
    }
    if (result.size > 50000) throw new Error('Слишком большой справочник для полной сверки');
  }
  // Do not merge a partial result into the application after any failed page.
  return [...result.values()];
}

export function useOwnedAliasSnapshot({API, companyContext, projects, userId, setMaterialAliases, setMaterialAliasesError}) {
  const companyId = companyContext?.mode === 'company' ? Number(companyContext.selectedCompanyId) : null;
  const membershipKey = aliasMembershipKey(companyContext);
  const latest = useRef();
  latest.current = {API, companyId, projects, userId, membershipKey, setMaterialAliases, setMaterialAliasesError};
  const pending = useRef({generation: 0, controller: null, writes: 0, ready: null});
  const clearSnapshot = useCallback(() => {
    pending.current.generation += 1;
    pending.current.ready = null;
    pending.current.controller?.abort();
    if (!ownedAliasesEnabled()) return;
    latest.current.setMaterialAliases([]);
    latest.current.setMaterialAliasesError('Загружаем соответствия компании…');
  }, []);
  const invalidateOwnedAliases = useCallback(() => {
    pending.current.writes += 1;
    clearSnapshot();
    let released = false;
    return () => {if (!released) {released = true; pending.current.writes -= 1;}};
  }, [clearSnapshot]);
  const getOwnedAliasSnapshotToken = useCallback(() => {
    const ready = pending.current.ready;
    const current = latest.current;
    return ready && current.membershipKey && !pending.current.writes && ['API', 'companyId', 'projects', 'userId', 'membershipKey'].every(key => ready[key] === current[key])
      ? pending.current.generation : null;
  }, []);
  const reloadOwnedAliases = useCallback(async () => {
    if (!ownedAliasesEnabled()) return;
    clearSnapshot();
    if (pending.current.writes) return;
    const {API, companyId, projects, userId, membershipKey, setMaterialAliases, setMaterialAliasesError} = latest.current;
    const controller = new AbortController();
    pending.current.controller = controller;
    const generation = pending.current.generation;
    if (!companyId || !userId || !membershipKey) {
      setMaterialAliasesError('Для сверки соответствий выберите одну компанию');
      return;
    }
    try {
      const rows = await loadOwnedAliasSnapshot(API, companyId, projects, controller.signal);
      if (generation === pending.current.generation && !pending.current.writes) {
        pending.current.ready = {API, companyId, projects, userId, membershipKey};
        setMaterialAliases(rows); setMaterialAliasesError('');
      }
    } catch (error) {
      if (generation === pending.current.generation) {setMaterialAliases([]); setMaterialAliasesError(error.message);}
    }
  }, [clearSnapshot]);
  useEffect(() => {
    const state = pending.current;
    reloadOwnedAliases();
    return () => {state.generation += 1; state.controller?.abort();};
  }, [API, companyId, projects, userId, membershipKey, reloadOwnedAliases]);
  return {invalidateOwnedAliases, reloadOwnedAliases, getOwnedAliasSnapshotToken};
}
