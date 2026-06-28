import React, { useMemo, useState } from 'react';
import {
  AlertTriangle,
  CircleDot,
  FileText,
  Package,
  Search,
  Settings,
  ShieldCheck,
  Wallet,
} from 'lucide-react';
import { adaptDirectorMapContract } from './directorMapAdapter';
import directorMapMockContract from './directorMapMockData';
import DirectorMapLinksTable from './DirectorMapLinksTable';
import DirectorMapStageCard from './DirectorMapStageCard';
import DirectorMapSummary from './DirectorMapSummary';
import DirectorMapSupplyChain from './DirectorMapSupplyChain';
import DirectorMapTimeline from './DirectorMapTimeline';
import { DIRECTOR_MAP_FILTERS, filterDirectorMapItems } from './directorMapRules';
import './directorMap.css';

const filterIcons = {
  all: CircleDot,
  red: AlertTriangle,
  material: Package,
  supply: Package,
  documents: FileText,
  money: Wallet,
  review: Search,
};

export default function ProjectDirectorMapPanel({
  contract = directorMapMockContract,
  onAction,
  onOpenStages,
  sandbox = true,
}) {
  const viewModel = useMemo(() => adaptDirectorMapContract(contract), [contract]);
  const [activeFilter, setActiveFilter] = useState('all');
  const [selectedId, setSelectedId] = useState(viewModel.items[1]?.id || viewModel.items[0]?.id || '');

  const visibleItems = filterDirectorMapItems(viewModel.items, activeFilter);
  const selectedItem = viewModel.items.find(item => item.id === selectedId)
    || visibleItems[0]
    || viewModel.items[0];

  const handleFilter = filterId => {
    const nextItems = filterDirectorMapItems(viewModel.items, filterId);
    setActiveFilter(filterId);
    if (nextItems.length && !nextItems.some(item => item.id === selectedId)) {
      setSelectedId(nextItems[0].id);
    }
  };

  return (
    <div className="dm-panel" data-mode={viewModel.mode}>
      <header className="dm-topbar">
        <div>
          <p className="dm-eyebrow">{sandbox ? 'Песочница без привязки' : 'Карта объекта'}</p>
          <h1>{viewModel.project.directorViewTitle}</h1>
          <p className="dm-subtitle">
            {viewModel.project.name} · {viewModel.project.status}
          </p>
        </div>
        <div className="dm-filterbar" aria-label="Фильтры карты">
          {typeof onOpenStages === 'function' ? (
            <button
              type="button"
              className="dm-filter-button dm-filter-button-secondary"
              onClick={onOpenStages}
            >
              <Settings size={14} aria-hidden="true" />
              Настроить этапы
            </button>
          ) : null}
          {DIRECTOR_MAP_FILTERS.map(filter => {
            const Icon = filterIcons[filter.id] || ShieldCheck;
            return (
              <button
                key={filter.id}
                type="button"
                className="dm-filter-button"
                aria-pressed={activeFilter === filter.id}
                onClick={() => handleFilter(filter.id)}
              >
                <Icon size={14} aria-hidden="true" />
                {filter.label}
              </button>
            );
          })}
        </div>
      </header>

      <DirectorMapSummary summary={viewModel.summary} />

      <div className="dm-main-grid">
        <DirectorMapTimeline
          items={viewModel.items}
          activeFilter={activeFilter}
          selectedId={selectedItem?.id}
          onSelect={setSelectedId}
        />
        <DirectorMapStageCard item={selectedItem} onAction={onAction} />
      </div>

      <DirectorMapSupplyChain item={selectedItem} />
      <DirectorMapLinksTable items={viewModel.items} />

      <footer className="dm-guardrail">
        <ShieldCheck size={16} aria-hidden="true" />
        <span>
          Только просмотр: модуль не проводит склад, ЖПР, оплату, документы и сроки.
        </span>
      </footer>
    </div>
  );
}
