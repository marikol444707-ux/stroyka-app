from backend.features.supply_kp_comparison.technical_matcher import (
    DECISION_COMPARABLE,
    DECISION_EXACT,
    DECISION_INCOMPATIBLE,
    DECISION_REVIEW_REQUIRED,
    TechnicalComparisonError,
    build_technical_signature,
    classify_supplier_pair,
    compare_required_to_offer,
    normalize_name,
)


def test_ppr_brand_difference_is_comparable():
    result = classify_supplier_pair(
        "Труба PP-R PN20 SDR6 20x3,4 мм",
        "м",
        ["Труба PP-R SDR6 Ø20x3,4 мм, PN20, Valfex"],
        ["Труба Kalde для холодной воды PN20 dy 20х3.4 мм SDR 6"],
        category="Трубы PP-R",
    )
    assert result.status == "ok"
    assert result.decision == DECISION_COMPARABLE
    assert result.writes_attempted == 0
    assert result.model_calls == 0
    assert result.to_dict()["automaticApprovalAllowed"] is False


def test_thread_gender_conflict_is_incompatible_even_with_matching_size():
    result = classify_supplier_pair(
        "Заглушка резьбовая PP-R D20x1/2",
        "шт",
        ["Заглушка резьбовая PP-R D=20 мм x 1/2\" НР, Valfex"],
        ["Заглушка в.р. 20 х 1/2\" пп"],
        category="Фитинги PP-R",
    )
    assert result.status == "blocked"
    assert result.decision == DECISION_INCOMPATIBLE
    assert result.reason_codes == ("THREAD_GENDER_CONFLICT",)


def test_missing_supplier_offer_fails_closed_to_review():
    result = classify_supplier_pair(
        "Заглушка PP-R D20",
        "шт",
        ["Заглушка PP-R D20"],
        [],
    )
    assert result.status == "review"
    assert result.decision == DECISION_REVIEW_REQUIRED


def test_transition_eccentricity_requires_review():
    result = classify_supplier_pair(
        "Переход D110x50",
        "шт",
        ["Переход ПП D=110х50 мм"],
        ["Переход эксцентрический 110x50"],
        category="Фитинги канализации",
    )
    assert result.status == "review"
    assert "ECCENTRICITY_DIFFERS" in result.reason_codes


def test_exact_normalized_required_offer_match():
    result = compare_required_to_offer(
        "Трубная оболочка 22/6 мм",
        "Трубная изоляция 22 х 6 мм",
        required_unit="пог.м",
        offered_unit="м",
        category="Теплоизоляция",
    )
    assert result.status == "ok"
    assert result.decision in {DECISION_EXACT, DECISION_COMPARABLE}
    assert result.to_dict()["automaticApprovalAllowed"] is False


def test_lower_pn_is_incompatible():
    result = compare_required_to_offer(
        "Труба PP-R PN20 SDR6 20x3,4 мм",
        "Труба PP-R PN16 SDR6 20x3,4 мм",
        required_unit="м",
        offered_unit="м",
        category="Трубы PP-R",
    )
    assert result.decision == DECISION_INCOMPATIBLE
    assert "PRESSURE_CLASS_BELOW_REQUIRED" in result.reason_codes


def test_missing_required_pressure_class_requires_review():
    result = compare_required_to_offer(
        "Труба PP-R PN20 SDR6 20x3,4 мм",
        "Труба PP-R 20x3,4 мм",
        required_unit="м",
        offered_unit="м",
        category="Трубы PP-R",
    )
    assert result.decision == DECISION_REVIEW_REQUIRED
    assert "PRESSURE_CLASS_MISSING" in result.reason_codes
    assert "SDR_MISSING" in result.reason_codes


def test_cyrillic_dimension_separator_does_not_corrupt_russian_words():
    normalized = normalize_name("Переход PP-R 20х25")
    assert "переход" in normalized
    assert "20x25" in normalized


def test_signatures_and_comparison_hashes_are_deterministic():
    first_signature = build_technical_signature("Труба PP-R PN20 20х3,4")
    second_signature = build_technical_signature("Труба PP-R PN20 20х3,4")
    assert first_signature == second_signature

    first = compare_required_to_offer(
        "Труба PP-R PN20 20х3,4",
        "Труба PP-R PN20 20х3,4",
        required_unit="м",
        offered_unit="м",
    )
    second = compare_required_to_offer(
        "Труба PP-R PN20 20х3,4",
        "Труба PP-R PN20 20х3,4",
        required_unit="м",
        offered_unit="м",
    )
    assert first.comparison_sha256 == second.comparison_sha256


def test_invalid_unbounded_input_is_rejected_with_fixed_error():
    try:
        build_technical_signature("x" * 5000)
    except TechnicalComparisonError as error:
        assert error.code == "supply_technical_comparison_invalid"
    else:
        raise AssertionError("expected TechnicalComparisonError")


def test_reinforcement_type_conflict_is_incompatible():
    result = classify_supplier_pair(
        "Труба PP-R 20x3,4 PN20",
        "м",
        ["Труба PP-R 20x3,4 PN20 армированная стекловолокном"],
        ["Труба PP-R 20x3,4 PN20 армированная алюминием"],
        category="Трубы PP-R",
    )
    assert result.decision == DECISION_INCOMPATIBLE
    assert result.reason_codes == ("REINFORCEMENT_CONFLICT",)


def test_thread_gender_multiplicity_conflict_is_incompatible():
    result = compare_required_to_offer(
        "Кран шаровый 1/2 ВР/ВР",
        "Кран шаровый 1/2 ВР/НР",
        required_unit="шт",
        offered_unit="шт",
    )
    assert result.decision == DECISION_INCOMPATIBLE
    assert "THREAD_GENDER_CONFLICT" in result.reason_codes


def test_dimension_conflict_cannot_be_overridden_by_similar_words():
    result = compare_required_to_offer(
        "Муфта PP-R 20x25",
        "Муфта PP-R 20x32",
        required_unit="шт",
        offered_unit="шт",
        category="Фитинги PP-R",
    )
    assert result.decision == DECISION_INCOMPATIBLE
    assert "DIMENSION_CONFLICT" in result.reason_codes


def test_unit_conflict_is_never_marked_safe():
    result = compare_required_to_offer(
        "Кабель ВВГ 3x2,5",
        "Кабель ВВГ 3x2,5",
        required_unit="м",
        offered_unit="шт",
    )
    assert result.decision == DECISION_REVIEW_REQUIRED
    assert "UNIT_CONFLICT" in result.reason_codes
    assert result.to_dict()["automaticApprovalAllowed"] is False


def test_deterministic_fuzz_does_not_create_side_effects():
    import random

    randomizer = random.Random(25082026)
    alphabet = "абвгдежзиклмнопрстуфхцчшщэюяABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789 /x-,.()"
    for _ in range(200):
        left = "".join(randomizer.choice(alphabet) for _ in range(80)).strip() or "материал 1"
        right = "".join(randomizer.choice(alphabet) for _ in range(80)).strip() or "материал 2"
        first = compare_required_to_offer(
            left,
            right,
            required_unit="шт",
            offered_unit="шт",
        )
        second = compare_required_to_offer(
            left,
            right,
            required_unit="шт",
            offered_unit="шт",
        )
        assert first == second
        assert first.writes_attempted == 0
        assert first.model_calls == 0
