import React from 'react';
import { render, screen } from '@testing-library/react';
import AssignmentDailyDraftPreviewPanel from './AssignmentDailyDraftPreviewPanel';

test('fallback styles used when empty/absent style props and dark tokens', () => {
  const C = {
    bg: '#111111',
    bgWhite: '#222222',
    bgGray: '#333333',
    border: '#444444',
    text: '#eeeeee',
    textSec: '#cccccc',
  };

  // mock fetch for versions
  global.fetch = jest.fn(() => Promise.resolve({ ok: true, json: () => Promise.resolve([]) }));
  render(<AssignmentDailyDraftPreviewPanel API="" C={C} btnG={{}} btnO={{}} card={{}} inp={{}} allowedCompanyIds={new Set([1])} selectedCompanyId={1} selectedCompanyRole={'директор'} projects={[{ id: 11, companyId: 1, name: 'P' }]} estimates={[{ id: 22, companyId: 1, projectId: 11, status: 'Активная', smetaType: 'Заказчик', isTemplate: false, workPackage: 'WP', name: 'E' }]} showPreview={() => {}} user={{}} enabled={true} />);

  // 'Сформировать предпросмотр' button should exist and use fallback btnO styles (background or padding)
  const btn = screen.getByRole('button', { name: /Сформировать предпросмотр/i });
  expect(btn).toBeInTheDocument();
  // inline style should include padding from default btnO
  expect(btn).toHaveStyle('padding: 9px 18px');
});
