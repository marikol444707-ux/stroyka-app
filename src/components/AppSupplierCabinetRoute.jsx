import React from 'react';
import SupplierCabinetPage from '../features/supply/SupplierCabinetPage';
import useSupplierInbox from '../features/supply/useSupplierInbox';

export default function AppSupplierCabinetRoute({ actions = {}, constants = {}, data = {}, ui = {} }) {
  const inbox = useSupplierInbox(ui.API, data.user);
  const refreshData = async () => {
    await Promise.allSettled([inbox.reload(), actions.refreshData?.()]);
  };
  return (
    <SupplierCabinetPage
      {...ui}
      {...constants}
      {...data}
      {...actions}
      supplierOffers={inbox.offers}
      supplyRequests={inbox.requests}
      inboxState={inbox}
      refreshData={refreshData}
    />
  );
}
