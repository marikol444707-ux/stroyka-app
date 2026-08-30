import DOMPurify from 'dompurify';

export const sanitizeDocumentHtml = (content) => DOMPurify.sanitize(
  String(content || ''),
  {USE_PROFILES: {html: true}},
);
