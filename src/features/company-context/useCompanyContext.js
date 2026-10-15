import { useCallback, useLayoutEffect, useMemo, useRef, useState } from 'react';
import { isSupportWorkspaceUser } from '../participant-support/workspaceMode';

import {
  asCompanyId,
  readStoredCompanySelection,
  writeStoredCompanySelection,
} from './companyContextStorage';

const normalizeSelection = (context, storedSelection) => {
  const companies = Array.isArray(context?.companies) ? context.companies : [];
  const canUseAll = Boolean(context?.canUseAllCompanies);
  const storedMode = storedSelection?.mode === 'all_companies' ? 'all_companies' : 'company';
  const storedCompanyId = asCompanyId(storedSelection?.companyId);
  if (storedMode === 'all_companies' && canUseAll) {
    return { mode: 'all_companies', companyId: null };
  }
  if (storedCompanyId && companies.some((company) => asCompanyId(company.companyId) === storedCompanyId)) {
    return { mode: 'company', companyId: storedCompanyId };
  }
  const defaultCompanyId = asCompanyId(context?.defaultCompanyId);
  if (defaultCompanyId && companies.some((company) => asCompanyId(company.companyId) === defaultCompanyId)) {
    return { mode: 'company', companyId: defaultCompanyId };
  }
  if (companies.length === 1) {
    return { mode: 'company', companyId: asCompanyId(companies[0].companyId) };
  }
  if (canUseAll) {
    return { mode: 'all_companies', companyId: null };
  }
  return { mode: 'company', companyId: asCompanyId(companies[0]?.companyId) };
};

export function useCompanyContext({ API, user }) {
  const enabled = Boolean(user) && !isSupportWorkspaceUser(user);
  const scope = enabled ? `${API}:${user.id || user.email || user.name}:${user.role}` : '';
  const empty = {context: null, selection: {mode: 'company', companyId: null}, loading: false, error: ''};
  const [snapshot, setSnapshot] = useState(empty);
  const requestRef = useRef({scope: '', sequence: 0, controller: null, selection: empty.selection});
  // Hide previous actor data in the render that precedes effect cleanup.
  const {context, selection, loading, error} = enabled && snapshot.scope === scope ? snapshot : empty;

  const refresh = useCallback(async () => {
    const current = requestRef.current;
    if (!enabled || current.scope !== scope) return null;
    current.controller?.abort();
    const controller = new AbortController();
    current.controller = controller;
    const sequence = ++current.sequence;
    const isCurrent = () => !controller.signal.aborted && current.scope === scope && current.sequence === sequence;
    setSnapshot(prev => ({...prev, scope, loading: true, error: ''}));
    try {
      const response = await fetch((API || '') + '/users/company-context', {signal: controller.signal});
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const data = await response.json();
      if (!isCurrent()) return null;
      const next = normalizeSelection(data, readStoredCompanySelection(user) || current.selection);
      current.selection = next;
      writeStoredCompanySelection(user, next);
      setSnapshot({scope, context: data, selection: next, loading: false, error: ''});
      return data;
    } catch (err) {
      if (isCurrent() && err?.name !== 'AbortError') {
        setSnapshot(prev => ({...prev, loading: false, error: 'Не удалось загрузить компании'}));
      }
      return null;
    } finally {
      if (isCurrent()) setSnapshot(prev => ({...prev, loading: false}));
    }
  }, [API, enabled, scope, user]);

  useLayoutEffect(() => {
    const current = requestRef.current;
    current.scope = scope;
    current.selection = {mode: 'company', companyId: null};
    setSnapshot({scope, context: null, selection: {mode: 'company', companyId: null}, loading: false, error: ''});
    refresh();
    return () => {
      current.sequence++;
      current.scope = '';
      current.controller?.abort();
    };
  }, [scope, refresh]);

  const companies = useMemo(() => (
    Array.isArray(context?.companies) ? context.companies : []
  ), [context]);

  const selectedCompany = useMemo(() => {
    if (selection.mode === 'all_companies') return null;
    const selectedId = asCompanyId(selection.companyId);
    return companies.find((company) => asCompanyId(company.companyId) === selectedId) || null;
  }, [companies, selection]);

  const setSelectedCompanyId = useCallback((value) => {
    if (!context || requestRef.current.scope !== scope) return;
    const next = value === 'all'
      ? { mode: 'all_companies', companyId: null }
      : { mode: 'company', companyId: asCompanyId(value) };
    const normalized = normalizeSelection(context, next);
    requestRef.current.selection = normalized;
    setSnapshot(prev => ({...prev, selection: normalized}));
    writeStoredCompanySelection(user, normalized);
  }, [context, scope, user]);

  return {
    canUseAllCompanies: Boolean(context?.canUseAllCompanies),
    companies,
    context,
    defaultCompanyId: context?.defaultCompanyId || null,
    error,
    loading,
    mode: selection.mode,
    refresh,
    selectedCompany,
    selectedCompanyId: selection.companyId,
    setSelectedCompanyId,
  };
}
