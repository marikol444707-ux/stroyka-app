export const MAX_PUBLIC_LEAD_FILES = 5;
export const MAX_PUBLIC_LEAD_FILE_BYTES = 10 * 1024 * 1024;

const ALLOWED_TYPES = new Set([
  'application/pdf',
  'image/jpeg',
  'image/png',
  'image/webp',
]);

export const validatePublicLeadFiles = (fileList) => {
  const files = Array.from(fileList || []);
  if (files.length > MAX_PUBLIC_LEAD_FILES) {
    throw new Error('Можно прикрепить не больше 5 файлов.');
  }
  files.forEach((file) => {
    if (!ALLOWED_TYPES.has(file.type)) {
      throw new Error('Разрешены только PDF, JPEG, PNG или WebP.');
    }
    if (file.size > MAX_PUBLIC_LEAD_FILE_BYTES) {
      throw new Error(`Файл «${file.name}» больше 10 МБ.`);
    }
  });
  return files;
};

export const uploadPublicLeadFiles = async (files, api, fetchImpl = fetch) => {
  const validatedFiles = validatePublicLeadFiles(files);
  const tokens = [];
  for (const file of validatedFiles) {
    const formData = new FormData();
    formData.append('file', file);
    const response = await fetchImpl(api + '/site/lead-files', {
      method: 'POST',
      body: formData,
    });
    const data = await response.json().catch(() => ({}));
    if (!response.ok || !data.token) {
      throw new Error(data.detail || `Не удалось загрузить файл «${file.name}».`);
    }
    tokens.push(data.token);
  }
  return tokens;
};
