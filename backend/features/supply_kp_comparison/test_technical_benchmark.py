from backend.features.supply_kp_comparison.technical_benchmark import (
    TechnicalBenchmarkError,
    run_technical_benchmark,
)


def _cases():
    return [
        {
            "caseId": "compatible-ppr",
            "canonicalName": "Труба PP-R PN20 SDR6 20x3,4 мм",
            "unit": "м",
            "category": "Трубы PP-R",
            "supplier1Names": ["Труба PP-R SDR6 Ø20x3,4 мм, PN20, Valfex"],
            "supplier2Names": ["Труба Kalde PN20 dy 20х3.4 мм SDR 6"],
            "expectedStatus": "ok",
        },
        {
            "caseId": "thread-conflict",
            "canonicalName": "Заглушка резьбовая PP-R D20x1/2",
            "unit": "шт",
            "category": "Фитинги PP-R",
            "supplier1Names": ["Заглушка PP-R D20 x 1/2 НР"],
            "supplier2Names": ["Заглушка PP-R D20 x 1/2 ВР"],
            "expectedStatus": "blocked",
        },
        {
            "caseId": "one-offer",
            "canonicalName": "Заглушка PP-R D20",
            "unit": "шт",
            "category": "Фитинги PP-R",
            "supplier1Names": ["Заглушка PP-R D20"],
            "supplier2Names": [],
            "expectedStatus": "review",
        },
    ]


def test_benchmark_reports_safety_metrics_and_zero_side_effects():
    report = run_technical_benchmark(_cases())
    assert report["totalCases"] == 3
    assert report["accuracyBasisPoints"] == 10_000
    assert report["falseSafeCount"] == 0
    assert report["dangerousErrorCount"] == 0
    assert report["writesAttempted"] == 0
    assert report["modelCalls"] == 0
    assert len(report["benchmarkSha256"]) == 64


def test_benchmark_is_deterministic():
    first = run_technical_benchmark(_cases())
    second = run_technical_benchmark(_cases())
    assert first == second


def test_duplicate_case_ids_fail_closed():
    cases = _cases()
    cases[1]["caseId"] = cases[0]["caseId"]
    try:
        run_technical_benchmark(cases)
    except TechnicalBenchmarkError as error:
        assert error.code == "supply_technical_benchmark_invalid"
    else:
        raise AssertionError("expected TechnicalBenchmarkError")


def load_tests(loader, tests, pattern):
    """Expose all pure function tests to the repository unittest runner."""
    import inspect
    import unittest

    from backend.features.supply_kp_comparison import (
        test_line_aggregation,
        test_technical_benchmark,
        test_technical_matcher,
    )

    del loader, tests, pattern

    suite = unittest.TestSuite()
    modules = (
        test_line_aggregation,
        test_technical_benchmark,
        test_technical_matcher,
    )

    for module in modules:
        for name, function in inspect.getmembers(module, inspect.isfunction):
            if name.startswith("test_") and function.__module__ == module.__name__:
                suite.addTest(
                    unittest.FunctionTestCase(
                        function,
                        description=f"{module.__name__}.{name}",
                    )
                )

    return suite
