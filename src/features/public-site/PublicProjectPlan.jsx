import React from 'react';
import plans from './projectPlanPresentation.json';
import './PublicProjectPlan.css';

export const getPlanPresentation = (src) => plans[src];

export default function PublicProjectPlan({ plan, title, compact = false }) {
  if (compact) return <img className="public-project-media-image is-plan" src={plan.diagram} alt={`Схема зонирования: ${title}`} loading="lazy" />;
  return (
    <figure className="public-plan-sheet">
      <figcaption className="public-plan-heading">
        <span>Эскизная планировка</span>
        <strong>{plan.heading}</strong>
        <p>{title}</p>
      </figcaption>
      <div className="public-plan-body">
        <img className="public-plan-drawing" src={plan.diagram} alt={`Схема с номерами помещений: ${title}`} />
        <div className="public-plan-legend">
          <h4>Экспликация помещений</h4>
          <ol>{plan.rooms.map(room => <li key={room.number}><b aria-hidden="true">{room.number}</b><span>{room.name}</span></li>)}</ol>
        </div>
      </div>
      <div className="public-plan-footer">
        <p>Схема показывает идею зонирования. Размеры, проёмы и конструктив уточняются при проектировании.</p>
        <a href={plan.sheet} target="_blank" rel="noopener noreferrer">Открыть крупно ↗</a>
      </div>
    </figure>
  );
}
