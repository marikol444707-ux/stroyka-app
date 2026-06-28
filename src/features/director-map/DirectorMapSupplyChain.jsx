import React from 'react';
import { ArrowRight, Package, ShieldCheck, Truck, Warehouse } from 'lucide-react';
import { getSupplyStepTone } from './directorMapRules';

const stepIcons = {
  need: Package,
  request: Package,
  offer: Package,
  invoice: ShieldCheck,
  shipment: Truck,
  acceptance: Truck,
  primary_document: ShieldCheck,
  quality_control: ShieldCheck,
  warehouse: Warehouse,
  work_journal: ShieldCheck,
};

export default function DirectorMapSupplyChain({ item }) {
  const chain = item?.supplyChain || [];
  if (!chain.length) return null;

  return (
    <section className="dm-section dm-supply-chain">
      <div className="dm-section-head">
        <div>
          <h2>Цепочка поставки по выбранному этапу</h2>
          <p>{item.workPackage} · {item.zone}</p>
        </div>
        <span className="dm-pill dm-tone-danger">поставка в фокусе</span>
      </div>

      <div className="dm-chain-grid">
        {chain.map((step, index) => {
          const Icon = stepIcons[step.step] || Package;
          const tone = getSupplyStepTone(step.status);
          return (
            <div key={step.id} className={`dm-chain-step dm-tone-${tone}`}>
              <div className="dm-chain-step-top">
                <Icon size={16} aria-hidden="true" />
                <span>{String(index + 1).padStart(2, '0')} · {step.title}</span>
              </div>
              <b>{step.value}</b>
              {step.description ? <p>{step.description}</p> : null}
              {index < chain.length - 1 ? <ArrowRight className="dm-chain-arrow" size={16} aria-hidden="true" /> : null}
            </div>
          );
        })}
      </div>
    </section>
  );
}
