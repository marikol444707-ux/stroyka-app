import React from 'react';
import { Banknote } from 'lucide-react';
import { formatCompactMoney } from './publicSiteContent';

const formatStageCount = (count) => `${count} ${count === 4 ? 'этапа' : 'этапов'}`;

export const PublicProjectPaymentSchedule = ({ packageLabel, stages = [] }) => {
  if (!stages.length) return null;

  return (
    <section
      className="public-project-payment-schedule"
      aria-label="Примерный график этапов и платежей"
    >
      <div className="public-project-payment-head">
        <span className="public-project-payment-icon" aria-hidden="true"><Banknote size={18} /></span>
        <div>
          <h4>Примерный график этапов и платежей</h4>
          <p>{packageLabel} · {formatStageCount(stages.length)}</p>
        </div>
      </div>
      <ol className="public-project-payment-list">
        {stages.map((stage, index) => (
          <li key={stage.id}>
            <span className="public-project-payment-number">{index + 1}</span>
            <strong>{stage.title}</strong>
            <b>{stage.percent}%</b>
            <small>{formatCompactMoney(stage.min)} - {formatCompactMoney(stage.max)}</small>
          </li>
        ))}
      </ol>
      <p className="public-project-payment-note">
        Это предварительный ориентир, он не является договорным графиком. Точные этапы и суммы фиксируются после проверки проекта, участка и материалов.
      </p>
    </section>
  );
};
