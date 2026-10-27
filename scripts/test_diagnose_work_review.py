import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from scripts.diagnose_work_review import database_name, main

class WorkDiagnosticTest(unittest.TestCase):
    def test_only_database_name_is_selected_and_connection_strings_are_rejected(self):
        with tempfile.TemporaryDirectory() as root:
            app=Path(root);(app/'backend').mkdir();env=app/'backend/.env'
            env.write_text('UNRELATED_SECRET=synthetic-do-not-output\nDB_NAME="stroyka_test"\n')
            self.assertEqual(database_name(app),'stroyka_test')
            env.write_text('DB_NAME=host=untrusted\n')
            with self.assertRaises(ValueError):database_name(app)
    def test_command_is_socket_only_passwordless_and_read_only(self):
        with tempfile.TemporaryDirectory() as root:
            app=Path(root);(app/'backend').mkdir();(app/'backend/.env').write_text('DB_NAME=test_db\nWORK_ACCEPTANCE_ENABLED=1\nUNRELATED_SECRET=synthetic-do-not-output')
            with patch('os.geteuid',return_value=0),patch('sys.argv',['diagnostic','--app',root,'--project','Synthetic','--worker','Synthetic']),patch('subprocess.run') as run,contextlib.redirect_stdout(io.StringIO()) as output:
                run.return_value.returncode=0;run.return_value.stdout='{"works": []}'
                main()
            args=run.call_args.args[0];kwargs=run.call_args.kwargs
            self.assertIn('--host=/var/run/postgresql',args);self.assertIn('--no-password',args)
            self.assertIn('BEGIN READ ONLY;',kwargs['input']);self.assertIn('ROLLBACK;',kwargs['input'])
            self.assertEqual(kwargs['env']['PGOPTIONS'],'-c default_transaction_read_only=on')
            report=json.loads(output.getvalue())
            self.assertTrue(report['read_only'])
            self.assertEqual(report['env_file_flags']['WORK_ACCEPTANCE_ENABLED'],'1')
            self.assertNotIn('UNRELATED_SECRET',output.getvalue())
            self.assertNotIn('synthetic-do-not-output',output.getvalue())
