import React from 'react';
import {render,screen} from '@testing-library/react';
import DirectorMapSummary from './DirectorMapSummary';
test('unknown progress does not display numeric zero as confirmed journal fact',()=>{
 render(<DirectorMapSummary summary={{factProgress:0,progressSource:'Прогресс не указан'}}/>);
 expect(screen.getByText('Прогресс').closest('.dm-metric')).toHaveTextContent('—');
 expect(screen.getByText('Прогресс не указан')).toBeInTheDocument();
 expect(screen.queryByText('Факт по ЖПР')).not.toBeInTheDocument();
});
test('stored card zero is labelled without claiming manual provenance',()=>{
 render(<DirectorMapSummary summary={{factProgress:0,progressSource:'Из карточки объекта'}}/>);
 expect(screen.getByText('Прогресс').closest('.dm-metric')).toHaveTextContent('0%');
 expect(screen.getByText('Из карточки объекта')).toBeInTheDocument();
});

test('contract and adapter preserve unknown source and suppress invented calendar lag',()=>{
 const {buildDirectorMapContract}=require('./buildDirectorMapContract');
 const {adaptDirectorMapContract}=require('./directorMapAdapter');
 const contract=buildDirectorMapContract({project:{id:1,name:'Объект'},projectProgress:0,planDone:{plan:0,done:0}});
 expect(contract.summary.progressSource).toBe('Прогресс не указан');
 expect(contract.summary.lagPercent).toBeNull();
 const adapted=adaptDirectorMapContract(contract);
 expect(adapted.summary.progressSource).toBe('Прогресс не указан');
 expect(adapted.summary.lagPercent).toBeNull();
});
