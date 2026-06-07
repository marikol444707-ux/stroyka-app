import React from 'react';
import AnalyticsProjectExpensesPanel from './AnalyticsProjectExpensesPanel';
import AnalyticsStatsGrid from './AnalyticsStatsGrid';
import AnalyticsWorkJournalActivityPanel from './AnalyticsWorkJournalActivityPanel';

export default function AnalyticsPage({
  C,
  badge,
  card,
  contracts,
  expByCategory,
  projects,
  staff,
  suppliers,
  tbl,
  tblC,
  tblH,
  workJournal,
}) {
  return (
    <div>
      <h3 style={{color:C.text,marginBottom:'20px',fontSize:'16px',fontWeight:'700'}}>Аналитика</h3>
      <AnalyticsStatsGrid C={C} card={card} projects={projects} staff={staff} suppliers={suppliers} contracts={contracts}/>
      <AnalyticsProjectExpensesPanel C={C} card={card} projects={projects} expByCategory={expByCategory}/>
      <AnalyticsWorkJournalActivityPanel C={C} card={card} tbl={tbl} tblH={tblH} tblC={tblC} badge={badge} workJournal={workJournal}/>
    </div>
  );
}

