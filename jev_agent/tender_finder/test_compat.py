from copy import deepcopy
import unittest
from unittest.mock import Mock

from .compat import LegacyBindingError, LegacyRequest, normalize_request
from .contract import InvalidRequest, SearchRequest


def v1():
    return {'version':1, 'request_id':'search-fixture-001', 'region':'Ставропольский край',
            'sources':['eis','commercial'], 'topics':['ремонт']}


def v2():
    return {**v1(), 'version':2, 'topics':['капремонт'], 'price_min_rub':1000000}


class CompatibilityTests(unittest.TestCase):
    def test_v1_uses_existing_validator_and_does_not_translate_topic_labels(self):
        original=v1()
        callback=Mock(return_value=deepcopy(original))
        result=normalize_request(original, legacy_validator=callback)
        self.assertIsInstance(result,LegacyRequest)
        self.assertEqual(result.legacy_payload(),original)
        callback.assert_called_once_with(original)
        self.assertEqual(result.request_id, original['request_id'])

    def test_legacy_all_selector_expansion_and_order_are_owned_by_existing_validator(self):
        # Synthetic callback output, not a guessed implementation of installed v1.
        raw={**v1(), 'topics':['все']}
        expanded={**v1(), 'topics':['ремонт','кровля','электромонтаж']}
        result=normalize_request(raw,legacy_validator=Mock(return_value=expanded))
        self.assertEqual(result.legacy_payload()['topics'],expanded['topics'])
        self.assertEqual(raw['topics'],['все'])

    def test_v2_does_not_call_five_field_legacy_validator(self):
        callback=Mock(side_effect=AssertionError('Do not send v2 to installed v1'))
        result=normalize_request(v2(),legacy_validator=callback)
        self.assertIsInstance(result,SearchRequest)
        callback.assert_not_called()

    def test_v2_unknown_fields_are_explicit_not_silently_dropped_for_legacy(self):
        with self.assertRaises(InvalidRequest) as caught:
            normalize_request({**v2(),'companyId':999},legacy_validator=Mock())
        self.assertEqual(caught.exception.issues[0].code,'untrusted_company_field')

    def test_legacy_rejection_type_and_reason_are_preserved(self):
        class ExistingBadRequest(ValueError):
            pass
        for payload in ({**v1(),'extra':'value'}, {**v1(),'version':True}, None):
            with self.subTest(payload=payload):
                callback=Mock(side_effect=ExistingBadRequest('invalid_fields'))
                with self.assertRaisesRegex(ExistingBadRequest,'invalid_fields'):
                    normalize_request(payload,legacy_validator=callback)

    def test_missing_binding_never_implies_compatibility(self):
        with self.assertRaisesRegex(LegacyBindingError,'reviewed_legacy_validator_required'):
            normalize_request(v1())

    def test_validator_cannot_change_request_identity_or_return_v2_as_v1(self):
        for normalized in ({**v1(),'request_id':'other-id'},v2(),{},None):
            with self.subTest(normalized=normalized),self.assertRaises(LegacyBindingError):
                normalize_request(v1(),legacy_validator=Mock(return_value=normalized))

    def test_callback_and_returned_payload_cannot_mutate_the_original_or_cached_envelope(self):
        original=v1()
        def callback(data):
            data['topics'].append('кровля')
            return data
        result=normalize_request(original,legacy_validator=callback)
        changed=result.legacy_payload();changed['topics'].append('фасад')
        self.assertEqual(original['topics'],['ремонт'])
        self.assertEqual(result.legacy_payload()['topics'],['ремонт','кровля'])


if __name__=='__main__':
    unittest.main()
