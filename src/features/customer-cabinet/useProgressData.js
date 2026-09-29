import { useEffect, useState } from 'react';
import { API } from '../../api';
import { customerProjectRecord } from './projectSelection';
import { estimateKind } from '../../utils/estimateUtils';

// The global journal is paginated and estimate rows are summaries. A percentage
// must use complete confirmed volumes and full active estimate details.
export default function useProgressData(project, userId, refreshVersion) {
  const companyId = project?.companyId ?? project?.company_id;
  const projectId = project?.id;
  const projectName = project?.name;
  const scope = `${userId}:${companyId}:${projectId}:${projectName}`;
  const [state, setState] = useState(null);
  useEffect(() => {
    if (!companyId || !projectId) return undefined;
    let current = true;
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), 20000);
    setState({ scope, loading: true, estimates: [], journal: [] });
    const load = async path => {
      const response = await fetch(API + path, { signal: controller.signal,
        headers: { 'X-Company-Id': String(companyId), 'X-Company-Mode': 'company' } });
      if (!response.ok) throw new Error('HTTP ' + response.status);
      const rows = await response.json();
      if (!Array.isArray(rows)) throw new Error('Invalid response');
      return rows;
    };
    Promise.all([load('/estimates'), load('/work-journal?project_name=' + encodeURIComponent(projectName))])
      .then(([estimates, journal]) => {
        const owner = { id: projectId, companyId };
        if (current) setState({ scope, loading: false,
          estimates: estimates.filter(row => customerProjectRecord(row, owner) && row.status === 'Активная' && estimateKind(row) === 'Заказчик'),
          journal: journal.filter(row => customerProjectRecord(row, owner) && row.status === 'Подтверждено') });
      })
      .catch(() => { if (current) setState({ scope, loading: false, error: 'Не удалось загрузить данные прогресса. Обновите страницу.', estimates: [], journal: [] }); })
      .finally(() => clearTimeout(timer));
    return () => { current = false; clearTimeout(timer); controller.abort(); };
  }, [companyId, projectId, projectName, userId, scope, refreshVersion]);
  return state?.scope === scope ? state : { loading: true, estimates: [], journal: [] };
}
