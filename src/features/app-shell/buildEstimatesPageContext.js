import EstimateAddSectionForm from '../../components/EstimateAddSectionForm';
import EstimateCreateActions from '../../components/EstimateCreateActions';
import EstimateCreateFormFields from '../../components/EstimateCreateFormFields';
import EstimateDuplicateWorkSummaryPanel from '../../components/EstimateDuplicateWorkSummaryPanel';
import EstimateExecutionPricingPanel from '../../components/EstimateExecutionPricingPanel';
import EstimateImportValidationBanner from '../../components/EstimateImportValidationBanner';
import EstimateImportView from '../../components/EstimateImportView';
import EstimateSearchResults from '../../components/EstimateSearchResults';
import EstimateSectionsEditor from '../../components/EstimateSectionsEditor';
import EstimateSelectedToolbar from '../../components/EstimateSelectedToolbar';
import EstimateTotalCard from '../../components/EstimateTotalCard';
import EstimatesListToolbar from '../../components/EstimatesListToolbar';
import EstimatesListView from '../../components/EstimatesListView';
import EstimatesTabsNav from '../../components/EstimatesTabsNav';
import MaterialNormCoverageSection from '../../components/MaterialNormCoverageSection';
import MaterialNormFormPanel from '../../components/MaterialNormFormPanel';
import MaterialNormNotice from '../../components/MaterialNormNotice';
import MaterialNormOverridesPanel from '../../components/MaterialNormOverridesPanel';
import MaterialNormSuggestionsPanel from '../../components/MaterialNormSuggestionsPanel';
import MaterialNormsHeader from '../../components/MaterialNormsHeader';
import MaterialNormsListPanel from '../../components/MaterialNormsListPanel';
import { ESTIMATE_PACKAGES } from '../../constants/catalogs';
import { WORK_MATERIAL_NORM_RULES } from '../../utils/materialNormUtils';
import { WorkAssignmentStatusPanel } from '../work-assignment';

export function buildEstimatesPageContext({
  API,
  actions = {},
  appMainState = {},
  businessRuntime = {},
  companyContext = {},
  coreRuntime = {},
  estimatePageActions = {},
  estimateWorkflowState = {},
  layout = {},
  materialNormsState = {},
  selectors = {},
  ui = {},
  user = null,
}) {
  return {
    ...ui,
    ...appMainState,
    ...materialNormsState,
    ...estimateWorkflowState,
    ...coreRuntime,
    ...businessRuntime,
    ...estimatePageActions,
    ...actions,
    ...selectors,
    API,
    companyContext,
    ESTIMATE_PACKAGES,
    EstimateAddSectionForm,
    EstimateCreateActions,
    EstimateCreateFormFields,
    EstimateDuplicateWorkSummaryPanel,
    EstimateExecutionPricingPanel,
    EstimateImportValidationBanner,
    EstimateImportView,
    EstimateSearchResults,
    EstimateSectionsEditor,
    EstimateSelectedToolbar,
    EstimateTotalCard,
    EstimatesListToolbar,
    EstimatesListView,
    EstimatesTabsNav,
    MaterialNormCoverageSection,
    MaterialNormFormPanel,
    MaterialNormNotice,
    MaterialNormOverridesPanel,
    MaterialNormSuggestionsPanel,
    MaterialNormsHeader,
    MaterialNormsListPanel,
    WorkAssignmentStatusPanel,
    WORK_MATERIAL_NORM_RULES,
    isMobile: layout.isMobile,
    user,
  };
}
