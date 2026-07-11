import unittest

from backend.features.estimate_changes.service import estimate_change_visibility_filter


DOCUMENT_ROLES = (
    "директор",
    "зам_директора",
    "бухгалтер",
    "прораб",
    "главный_инженер",
    "сметчик",
    "мастер",
    "субподрядчик",
    "бригадир",
    "кладовщик",
    "снабженец",
    "технадзор",
    "заказчик",
    "стройконтроль",
)
FULL_VIEW_ROLES = ("директор", "зам_директора", "бухгалтер", "главный_инженер", "сметчик")
PACKAGE_LIMIT_ROLES = ("прораб", "мастер", "субподрядчик", "бригадир")
CUSTOMER_STATUSES = (
    "Ожидает согласования",
    "Утверждено",
    "Утверждено отдельной допработой",
    "Включено в новую смету",
)


def build_filter(actors):
    return estimate_change_visibility_filter(
        actors,
        DOCUMENT_ROLES,
        FULL_VIEW_ROLES,
        PACKAGE_LIMIT_ROLES,
        ("прораб",),
        ("заказчик",),
        CUSTOMER_STATUSES,
    )


class EstimateChangeVisibilityFilterTests(unittest.TestCase):
    def test_director_is_scoped_by_company_and_non_cancelled_status(self):
        sql, params = build_filter([{"companyId": 4, "role": " директор "}])

        self.assertIn("p.company_id=%s", sql)
        self.assertIn("COALESCE(uw.status,'') <> 'Аннулировано'", sql)
        self.assertNotIn("p.name = ANY", sql)
        self.assertEqual(params, [4])

    def test_worker_keeps_project_and_package_restrictions(self):
        sql, params = build_filter([{
            "companyId": 4,
            "role": "мастер",
            "assignedProjects": ["Лицей"],
            "assignedPackages": ["Отделка"],
        }])

        self.assertIn("p.name = ANY(%s)", sql)
        self.assertIn("COALESCE(NULLIF(uw.section_name,''),'Основная') = ANY(%s)", sql)
        self.assertEqual(params, [4, ["Лицей"], ["Отделка"]])

    def test_foreman_keeps_existing_unrestricted_package_access(self):
        sql, params = build_filter([{
            "companyId": 4,
            "role": "прораб",
            "assignedProjects": ["Лицей"],
            "assignedPackages": ["Электрика"],
        }])

        self.assertNotEqual(sql, "FALSE")
        self.assertNotIn("section_name", sql)
        self.assertEqual(params, [4, ["Лицей"]])

    def test_customer_only_sees_existing_customer_statuses(self):
        sql, params = build_filter([{
            "companyId": 8,
            "role": "заказчик",
            "assignedProjects": ["Школа"],
        }])

        self.assertIn("uw.status = ANY(%s)", sql)
        self.assertEqual(params, [8, ["Школа"], list(CUSTOMER_STATUSES)])

    def test_non_document_role_fails_closed(self):
        sql, params = build_filter([{
            "companyId": 4,
            "role": "поставщик",
            "assignedProjects": ["Лицей"],
        }])

        self.assertEqual((sql, params), ("FALSE", []))

    def test_all_companies_keeps_membership_rules_separate(self):
        sql, params = build_filter([
            {"companyId": 4, "role": "директор"},
            {
                "companyId": 8,
                "role": "мастер",
                "assignedProjects": ["Школа"],
                "assignedPackages": ["Электрика"],
            },
        ])

        self.assertIn(" OR ", sql)
        self.assertEqual(params, [4, 8, ["Школа"], ["Электрика"]])

    def test_rejects_untrusted_sql_alias(self):
        with self.assertRaises(ValueError):
            estimate_change_visibility_filter(
                [],
                DOCUMENT_ROLES,
                FULL_VIEW_ROLES,
                PACKAGE_LIMIT_ROLES,
                ("прораб",),
                ("заказчик",),
                CUSTOMER_STATUSES,
                change_prefix="uw; DROP TABLE projects",
            )


if __name__ == "__main__":
    unittest.main()
