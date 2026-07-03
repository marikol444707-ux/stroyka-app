import React from 'react';
import { MasterCabinetPage } from '../app/lazyComponents';

export default function AppMasterCabinetRoute({ actions = {}, constants = {}, data = {}, pageFallback = null, ui = {} }) {
  return (
    <React.Suspense fallback={pageFallback}>
      <MasterCabinetPage
        {...ui}
        {...constants}
        {...data}
        {...actions}
      />
    </React.Suspense>
  );
}
