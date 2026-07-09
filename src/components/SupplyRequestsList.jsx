import React from 'react';
import {
  SupplyRequestCard,
  SupplyRequestsEmpty,
  SupplyRequestsProjectHeader,
} from './supply/SupplyRequestsListParts';
import { supplyRequestListGroup } from '../utils/supplyUtils';

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
    const group = supplyRequestListGroup(request);
    if (!byProject.has(group.key)) byProject.set(group.key, { group, requests: [] });
    byProject.get(group.key).requests.push(request);
  });

  return (
    <>
      {Array.from(byProject.values()).map(({ group, requests }) => {
        const collapsed = supplyCollapsedProjects[group.key];
        const visibleRequests = isMobile ? requests.slice(0, 20) : requests;
        return (
          <div key={group.key} style={{ marginBottom: '12px' }}>
            <SupplyRequestsProjectHeader
              C={C}
              card={card}
              badge={badge}
              project={group.project}
              groupLabel={group.label}
              groupBucket={group.bucket}
              requests={requests}
              collapsed={collapsed}
              onToggle={() => setSupplyCollapsedProjects({
                ...supplyCollapsedProjects,
                [group.key]: !collapsed,
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
