import unittest
from scripts.qa_bootstrap_plan import recovery_gaps, HOLD
from scripts.qa_recovery_model import STAGES, new_model, advance, fail, recovery_plan, execute

SHA = 'a' * 40


def evidence(required):
    return dict(build_sha=SHA, recovery={k: True for k in recovery_gaps({})},
                **{k: True for k in required})


class RecoveryTests(unittest.TestCase):
    def test_complete_model_is_still_held(self):
        state = new_model(SHA)
        for name, required in STAGES:
            state = advance(state, name, evidence(required))
        self.assertEqual(state.status, 'model_complete_execution_held')
        self.assertEqual(len(state.journal), 10)
        called = []
        with self.assertRaisesRegex(RuntimeError, HOLD):
            execute(state, adapter=lambda: called.append(True), force=True)
        self.assertEqual(called, [])

    def test_every_stage_missing_evidence_fails_without_mutation(self):
        state = new_model(SHA)
        for name, required in STAGES:
            for key in required:
                data = evidence(required)
                data[key] = 'true'
                with self.subTest(stage=name, key=key), self.assertRaises(ValueError):
                    advance(state, name, data)
            previous = state
            state = advance(state, name, evidence(required))
            self.assertEqual(len(previous.journal) + 1, len(state.journal))

    def test_skip_repeat_and_stale_build(self):
        state = new_model(SHA)
        with self.assertRaises(ValueError):
            advance(state, 'empty_schema', {})
        name, required = STAGES[0]
        data = evidence(required)
        data['build_sha'] = 'b' * 40
        with self.assertRaises(ValueError):
            advance(state, name, data)
        state = advance(state, name, evidence(required))
        with self.assertRaises(ValueError):
            advance(state, name, evidence(required))

    def test_failure_at_every_stage_retains_recovery_and_blocks_resume(self):
        state = new_model(SHA)
        for name, required in STAGES:
            failed = fail(state)
            plan = recovery_plan(failed)
            self.assertFalse(plan['execution_allowed'])
            self.assertFalse(plan['cleanup_allowed'])
            self.assertFalse(plan['automatic_downgrade'])
            with self.assertRaises(ValueError):
                advance(failed, name, evidence(required))
            state = advance(state, name, evidence(required))

    def test_backup_requires_restore_not_just_dump(self):
        state = new_model(SHA)
        for name, required in STAGES[:2]:
            state = advance(state, name, evidence(required))
        data = evidence(STAGES[2][1])
        data['recovery']['restore_demonstrated'] = False
        with self.assertRaises(ValueError):
            advance(state, 'backup', data)

    def test_exact_sha_required(self):
        for value in ('short', '', None, 'A' * 40):
            with self.assertRaises(ValueError):
                new_model(value)
