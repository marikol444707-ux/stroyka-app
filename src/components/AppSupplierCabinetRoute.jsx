import React from 'react';
import SupplierCabinetPage from '../features/supply/SupplierCabinetPage';

export default function AppSupplierCabinetRoute({ actions = {}, constants = {}, data = {}, ui = {} }) {
  return (
    <SupplierCabinetPage
      {...ui}
      {...constants}
      {...data}
      {...actions}
    />
  );
}
