import React from 'react';
import {render,screen} from '@testing-library/react';
import ProjectScheduleSummaryPanel from './ProjectScheduleSummaryPanel';
test('unknown completion does not create a false calendar lag warning',()=>{
 render(<ProjectScheduleSummaryPanel C={{}} card={{}} project={{name:'Объект'}} progress={0} planDone={{plan:0,done:0}}
 stages={[{projectName:'Объект',name:'Этап',startDate:'2000-01-01',endDate:'2000-02-01'}]}/>);
 expect(screen.getByText(/Прогресс не указан/)).toBeInTheDocument();
 expect(screen.queryByText(/отставание от календаря/)).not.toBeInTheDocument();
});
