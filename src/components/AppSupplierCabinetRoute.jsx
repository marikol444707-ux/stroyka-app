import React from 'react';
import SupplierCabinetPage from '../features/supply/SupplierCabinetPage';
import useSupplierTeam from '../features/supply/useSupplierTeam';
import useSupplierInbox from '../features/supply/useSupplierInbox';

export default function AppSupplierCabinetRoute({ actions = {}, constants = {}, data = {}, ui = {} }) {
  const teamContext = useSupplierTeam(ui.API, data.user);
  const inbox = useSupplierInbox(ui.API, data.user, true);
  const refreshData = async () => {
    await Promise.allSettled([inbox.reload(), teamContext.reload(), actions.refreshData?.()]);
  };
  return (
    <SupplierCabinetPage
      {...ui}
      {...constants}
      {...data}
      {...actions}
      supplierOffers={inbox.offers}
      supplyRequests={inbox.requests}
      supplyDeliveries={inbox.deliveries}
      supplierInvoices={inbox.invoices}
      inboxState={inbox}
      teamContext={teamContext}
      refreshData={refreshData}
    />
  );
}
