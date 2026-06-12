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
                {requests.map(request => (
                  <SupplyRequestCard
                    key={request.id}
                    {...props}
                    request={request}
                  />
                ))}
              </div>
            )}
          </div>
        );
      })}
    </>
  );
}

export default SupplyRequestsList;
