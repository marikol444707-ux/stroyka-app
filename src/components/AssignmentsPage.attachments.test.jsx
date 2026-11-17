import React from 'react';
import {cleanup, fireEvent, render, screen, waitFor} from '@testing-library/react';

import AssignmentsPage from './AssignmentsPage';

const currentReport = {
  id: 101, text: 'Устранение замечаний завершено', authorName: 'Мастер',
  createdAt: '2026-11-08T12:00:00Z',
  attachments: [
    {id: 8, url: '/tenant-files/8/content', type: 'photo', name: 'finished.jpg'},
    {id: 9, url: '/tenant-files/9/content', type: 'file', name: 'report.pdf'},
  ],
};
const earlierReport = {
  id: 100, text: 'Первичный осмотр помещения', authorName: 'Мастер',
  createdAt: '2026-11-07T10:00:00Z',
  attachments: [{id: 7, url: '/tenant-files/7/content', type: 'photo', name: 'inspection.jpg'}],
};
// These are loaded server report records, not a local upload draft.
const task = {
  id: 41, title: 'Проверить устранение замечаний', projectName: 'Объект',
  status: 'На проверке', assignedRole: 'мастер', assignedTo: 'Мастер',
  reportsCount: 2, reports: [currentReport, earlierReport], latestReport: currentReport,
};

function renderLoadedTasks(tasks = [task]) {
  const page = aiTasks => <AssignmentsPage API="/api" C={{}} aiTasks={aiTasks}
    user={{id: 11, name: 'Мастер', role: 'мастер'}}/>;
  const rendered = render(page([]));
  rendered.rerender(page(tasks));
  return rendered;
}

describe('AssignmentsPage saved report attachments', () => {
  const originalFetch = global.fetch;
  const originalCreateObjectURL = URL.createObjectURL;
  const originalRevokeObjectURL = URL.revokeObjectURL;
  let files;

  beforeEach(() => {
    files = [
      {url: '/api/tenant-files/8/content', objectUrl: 'blob:finished', blob: new Blob(['finished'], {type: 'image/jpeg'})},
      {url: '/api/tenant-files/9/content', objectUrl: 'blob:report', blob: new Blob(['report'], {type: 'application/pdf'})},
      {url: '/api/tenant-files/7/content', objectUrl: 'blob:inspection', blob: new Blob(['inspection'], {type: 'image/jpeg'})},
    ];
    global.fetch = jest.fn(async url => {
      const file = files.find(item => item.url === url);
      if (!file) throw new Error('Unexpected file URL: ' + url);
      return {ok: true, blob: async () => file.blob};
    });
    URL.createObjectURL = jest.fn(blob => files.find(file => file.blob === blob).objectUrl);
    URL.revokeObjectURL = jest.fn();
  });

  afterEach(() => {
    // Protected previews revoke URLs during unmount, before restoring the URL API.
    cleanup();
    global.fetch = originalFetch;
    if (originalCreateObjectURL) URL.createObjectURL = originalCreateObjectURL;
    else delete URL.createObjectURL;
    if (originalRevokeObjectURL) URL.revokeObjectURL = originalRevokeObjectURL;
    else delete URL.revokeObjectURL;
  });

  it('shows the loaded latest report photo and PDF using authenticated blob URLs', async () => {
    const {container, unmount} = renderLoadedTasks();
    expect(screen.getByText(currentReport.text)).toBeVisible();
    const image = await screen.findByRole('img', {name: 'finished.jpg'});
    expect(image).toHaveAttribute('src', 'blob:finished');
    expect(screen.getByRole('link', {name: 'finished.jpg'})).toHaveAttribute('href', 'blob:finished');
    const pdf = await screen.findByRole('link', {name: 'report.pdf'});
    expect(pdf).toHaveAttribute('href', 'blob:report');
    expect(pdf).toHaveAttribute('download', 'report.pdf');
    for (const id of [8, 9]) {
      expect(global.fetch).toHaveBeenCalledWith(`/api/tenant-files/${id}/content`,
        expect.objectContaining({credentials: 'include', cache: 'no-store'}));
    }
    expect(container.querySelector('[href*="tenant-files"], [src*="tenant-files"]')).toBeNull();
    unmount();
    expect(URL.revokeObjectURL).toHaveBeenCalledWith('blob:finished');
    expect(URL.revokeObjectURL).toHaveBeenCalledWith('blob:report');
  });

  it('keeps earlier report text and its photo accessible in report history', async () => {
    renderLoadedTasks();
    const historyToggle = screen.queryByText(/История отчетов/);
    if (historyToggle) fireEvent.click(historyToggle);
    expect(await screen.findByText(earlierReport.text)).toBeVisible();
    const image = await screen.findByRole('img', {name: 'inspection.jpg'});
    expect(image).toHaveAttribute('src', 'blob:inspection');
    expect(screen.getByRole('link', {name: 'inspection.jpg'})).toHaveAttribute('href', 'blob:inspection');
    expect(global.fetch).toHaveBeenCalledWith('/api/tenant-files/7/content',
      expect.objectContaining({credentials: 'include', cache: 'no-store'}));
  });

  it('shows a failed protected download without exposing a raw file link or image', async () => {
    global.fetch.mockResolvedValue({ok: false, status: 403});
    const {container} = renderLoadedTasks([{
      ...task, reportsCount: 1, reports: [currentReport], latestReport: currentReport,
    }]);
    await waitFor(() => expect(screen.getAllByRole('alert').map(alert => alert.textContent)).toEqual(
      expect.arrayContaining(['Файл недоступен: finished.jpg', 'Файл недоступен: report.pdf']),
    ));
    expect(global.fetch).toHaveBeenCalledWith('/api/tenant-files/8/content',
      expect.objectContaining({credentials: 'include', cache: 'no-store'}));
    expect(global.fetch).toHaveBeenCalledWith('/api/tenant-files/9/content',
      expect.objectContaining({credentials: 'include', cache: 'no-store'}));
    expect(screen.queryByRole('link', {name: 'finished.jpg'})).not.toBeInTheDocument();
    expect(screen.queryByRole('link', {name: 'report.pdf'})).not.toBeInTheDocument();
    expect(container.querySelector('[href*="tenant-files"], [src*="tenant-files"]')).toBeNull();
    expect(URL.createObjectURL).not.toHaveBeenCalled();
  });
});
