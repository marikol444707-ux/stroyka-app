-- Migration: add explicit project_id and company_id to project_documents
-- DO NOT RUN AUTOMATICALLY. Review and run with manual approval on production.
BEGIN;
ALTER TABLE project_documents
  ADD COLUMN IF NOT EXISTS project_id INT;
ALTER TABLE project_documents
  ADD COLUMN IF NOT EXISTS company_id INT;
-- Consider adding indexes and constraints after audit and staged backfill
-- Example indexes (create when ready):
-- CREATE INDEX idx_project_documents_company_id ON project_documents(company_id,id DESC);
-- CREATE INDEX idx_project_documents_project_id ON project_documents(project_id,id DESC);
COMMIT;
