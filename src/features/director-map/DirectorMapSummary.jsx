import React from 'react';
import { AlertTriangle, CheckCircle2, ClipboardList, Wallet } from 'lucide-react';
import { formatMoneyShort } from './directorMapRules';

const metrics = [
  { id: 'plannedProgress', label: 'План по календарю', tone: 'warning', suffix: '%', sub: 'расчетный план' },
  { id: 'factProgress', label: 'Факт по ЖПР', tone: 'info', suffix: '%', sub: 'подтвержденные объемы' },
  { id: 'redSignals', label: 'Критичные сигналы', tone: 'danger', suffix: '', sub: 'сначала смотреть' },
  { id: 'reviewItems', label: 'На проверке', tone: 'warning', suffix: '', sub: 'связи и документы' },
  { id: 'moneyFact', label: 'Оплачено факт', tone: 'success', suffix: '', sub: 'только project_payments' },
  { id: 'moneyObligations', label: 'Обязательства', tone: 'info', suffix: '', sub: 'счета и поставки' },
];

const iconByMetric = {
  plannedProgress: ClipboardList,
  factProgress: CheckCircle2,
  redSignals: AlertTriangle,
  reviewItems: AlertTriangle,
  moneyFact: Wallet,
  moneyObligations: Wallet,
};

function formatMetricValue(metric, summary) {
  const value = summary?.[metric.id] ?? 0;
  if (metric.id === 'moneyFact' || metric.id === 'moneyObligations') return formatMoneyShort(value);
  return `${value}${metric.suffix}`;
}

export default function DirectorMapSummary({ summary }) {
  return (
    <section className="dm-summary" aria-label="Сводка карты руководителя">
      {metrics.map(metric => {
        const Icon = iconByMetric[metric.id] || ClipboardList;
        return (
          <div key={metric.id} className={`dm-metric dm-tone-${metric.tone}`}>
            <div className="dm-metric-top">
              <p>{metric.label}</p>
              <Icon size={17} strokeWidth={2.2} aria-hidden="true" />
            </div>
            <strong>{formatMetricValue(metric, summary)}</strong>
            <span>{metric.sub}</span>
          </div>
        );
      })}
    </section>
  );
}
