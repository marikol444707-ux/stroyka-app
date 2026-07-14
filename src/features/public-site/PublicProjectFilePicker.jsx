import React from 'react';
import { FileText, Image, Plus, Trash2, Upload } from 'lucide-react';
import { MAX_PUBLIC_LEAD_FILES } from './publicLeadFiles';

const formatFileSize = (bytes) => {
  const size = Math.max(0, Number(bytes) || 0);
  if (size >= 1024 * 1024) return `${(size / (1024 * 1024)).toFixed(1).replace('.0', '')} МБ`;
  return `${Math.max(1, Math.round(size / 1024))} КБ`;
};

export const PublicProjectFilePicker = ({ files = [], error = '', onChoose, onRemove }) => {
  const hasFiles = files.length > 0;
  const canAddFiles = files.length < MAX_PUBLIC_LEAD_FILES;

  return (
    <section className="public-project-file-picker" aria-label="Загрузка собственного проекта">
      <div className="public-project-file-head">
        <span aria-hidden="true"><Upload size={20} /></span>
        <div>
          <h3>Есть свой проект?</h3>
          <p>Добавьте план, PDF-проект или фотографии участка и текущего состояния.</p>
        </div>
      </div>

      <div className="public-project-file-actions">
        {canAddFiles && (
          <label className="public-project-file-button">
            {hasFiles ? <Plus size={16} /> : <Upload size={16} />}
            {hasFiles ? 'Добавить ещё' : 'Выбрать файлы'}
            <input
              type="file"
              accept="application/pdf,image/jpeg,image/png,image/webp"
              multiple
              onChange={(event) => {
                onChoose?.(event.target.files);
                event.target.value = '';
              }}
            />
          </label>
        )}
        <small>{files.length} из {MAX_PUBLIC_LEAD_FILES} файлов · PDF, JPG, PNG, WebP · до 10 МБ</small>
      </div>

      {hasFiles && (
        <ul className="public-project-file-list">
          {files.map((file, index) => {
            const isPdf = file.type === 'application/pdf';
            return (
              <li key={`${file.name}-${file.size}-${file.lastModified}`}>
                <span aria-hidden="true">{isPdf ? <FileText size={17} /> : <Image size={17} />}</span>
                <div>
                  <strong>{file.name}</strong>
                  <small>{isPdf ? 'Документ проекта' : 'Изображение'} · {formatFileSize(file.size)}</small>
                </div>
                <button type="button" aria-label={`Удалить ${file.name}`} onClick={() => onRemove?.(index)}>
                  <Trash2 size={16} />
                </button>
              </li>
            );
          })}
        </ul>
      )}

      {error && <p className="public-project-file-error" role="alert">{error}</p>}
      <p className="public-project-file-note">Файлы загрузятся только при отправке заявки и попадут в CRM вместе с выбранным расчётом.</p>
    </section>
  );
};
