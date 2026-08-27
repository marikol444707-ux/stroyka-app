import React from 'react';

import {
  ACCOUNTING_EXCEPTION_REASON_CONTRACTS,
  accountingExceptionReasonLabel,
} from './accountingExceptionChecks';

const SUBJECT_LABELS = {
  brigade_payment: 'Выплата бригаде',
  supplier_invoice: 'Накладная поставщика',
  warehouse_invoice: 'Складская накладная',
  accountable_expense: 'Подотчётный расход',
  accountable_payment: 'Подотчётный аванс',
  expense_report: 'Авансовый отчёт',
  salary_payment: 'Выплата зарплаты',
  own_expense: 'Личная трата',
  manual_expense: 'Ручная трата',
};

const MONEY_LABELS = {
  storedAmount: 'Сохранённая сумма',
  linkedAmount: 'Связанная сумма',
  invoiceAmount: 'Сумма документа',
  paidAmount: 'Оплачено',
  storedSpentAmount: 'Сохранено как потраченное',
  childAmountSum: 'Сумма расходов',
  advanceAmount: 'Сумма аванса',
  issuedAmount: 'Выдано',
  spentAmount: 'Потрачено',
  storedBalance: 'Сохранённый остаток',
  expectedBalance: 'Расчётный остаток',
};

const documentCountLabel = count => {
  const tail = count % 100;
  const last = count % 10;
  if (tail >= 11 && tail <= 19) return `${count} документов`;
  if (last === 1) return `${count} документ`;
  if (last >= 2 && last <= 4) return `${count} документа`;
  return `${count} документов`;
};

export default function AccountingExceptionFindingGroups({ groups, palette, isMobile }) {
  return (
    <div role="list" style={{ display: 'grid', gridTemplateColumns: isMobile ? '1fr' : 'repeat(2, minmax(0, 1fr))', gap: '10px' }}>
      {groups.map(group => {
        const contract = ACCOUNTING_EXCEPTION_REASON_CONTRACTS[group.reasonCode];
        return (
          <article key={group.reasonCode} role="listitem" style={{ border: `1px solid ${palette.border}`, borderRadius: '10px', padding: '12px', minWidth: 0 }}>
            <h3 style={{ margin: 0, color: palette.text, fontSize: '14px' }}>{accountingExceptionReasonLabel(group.reasonCode)}</h3>
            <p style={{ margin: '7px 0 0', color: palette.textSec, fontSize: '12px' }}>
              <b>Что сделать:</b> {contract.nextStep}
            </p>
            <p style={{ margin: '7px 0 0', color: palette.warning, fontSize: '12px', fontWeight: 800 }}>
              {documentCountLabel(group.count)}
            </p>
            <details style={{ marginTop: '8px' }}>
              <summary style={{ color: palette.textSec, fontSize: '12px', fontWeight: 700, cursor: 'pointer' }}>
                Показать документы ({group.count})
              </summary>
              <div style={{ display: 'grid', gap: '8px', marginTop: '9px' }}>
                {group.findings.map((finding, index) => (
                  <div key={`${finding.subjectKind}:${finding.subjectId}:${finding.relatedId || 0}:${index}`} style={{ borderTop: `1px solid ${palette.border}`, paddingTop: '8px' }}>
                    <p style={{ margin: 0, color: palette.textSec, fontSize: '12px' }}>
                      {SUBJECT_LABELS[finding.subjectKind]} №{finding.subjectId}
                      {finding.projectId !== null ? ` · Объект №${finding.projectId}` : ''}
                      {contract.ids.map(field => ` · Связанный документ №${finding[field]}`).join('')}
                    </p>
                    {contract.money.length > 0 && (
                      <ul style={{ margin: '6px 0 0', paddingLeft: '18px', color: palette.textSec, fontSize: '12px' }}>
                        {contract.money.map(field => <li key={field}>{MONEY_LABELS[field]}: {finding[field]} ₽</li>)}
                      </ul>
                    )}
                  </div>
                ))}
              </div>
            </details>
          </article>
        );
      })}
    </div>
  );
}
