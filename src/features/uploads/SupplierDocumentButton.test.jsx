import React from 'react';
import {TextEncoder} from 'util';
import {render,screen,fireEvent,waitFor,act} from '@testing-library/react';
import SupplierDocumentButton from './SupplierDocumentButton';
import {loadPdfDocument} from './loadPdfDocument';
import {PREVIEW_INVALIDATED} from '../../hooks/usePreviewInvalidation';
jest.mock('./loadPdfDocument',()=>({loadPdfDocument:jest.fn()}));
const oldFetch=global.fetch,oldCreate=URL.createObjectURL,oldRevoke=URL.revokeObjectURL;
const page={getViewport:({scale})=>({width:600*scale,height:800*scale}),render:()=>({promise:Promise.resolve(),cancel:jest.fn()})};
const pdf={numPages:2,getPage:jest.fn(async()=>page)};
const blob={size:100,type:'application/pdf',arrayBuffer:async()=>new TextEncoder().encode('%PDF-test').buffer};
beforeEach(()=>{
 global.fetch=jest.fn(async()=>({ok:true,blob:async()=>blob,headers:{get:()=>null}}));
 URL.createObjectURL=jest.fn(()=> 'blob:document');URL.revokeObjectURL=jest.fn();
 loadPdfDocument.mockResolvedValue({promise:Promise.resolve(pdf),destroy:jest.fn()});
 jest.spyOn(HTMLCanvasElement.prototype,'getContext').mockReturnValue({});
});
afterEach(()=>{global.fetch=oldFetch;URL.createObjectURL=oldCreate;URL.revokeObjectURL=oldRevoke;jest.restoreAllMocks();jest.clearAllMocks();});
test('opens a PDF inside the app on demand, turns pages and releases the file on close',async()=>{
 render(<SupplierDocumentButton url="/tenant-files/7/content" label="Открыть предложение"/>);
 expect(fetch).not.toHaveBeenCalled();
 fireEvent.click(screen.getByRole('button',{name:'Открыть предложение'}));
 await screen.findByRole('link',{name:'Скачать'});
 expect(screen.getByRole('dialog')).toHaveAttribute('aria-modal','true');
 expect(screen.getByText('1 / 2')).toBeInTheDocument();
 fireEvent.click(screen.getByRole('button',{name:'Следующая страница'}));
 await waitFor(()=>expect(pdf.getPage).toHaveBeenCalledWith(2));
 expect(fetch).toHaveBeenCalledWith('/tenant-files/7/content',expect.objectContaining({credentials:'include',cache:'no-store'}));
 fireEvent.click(screen.getByRole('button',{name:'Закрыть документ'}));
 expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
 expect(URL.revokeObjectURL).toHaveBeenCalledWith('blob:document');
 expect(screen.getByRole('button',{name:'Открыть предложение'})).toHaveFocus();
});
test('missing file has a clear error and retry loads it without another tab',async()=>{
 fetch.mockResolvedValueOnce({ok:false,status:404});
 render(<SupplierDocumentButton url="/tenant-files/7/content"/>);
 fireEvent.click(screen.getByRole('button',{name:'Открыть документ'}));
 expect(await screen.findByRole('alert')).toHaveTextContent('Файл не найден');
 expect(screen.queryByRole('link')).not.toBeInTheDocument();
 fireEvent.click(screen.getByRole('button',{name:'Попробовать ещё раз'}));
 await screen.findByRole('link',{name:'Скачать'});
});
test('forbidden response does not expose a file or renderer',async()=>{
 fetch.mockResolvedValue({ok:false,status:403});
 render(<SupplierDocumentButton url="/tenant-files/7/content"/>);
 fireEvent.click(screen.getByRole('button',{name:'Открыть документ'}));
 expect(await screen.findByRole('alert')).toHaveTextContent('Нет доступа');
 expect(loadPdfDocument).not.toHaveBeenCalled();expect(URL.createObjectURL).not.toHaveBeenCalled();
});
test('external links are not fetched',async()=>{
 render(<SupplierDocumentButton url="https://foreign.test/file.pdf"/>);
 fireEvent.click(screen.getByRole('button',{name:'Открыть документ'}));
 expect(await screen.findByRole('alert')).toHaveTextContent('Ссылка на файл устарела');
 expect(fetch).not.toHaveBeenCalled();
});
test.each(['/uploads/../secret.pdf','/uploads/%2e%2e/secret.pdf','/uploads/a%2fb.pdf'])('rejects noncanonical legacy path %s',async url=>{
 render(<SupplierDocumentButton url={url}/>);
 fireEvent.click(screen.getByRole('button',{name:'Открыть документ'}));
 await screen.findByRole('alert');expect(fetch).not.toHaveBeenCalled();
});
test('opens a legacy PDF with a Russian filename',async()=>{
 render(<SupplierDocumentButton url="/uploads/Предложение.pdf"/>);
 fireEvent.click(screen.getByRole('button',{name:'Открыть документ'}));
 await screen.findByRole('link',{name:'Скачать'});
 expect(fetch).toHaveBeenCalledWith('/uploads/Предложение.pdf',expect.objectContaining({credentials:'include'}));
});
test('changing company invalidates the viewer and aborts the download',async()=>{
 fetch.mockImplementation(()=>new Promise(()=>{}));
 render(<SupplierDocumentButton url="/tenant-files/7/content"/>);
 fireEvent.click(screen.getByRole('button',{name:'Открыть документ'}));
 const signal=fetch.mock.calls[0][1].signal;
 act(()=>window.dispatchEvent(new Event(PREVIEW_INVALIDATED)));
 expect(screen.queryByRole('dialog')).not.toBeInTheDocument();expect(signal.aborted).toBe(true);
});
test('HTML error pages are never accepted as a PDF',async()=>{
 fetch.mockResolvedValue({ok:true,blob:async()=>({...blob,type:'text/html',arrayBuffer:async()=>new TextEncoder().encode('<html>').buffer})});
 render(<SupplierDocumentButton url="/tenant-files/7/content"/>);
 fireEvent.click(screen.getByRole('button',{name:'Открыть документ'}));
 expect(await screen.findByRole('alert')).toHaveTextContent('Этот файл нельзя показать');
 expect(loadPdfDocument).not.toHaveBeenCalled();
});
