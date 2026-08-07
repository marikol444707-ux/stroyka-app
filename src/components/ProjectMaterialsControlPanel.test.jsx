import { fireEvent, render, screen } from '@testing-library/react';
import ProjectMaterialsControlPanel from './ProjectMaterialsControlPanel';

const colors = {
  text: '#111827', textSec: '#475569', textMuted: '#64748b', bg: '#f8fafc', bgWhite: '#fff',
  border: '#cbd5e1', accent: '#ea580c', accentBorder: '#fb923c', accentLight: '#ffedd5',
  success: '#047857', successBorder: '#6ee7b7', successLight: '#ecfdf5',
  info: '#0369a1', infoBorder: '#7dd3fc', infoLight: '#f0f9ff',
  warning: '#a16207', warningBorder: '#facc15', warningLight: '#fefce8', danger: '#b91c1c'
};

const styles = {
  card: {}, tbl: {}, tblH: {}, tblC: {}, btnB: {},
  badge: () => ({})
};

const rows = Array.from({ length: 161 }, (_, index) => ({
  key: `material-${index + 1}`,
  name: `Материал ${index + 1}`,
  unit: 'шт',
  sections: [], workRefs: [], aliases: [], planDetails: [], invalidPlanDetails: [], normDetails: [],
  invoiceDetails: [], supplyDetails: [], movementDetails: [], holders: []
}));

function renderPanel(overrides = {}) {
  const project = {companyId: 7, id: 11, name: 'Тестовый объект'};
  return render(
    <ProjectMaterialsControlPanel
      project={project}
      projectName="Тестовый объект"
      rows={rows}
      C={colors}
      {...styles}
      fmtMeasure={(value, unit) => `${value || 0} ${unit || ''}`.trim()}
      materialControlStatus={() => ({ label: 'Готово', color: colors.success, bg: colors.successLight, border: colors.successBorder })}
      renderMaterialSupplyAction={() => null}
      renderMaterialAliasControls={() => null}
      showPreview={() => {}}
      buildMaterialRequirementContent={() => ''}
      {...overrides}
    />
  );
}

describe('ProjectMaterialsControlPanel pagination', () => {
  test('adds a bounded next page instead of rendering every material at once', () => {
    renderPanel();

    expect(screen.getByText('Показано 80 из 161. Заявку можно создать прямо в колонке «Статус».')).toBeInTheDocument();
    expect(screen.queryByText('Материал 81')).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: 'Показать ещё 80 материалов' }));

    expect(screen.getByText('Показано 160 из 161. Заявку можно создать прямо в колонке «Статус».')).toBeInTheDocument();
    expect(screen.getByText('Материал 160')).toBeInTheDocument();
    expect(screen.queryByText('Материал 161')).not.toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Показать ещё 1 материалов' })).toBeInTheDocument();
  });

  test('passes the stored project owner to material actions', () => {
    const renderMaterialSupplyAction = jest.fn(() => null);

    renderPanel({renderMaterialSupplyAction});

    expect(renderMaterialSupplyAction).toHaveBeenCalledWith(
      {companyId: 7, id: 11, name: 'Тестовый объект'},
      expect.objectContaining({key: 'material-1'}),
    );
  });
});
