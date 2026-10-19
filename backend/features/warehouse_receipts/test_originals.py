import unittest
from unittest.mock import Mock
from fastapi import HTTPException
from .originals import retain_originals


class RetainOriginalTests(unittest.TestCase):
    def cursor(self, **row):
        cur=Mock(rowcount=1)
        cur.fetchone.return_value={'company_id':2,'status':'active',**row}
        return cur

    def test_locks_sorted_unique_files_and_retains_transactionally(self):
        cur=self.cursor()
        retain_originals(cur,['/tenant-files/9/content','/tenant-files/3/content','/tenant-files/9/content'],2)
        calls=cur.execute.call_args_list
        self.assertEqual([call.args[1] for call in calls],[(3,),(3,2),(9,),(9,2)])
        self.assertTrue(all('FOR UPDATE' in calls[i].args[0] for i in (0,2)))
        self.assertTrue(all('retained_at=COALESCE' in calls[i].args[0] for i in (1,3)))
        cur.commit.assert_not_called()

    def test_foreign_deleted_or_missing_file_blocks_before_retention(self):
        for row in ({'company_id':3,'status':'active'},{'company_id':2,'status':'deleting'},None):
            cur=self.cursor();cur.fetchone.return_value=row
            with self.subTest(row=row),self.assertRaises(HTTPException):
                retain_originals(cur,['/tenant-files/3/content'],2)
            self.assertEqual(cur.execute.call_count,1)

    def test_invalid_urls_never_lock(self):
        for urls in ([],['https://foreign/file'],['/tenant-files/0/content']):
            cur=self.cursor()
            with self.subTest(urls=urls),self.assertRaises(HTTPException):
                retain_originals(cur,urls,2)
            cur.execute.assert_not_called()

    def test_standalone_main_warehouse_rejects_project_owned_original(self):
        cur=self.cursor(project_id=9)
        with self.assertRaises(HTTPException):
            retain_originals(cur,['/tenant-files/3/content'],2,target_project='')
        self.assertEqual(cur.execute.call_count,1)

    def test_standalone_project_requires_exact_owned_project(self):
        for project_id in (None,8,9):
            cur=self.cursor(project_id=project_id);cur.fetchall.return_value=[{'id':9}]
            if project_id == 9:
                retain_originals(cur,['/tenant-files/3/content'],2,target_project='School')
            else:
                with self.assertRaises(HTTPException):
                    retain_originals(cur,['/tenant-files/3/content'],2,target_project='School')
