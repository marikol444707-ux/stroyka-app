// Lazy loading keeps the PDF renderer out of the main application bundle.
let worker;
export async function loadPdfDocument(data) {
  const pdf = await import('pdfjs-dist/legacy/build/pdf.mjs');
  // Webpack emits a .js worker chunk, served as JavaScript by production nginx.
  if (!worker) worker = new Worker(new URL('pdfjs-dist/legacy/build/pdf.worker.mjs', import.meta.url), {type:'module'});
  pdf.GlobalWorkerOptions.workerPort = worker;
  return pdf.getDocument({data, isEvalSupported:false, useWasm:false, useSystemFonts:true});
}
