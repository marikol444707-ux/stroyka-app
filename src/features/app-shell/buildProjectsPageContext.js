import PhotoAttachmentField from '../../components/PhotoAttachmentField';
import ProjectBrigadeCalculationTab from '../../components/ProjectBrigadeCalculationTab';
import ProjectCardHeader from '../../components/ProjectCardHeader';
import ProjectDocumentsRegistryPanel from '../../components/ProjectDocumentsRegistryPanel';
import ProjectEconomyPanel from '../../components/ProjectEconomyPanel';
import ProjectFinancePanel from '../../components/ProjectFinancePanel';
import ProjectHiddenWorksActsPanel from '../../components/ProjectHiddenWorksActsPanel';
import { ProjectLaunchPanel } from '../project-launch';
import ProjectLettersPanel from '../../components/ProjectLettersPanel';
import ProjectMaterialsControlPanel from '../../components/ProjectMaterialsControlPanel';
import ProjectMaterialsStockPanel from '../../components/ProjectMaterialsStockPanel';
import ProjectMaterialsTransferPanel from '../../components/ProjectMaterialsTransferPanel';
import ProjectObjectLinksPanel from '../../components/ProjectObjectLinksPanel';
import ProjectPrescriptionsPanel from '../../components/ProjectPrescriptionsPanel';
import ProjectSafetyJournalPanel from '../../components/ProjectSafetyJournalPanel';
import ProjectScheduleSummaryPanel from '../../components/ProjectScheduleSummaryPanel';
import ProjectTabsNav from '../../components/ProjectTabsNav';
import ProjectWorkJournalPanel from '../../components/ProjectWorkJournalPanel';
import { ProjectDirectorMapPanel } from '../director-map';
import {
  DOOR_PURPOSES,
  DOOR_TYPES,
  ESTIMATE_CHANGE_TYPES,
  ESTIMATE_CHANGE_VISIBLE_STATUSES,
  ESTIMATE_PACKAGES,
  EXPENSE_CATEGORIES,
  REVEAL_MATERIALS,
  STAGE_STATUSES,
  SURFACES,
  UNITS,
  WINDOW_TYPES,
} from '../../constants/catalogs';
import {
  PROJECT_MEASUREMENT_DOC_TYPES,
  PROJECT_MEASUREMENT_SOURCE_TYPES,
  PROJECT_MEASUREMENT_STATUSES,
} from '../../constants/estimateConstants';
import { DIRECTOR_MAP_FEATURE_ENABLED } from '../../constants/appConfig';
import { CHECKLIST_TEMPLATES, TB_INSTRUCTIONS, TB_TYPES_GOST } from '../../constants/documentTemplates';
import { createProjectMeasurementActions } from '../project-measurements/projectMeasurementActions';
import {
  Archive,
  Bot,
  Calculator,
  Check,
  ChevronDown,
  ChevronUp,
  Edit2,
  Eye,
  FileText,
  FolderKanban,
  GitBranch,
  MapPin,
  Package,
  Plus,
  QrCode,
  ScrollText,
  Search,
  Trash2,
  Upload,
  X,
} from 'lucide-react';

export function buildProjectsPageContext({
  API,
  actions = {},
  appMainState = {},
  businessRuntime = {},
  coreRuntime = {},
  documentActions = {},
  layout = {},
  paymentUiState = {},
  projectCrudActions = {},
  projectOperationActions = {},
  selectors = {},
  ui = {},
  warehouseActions = {},
  workJournalActions = {},
}) {
  return {
    ...ui,
    ...appMainState,
    ...paymentUiState,
    ...coreRuntime,
    ...businessRuntime,
    ...documentActions,
    ...projectCrudActions,
    ...warehouseActions,
    ...workJournalActions,
    ...projectOperationActions,
    ...actions,
    ...selectors,
    API,
    Archive,
    Bot,
    CHECKLIST_TEMPLATES,
    Calculator,
    Check,
    ChevronDown,
    ChevronUp,
    DIRECTOR_MAP_FEATURE_ENABLED,
    DOOR_PURPOSES,
    DOOR_TYPES,
    EMPTY_ESTIMATE_CHANGE: selectors.EMPTY_ESTIMATE_CHANGE,
    ESTIMATE_CHANGE_TYPES,
    ESTIMATE_CHANGE_VISIBLE_STATUSES,
    ESTIMATE_PACKAGES,
    EXPENSE_CATEGORIES,
    Edit2,
    Eye,
    FileText,
    FolderKanban,
    GitBranch,
    MapPin,
    PROJECT_MEASUREMENT_DOC_TYPES,
    PROJECT_MEASUREMENT_SOURCE_TYPES,
    PROJECT_MEASUREMENT_STATUSES,
    Package,
    PhotoAttachmentField,
    Plus,
    ProjectBrigadeCalculationTab,
    ProjectCardHeader,
    ProjectDirectorMapPanel,
    ProjectDocumentsRegistryPanel,
    ProjectEconomyPanel,
    ProjectFinancePanel,
    ProjectHiddenWorksActsPanel,
    ProjectLaunchPanel,
    ProjectLettersPanel,
    ProjectMaterialsControlPanel,
    ProjectMaterialsStockPanel,
    ProjectMaterialsTransferPanel,
    ProjectObjectLinksPanel,
    ProjectPrescriptionsPanel,
    ProjectSafetyJournalPanel,
    ProjectScheduleSummaryPanel,
    ProjectTabsNav,
    ProjectWorkJournalPanel,
    QrCode,
    REVEAL_MATERIALS,
    STAGE_STATUSES,
    SURFACES,
    ScrollText,
    Search,
    TB_INSTRUCTIONS,
    TB_TYPES_GOST,
    Trash2,
    UNITS,
    Upload,
    WINDOW_TYPES,
    X,
    createProjectMeasurementActions,
    isMobile: layout.isMobile,
  };
}
