import { buildProjectsPageContext } from './buildProjectsPageContext';
import { aiSeverityMeta } from '../../utils/statusMetaUtils';

it('passes the AI finding severity formatter to the project screen', () => {
  const context = buildProjectsPageContext({});
  expect(context.aiSeverityMeta).toBe(aiSeverityMeta);
  expect(typeof context.aiSeverityMeta).toBe('function');
});
