import React from 'react';

const ACCOUNTING_TAB_LABELS = {
  summary: '📊 Сводка',
  contracts: '🧾 Договоры',
  acts: '📄 Акты',
  performerClosing: '📘 Закрытие',
  payments: '💸 Платежи',
  documents: '🏗 По объектам',
  salary: '👥 Зарплата',
  expenses: '💼 Авансовые',
  audit: '📜 Аудит',
};

export default function AccountingTabsNav({
  accountingTab,
  setAccountingTab,
  setShowForm,
  isLeadership,
  loadAuditLog,
  btnO,
  btnG,
}) {
  const tabs = ['summary', 'contracts', 'acts', 'performerClosing', 'payments', 'documents', 'salary', 'expenses', 'audit']
    .filter(tab => tab !== 'audit' || isLeadership);

  return (
    <div style={{ display: 'flex', gap: '8px', marginBottom: '20px', flexWrap: 'wrap' }}>
      {tabs.map(tab => (
        <button
          key={tab}
          onClick={() => {
            setAccountingTab(tab);
            setShowForm(false);
            if (tab === 'audit') loadAuditLog();
          }}
          style={{ ...(accountingTab === tab ? btnO : btnG), fontSize: '12px', padding: '7px 12px' }}
        >
          {ACCOUNTING_TAB_LABELS[tab]}
        </button>
      ))}
    </div>
  );
}
