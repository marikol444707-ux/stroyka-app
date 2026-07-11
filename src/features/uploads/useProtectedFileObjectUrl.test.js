import {render, screen, waitFor} from '@testing-library/react';

import useProtectedFileObjectUrl, {isProtectedTenantFileUrl} from './useProtectedFileObjectUrl';


function PreviewHarness({url, fileSrc = value => value}) {
  const {src, loading, error} = useProtectedFileObjectUrl(url, fileSrc);
  return (
    <div>
      <output data-testid="src">{src}</output>
      <output data-testid="loading">{loading ? 'loading' : 'ready'}</output>
      <output data-testid="error">{error}</output>
    </div>
  );
}


describe('useProtectedFileObjectUrl', () => {
  const originalFetch = global.fetch;
  const originalCreateObjectUrl = global.URL.createObjectURL;
  const originalRevokeObjectUrl = global.URL.revokeObjectURL;

  beforeEach(() => {
    global.fetch = jest.fn();
    global.URL.createObjectURL = jest.fn(() => 'blob:tenant-file');
    global.URL.revokeObjectURL = jest.fn();
  });

  afterEach(() => {
    global.fetch = originalFetch;
    if (originalCreateObjectUrl) global.URL.createObjectURL = originalCreateObjectUrl;
    else delete global.URL.createObjectURL;
    if (originalRevokeObjectUrl) global.URL.revokeObjectURL = originalRevokeObjectUrl;
    else delete global.URL.revokeObjectURL;
  });

  it('recognizes only local tenant content paths as protected', () => {
    expect(isProtectedTenantFileUrl('/tenant-files/31/content')).toBe(true);
    expect(isProtectedTenantFileUrl('/tenant-files/31/content/')).toBe(true);
    expect(isProtectedTenantFileUrl('https://evil.example/tenant-files/31/content')).toBe(false);
    expect(isProtectedTenantFileUrl('//evil.example/tenant-files/31/content')).toBe(false);
  });

  it('keeps compatibility URLs direct without fetching a Blob', () => {
    render(<PreviewHarness url="/uploads/company-1/photo.png" fileSrc={value => 'https://api.test' + value}/>);

    expect(screen.getByTestId('src')).toHaveTextContent('https://api.test/uploads/company-1/photo.png');
    expect(screen.getByTestId('loading')).toHaveTextContent('ready');
    expect(global.fetch).not.toHaveBeenCalled();
    expect(global.URL.createObjectURL).not.toHaveBeenCalled();
  });

  it('loads protected content through authenticated fetch and revokes the Blob URL', async () => {
    const blob = new Blob(['protected'], {type: 'image/png'});
    global.fetch.mockResolvedValue({ok: true, blob: async () => blob});
    const {unmount} = render(
      <PreviewHarness url="/tenant-files/31/content" fileSrc={value => 'https://api.test' + value}/>,
    );

    expect(screen.getByTestId('loading')).toHaveTextContent('loading');
    await waitFor(() => expect(screen.getByTestId('src')).toHaveTextContent('blob:tenant-file'));
    const [, request] = global.fetch.mock.calls[0];
    expect(global.fetch).toHaveBeenCalledWith(
      'https://api.test/tenant-files/31/content',
      expect.objectContaining({credentials: 'include'}),
    );
    expect(request.signal).toBeInstanceOf(AbortSignal);
    expect(global.URL.createObjectURL).toHaveBeenCalledWith(blob);

    unmount();

    expect(global.URL.revokeObjectURL).toHaveBeenCalledWith('blob:tenant-file');
  });

  it('aborts an unfinished protected request on unmount', () => {
    let requestSignal;
    global.fetch.mockImplementation((_url, options) => {
      requestSignal = options.signal;
      return new Promise(() => {});
    });
    const {unmount} = render(<PreviewHarness url="/tenant-files/32/content"/>);

    unmount();

    expect(requestSignal.aborted).toBe(true);
    expect(global.URL.createObjectURL).not.toHaveBeenCalled();
  });

  it('revokes the previous Blob URL when the protected file changes', async () => {
    global.fetch.mockResolvedValue({ok: true, blob: async () => new Blob(['protected'])});
    global.URL.createObjectURL
      .mockReturnValueOnce('blob:first-file')
      .mockReturnValueOnce('blob:second-file');
    const {rerender, unmount} = render(<PreviewHarness url="/tenant-files/34/content"/>);
    await waitFor(() => expect(screen.getByTestId('src')).toHaveTextContent('blob:first-file'));

    rerender(<PreviewHarness url="/tenant-files/35/content"/>);

    await waitFor(() => expect(screen.getByTestId('src')).toHaveTextContent('blob:second-file'));
    expect(global.URL.revokeObjectURL).toHaveBeenCalledWith('blob:first-file');

    unmount();

    expect(global.URL.revokeObjectURL).toHaveBeenCalledWith('blob:second-file');
  });

  it('fails closed when protected content cannot be loaded', async () => {
    global.fetch.mockResolvedValue({ok: false, status: 403});
    render(<PreviewHarness url="/tenant-files/33/content"/>);

    await waitFor(() => expect(screen.getByTestId('error')).toHaveTextContent('HTTP 403'));
    expect(screen.getByTestId('src')).toBeEmptyDOMElement();
    expect(screen.getByTestId('loading')).toHaveTextContent('ready');
    expect(global.URL.createObjectURL).not.toHaveBeenCalled();
  });
});
