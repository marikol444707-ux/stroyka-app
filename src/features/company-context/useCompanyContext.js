import { useCallback, useEffect, useMemo, useState } from 'react';

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
  const [context, setContext] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [selection, setSelection] = useState({ mode: 'company', companyId: null });

  const refresh = useCallback(async () => {
    if (!user) {
      setContext(null);
      setSelection({ mode: 'company', companyId: null });
      setError('');
      setLoading(false);
      return null;
    }
    const controller = new AbortController();
    setLoading(true);
    setError('');
    try {
      const response = await fetch((API || '') + '/users/company-context', { signal: controller.signal });
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const data = await response.json();
      setContext(data);
      setSelection((prev) => {
        const next = normalizeSelection(data, readStoredCompanySelection(user) || prev);
        writeStoredCompanySelection(user, next);
        return next;
      });
      return data;
    } catch (err) {
      if (err?.name !== 'AbortError') {
        setError('Не удалось загрузить компании');
      }
      return null;
    } finally {
      setLoading(false);
    }
  }, [API, user]);

  useEffect(() => {
    refresh();
  }, [refresh]);

  const companies = useMemo(() => (
    Array.isArray(context?.companies) ? context.companies : []
  ), [context]);

  const selectedCompany = useMemo(() => {
    if (selection.mode === 'all_companies') return null;
    const selectedId = asCompanyId(selection.companyId);
    return companies.find((company) => asCompanyId(company.companyId) === selectedId) || null;
  }, [companies, selection]);

  const setSelectedCompanyId = useCallback((value) => {
    if (!context) return;
    const next = value === 'all'
      ? { mode: 'all_companies', companyId: null }
      : { mode: 'company', companyId: asCompanyId(value) };
    const normalized = normalizeSelection(context, next);
    setSelection(normalized);
    writeStoredCompanySelection(user, normalized);
  }, [context, user]);

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
