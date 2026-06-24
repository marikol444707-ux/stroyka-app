export const HEIC_INVOICE_HELP = 'Фото HEIC не удалось прочитать. На iPhone откройте Настройки -> Камера -> Форматы -> Наиболее совместимые или отправьте фото как JPEG/PNG.';
export const RAW_INVOICE_HELP = 'RAW/DNG-фото накладной браузер не обрабатывает. Экспортируйте снимок в JPEG/PNG/HEIC или сделайте обычное фото через камеру телефона.';

export const invoiceImageAccept = 'image/jpeg,image/png,image/webp,image/heic,image/heif,image/*,.heic,.heif,.dng,.raw,.cr2,.nef,.arw,.raf,.orf,.rw2';

const RAW_IMAGE_EXTENSIONS = /\.(dng|raw|cr2|cr3|nef|arw|raf|orf|rw2)$/i;

export const isHeicLikeFile = (file = {}) => {
  const type = String(file.type || '').toLowerCase();
  const name = String(file.name || '').toLowerCase();
  return type.includes('heic') || type.includes('heif') || /\.(heic|heif)$/i.test(name);
};

export const isRawLikeFile = (file = {}) => {
  const type = String(file.type || '').toLowerCase();
  const name = String(file.name || '').toLowerCase();
  return type.includes('raw') || type.includes('dng') || RAW_IMAGE_EXTENSIONS.test(name);
};

const readFileAsDataUrl = (file) => new Promise((resolve, reject) => {
  const reader = new FileReader();
  reader.onload = () => resolve(String(reader.result || ''));
  reader.onerror = () => reject(new Error('Не удалось прочитать файл накладной'));
  reader.readAsDataURL(file);
});

const loadImage = (dataUrl, file) => new Promise((resolve, reject) => {
  const image = new Image();
  image.onload = () => resolve(image);
  image.onerror = () => reject(new Error(
    isHeicLikeFile(file)
      ? HEIC_INVOICE_HELP
      : 'Не удалось открыть фото накладной. Попробуйте JPEG/PNG или переснимите документ.'
  ));
  image.src = dataUrl;
});

export async function normalizeInvoiceImageFile(file, options = {}) {
  const { maxSide = 1800, quality = 0.88 } = options;
  if (isRawLikeFile(file)) {
    throw new Error(RAW_INVOICE_HELP);
  }
  const dataUrl = await readFileAsDataUrl(file);
  if (!dataUrl.startsWith('data:image/')) {
    throw new Error('Для распознавания накладной нужен файл изображения.');
  }

  const image = await loadImage(dataUrl, file);
  const sourceWidth = image.naturalWidth || image.width || 1;
  const sourceHeight = image.naturalHeight || image.height || 1;
  const scale = Math.min(1, maxSide / Math.max(sourceWidth, sourceHeight));
  const width = Math.max(1, Math.round(sourceWidth * scale));
  const height = Math.max(1, Math.round(sourceHeight * scale));

  const canvas = document.createElement('canvas');
  canvas.width = width;
  canvas.height = height;
  const context = canvas.getContext('2d');
  if (!context) {
    throw new Error('Браузер не смог подготовить фото накладной');
  }
  context.drawImage(image, 0, 0, width, height);

  const jpegDataUrl = canvas.toDataURL('image/jpeg', quality);
  const base64 = jpegDataUrl.split(',')[1] || '';
  const safeName = String(file.name || 'invoice-page').replace(/\.[^.]+$/, '') || 'invoice-page';
  const blob = await new Promise(resolve => canvas.toBlob(resolve, 'image/jpeg', quality));
  if (!blob || !base64) {
    throw new Error('Не удалось подготовить фото накладной');
  }

  const uploadFile = new File([blob], `${safeName}.jpg`, { type: 'image/jpeg' });
  return {
    base64,
    dataUrl: jpegDataUrl,
    mimeType: 'image/jpeg',
    uploadFile,
    originalFile: file,
    originalName: file.name || uploadFile.name,
    originalType: file.type || '',
  };
}

export const normalizeInvoiceImageFiles = (files, options) => (
  Promise.all(Array.from(files || []).map(file => normalizeInvoiceImageFile(file, options)))
);
