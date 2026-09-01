from backend.features.supply_kp_comparison.line_aggregation import (
    SupplyLineAggregationError,
    aggregate_supply_lines,
)


def test_split_lines_are_aggregated_with_weighted_price():
    result = aggregate_supply_lines(
        [
            {
                "sourceLineId": "10",
                "name": "Трубная изоляция 28/6 мм",
                "unit": "м",
                "quantity": "100",
                "pricePerUnit": "10.00",
                "totalPrice": "1000.00",
            },
            {
                "sourceLineId": "11",
                "name": "Трубная изоляция 28/6 мм",
                "unit": "пог.м",
                "quantity": "70",
                "pricePerUnit": "12.00",
                "totalPrice": "840.00",
            },
        ]
    )
    assert result.source_line_count == 2
    assert result.aggregated_line_count == 1
    line = result.lines[0].to_dict()
    assert line["quantity"] == "170"
    assert line["totalPrice"] == "1840.00"
    assert line["pricePerUnit"] == "10.823529"
    assert line["sourceLineIds"] == ["10", "11"]
    assert result.writes_attempted == 0
    assert result.model_calls == 0


def test_tonnes_are_converted_to_kilograms_without_changing_total():
    result = aggregate_supply_lines(
        [
            {
                "name": "Цемент М500",
                "unit": "т",
                "quantity": "1.5",
                "pricePerUnit": "8000",
            }
        ]
    )
    line = result.lines[0].to_dict()
    assert line["unit"] == "кг"
    assert line["quantity"] == "1500"
    assert line["totalPrice"] == "12000.00"
    assert line["pricePerUnit"] == "8"


def test_different_manufacturers_are_not_merged_automatically():
    result = aggregate_supply_lines(
        [
            {
                "name": "Труба PP-R PN20 20x3,4",
                "manufacturer": "Valfex",
                "unit": "м",
                "quantity": 10,
                "pricePerUnit": 100,
            },
            {
                "name": "Труба PP-R PN20 20x3,4",
                "manufacturer": "Kalde",
                "unit": "м",
                "quantity": 10,
                "pricePerUnit": 100,
            },
        ]
    )
    assert result.aggregated_line_count == 2


def test_package_units_are_not_silently_converted_to_pieces():
    result = aggregate_supply_lines(
        [
            {
                "name": "Саморез 4,2x16",
                "unit": "упаковка",
                "quantity": 2,
                "pricePerUnit": 500,
            },
            {
                "name": "Саморез 4,2x16",
                "unit": "шт",
                "quantity": 200,
                "pricePerUnit": 5,
            },
        ]
    )
    assert result.aggregated_line_count == 2
    assert {line.unit for line in result.lines} == {"уп", "шт"}


def test_line_arithmetic_mismatch_is_rejected():
    try:
        aggregate_supply_lines(
            [
                {
                    "name": "Кабель ВВГ 3x2,5",
                    "unit": "м",
                    "quantity": 10,
                    "pricePerUnit": 100,
                    "totalPrice": 500,
                }
            ]
        )
    except SupplyLineAggregationError as error:
        assert error.code == "supply_line_aggregation_arithmetic_mismatch"
    else:
        raise AssertionError("expected SupplyLineAggregationError")


def test_aggregation_hash_is_order_independent_for_equivalent_groups():
    lines = [
        {
            "sourceLineId": "1",
            "name": "Изоляция 28/6",
            "unit": "м",
            "quantity": 100,
            "pricePerUnit": 10,
        },
        {
            "sourceLineId": "2",
            "name": "Изоляция 28/6",
            "unit": "м",
            "quantity": 70,
            "pricePerUnit": 12,
        },
    ]
    first = aggregate_supply_lines(lines)
    second = aggregate_supply_lines(list(reversed(lines)))
    assert first.to_dict()["lines"] == second.to_dict()["lines"]
    assert first.aggregation_sha256 == second.aggregation_sha256


def test_order_independence_with_case_variants():
    lines = [
        {
            "sourceLineId": "b",
            "name": "ИЗОЛЯЦИЯ 28/6",
            "unit": "м",
            "quantity": 70,
            "pricePerUnit": 12,
        },
        {
            "sourceLineId": "a",
            "name": "Изоляция 28/6",
            "unit": "м",
            "quantity": 100,
            "pricePerUnit": 10,
        },
    ]
    assert aggregate_supply_lines(lines).to_dict() == aggregate_supply_lines(
        list(reversed(lines))
    ).to_dict()


def test_non_finite_and_zero_quantity_are_rejected():
    for quantity in (0, "NaN", "Infinity"):
        try:
            aggregate_supply_lines(
                [
                    {
                        "name": "Материал",
                        "unit": "шт",
                        "quantity": quantity,
                        "pricePerUnit": 1,
                    }
                ]
            )
        except SupplyLineAggregationError as error:
            assert error.code == "supply_line_aggregation_invalid"
        else:
            raise AssertionError("expected SupplyLineAggregationError")


def test_huge_numeric_payload_is_rejected():
    try:
        aggregate_supply_lines(
            [
                {
                    "name": "Материал",
                    "unit": "шт",
                    "quantity": "9" * 100,
                    "pricePerUnit": 1,
                }
            ]
        )
    except SupplyLineAggregationError as error:
        assert error.code == "supply_line_aggregation_invalid"
    else:
        raise AssertionError("expected SupplyLineAggregationError")
