import React from 'react';
import { C as DEFAULT_C } from '../constants/uiTheme';
import DashboardPage from '../features/dashboard/DashboardPage';
import EstimatesPage from '../features/estimates/EstimatesPage';
import ProjectsPage from '../features/projects/ProjectsPage';
import WorkAssignmentModal from '../features/work-assignment';
import AppActionModals from './AppActionModals';
import AppBackofficePages from './AppBackofficePages';
import AppDirectoryPages from './AppDirectoryPages';
import AppHeaderBar from './AppHeaderBar';
import AppOperationsPages from './AppOperationsPages';
import AppOverlayLayer from './AppOverlayLayer';
import AppProjectEditModals from './AppProjectEditModals';
import AppSecondaryPages from './AppSecondaryPages';
import AppSidebar from './AppSidebar';
import AppWorkflowModals from './AppWorkflowModals';
import ImagePreviewModal from './ImagePreviewModal';
import MobileBottomNav from './MobileBottomNav';
import PreviewModal from './PreviewModal';
import ProjectSitePublicationPage from './ProjectSitePublicationPage';

export default function AppAuthenticatedShell({
  activePage,
  appActionModalsProps,
  appBackofficePagesProps,
  appDirectoryPagesProps,
  appOperationsPagesProps,
  appProjectEditModalsProps,
  appSecondaryPagesProps,
  appWorkflowModalsProps,
  C,
  canOpenProjects,
  dashboardProps,
  estimatesPageContext,
  headerProps,
  isMobile,
  mobileBottomNavProps,
  overlayProps,
  pageFallback,
  photoPreviewProps,
  previewProps,
  projectSiteProps,
  projectsPageContext,
  sidebarProps,
  workAssignmentProps,
}) {
  const theme = C || DEFAULT_C;
  const safePreviewProps = previewProps || {};
  return (
    <div style={{display:'flex',height:'100vh',backgroundColor:theme.bg,position:'relative',overflow:'hidden'}}>
      {safePreviewProps.content && (
        <PreviewModal
          content={safePreviewProps.content}
          title={safePreviewProps.title}
          onClose={safePreviewProps.onClose}
          onPrint={safePreviewProps.onPrint}
        />
      )}
      <ImagePreviewModal {...(photoPreviewProps || {})} />

      <React.Suspense fallback={null}>
        <AppProjectEditModals {...(appProjectEditModalsProps || {})} />
        <AppActionModals {...(appActionModalsProps || {})} />
      </React.Suspense>

      <AppSidebar {...(sidebarProps || {})} />

      <div style={{flex:1,display:'flex',flexDirection:'column',overflow:'hidden',width:'100%',minWidth:0,marginLeft:isMobile?0:'240px'}}>
        <AppHeaderBar {...(headerProps || {})} />
        <div style={{flex:1,overflowY:'auto',backgroundColor:activePage==='dashboard'?'#0b1120':theme.bg,padding:activePage==='dashboard'?'0':'24px'}}>
          <React.Suspense fallback={pageFallback}>
            {activePage === 'dashboard' && <DashboardPage {...(dashboardProps || {})} />}
            {activePage === 'projects' && canOpenProjects && <ProjectsPage ctx={projectsPageContext} />}
            {activePage === 'site' && <ProjectSitePublicationPage {...(projectSiteProps || {})} />}
            <AppDirectoryPages {...(appDirectoryPagesProps || {})} />
            <AppOperationsPages {...(appOperationsPagesProps || {})} />
            <AppBackofficePages {...(appBackofficePagesProps || {})} />
            {activePage === 'estimates' && <EstimatesPage ctx={estimatesPageContext} />}
            <AppSecondaryPages {...(appSecondaryPagesProps || {})} />
          </React.Suspense>
        </div>
      </div>

      <MobileBottomNav {...(mobileBottomNavProps || {})} />
      <WorkAssignmentModal {...(workAssignmentProps || {})} />
      <AppWorkflowModals {...(appWorkflowModalsProps || {})} />
      <AppOverlayLayer {...(overlayProps || {})} />
    </div>
  );
}
