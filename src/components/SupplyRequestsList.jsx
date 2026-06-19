import React from 'react';
import {
  SupplyRequestCard,
  SupplyRequestsEmpty,
  SupplyRequestsProjectHeader,
} from './supply/SupplyRequestsListParts';

function SupplyRequestsList(props) {
  const {
    C,
    card,
    badge,
    list,
    isMobile = false,
    supplyCollapsedProjects,
    setSupplyCollapsedProjects,
  } = props;

  if ((list || []).length === 0) {
    return <SupplyRequestsEmpty C={C} card={card} />;
  }

  const byProject = new Map();
  (list || []).forEach(request => {
    const key = request.project || '— Без объекта —';
    if (!byProject.has(key)) byProject.set(key, []);
    byProject.get(key).push(request);
  });

  return (
    <>
      {Array.from(byProject.entries()).map(([project, requests]) => {
        const collapsed = supplyCollapsedProjects[project];
        const visibleRequests = isMobile ? requests.slice(0, 20) : requests;
        return (
          <div key={project} style={{ marginBottom: '12px' }}>
            <SupplyRequestsProjectHeader
              C={C}
              card={card}
              badge={badge}
              project={project}
              requests={requests}
              collapsed={collapsed}
              onToggle={() => setSupplyCollapsedProjects({
                ...supplyCollapsedProjects,
                [project]: !collapsed,
              })}
            />
            {!collapsed && (
              <div style={{ paddingLeft: '12px', borderLeft: '2px solid ' + C.border, marginLeft: '8px' }}>
                {visibleRequests.map(request => (
                  <SupplyRequestCard
                    key={request.id}
                    {...props}
                    request={request}
                  />
                ))}
                {visibleRequests.length < requests.length && (
                  <div style={{padding:'10px 12px',color:C.textMuted,fontSize:'11px',textAlign:'center'}}>
                    Показаны последние {visibleRequests.length} из {requests.length}. Используйте поиск или откройте на компьютере для полного списка.
                  </div>
                )}
              </div>
            )}
          </div>
        );
      })}
    </>
  );
}

export default SupplyRequestsList;
