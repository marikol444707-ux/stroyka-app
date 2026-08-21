"""Private exact byte limits for the bounded A7 collector."""


MAX_JSON_QUERY_BYTES = 4 * 1024 * 1024
MAX_TEXT_FIELD_BYTES = 1024
MAX_TEXT_QUERY_AGGREGATE_BYTES = 1024 * 1024
MAX_NUMERIC_FIELD_BYTES = 64
MAX_COLLECTOR_VARIABLE_BYTES = 17 * 1024 * 1024

_INVALID_COUNT = "variable byte count is invalid"
_LIMIT_EXCEEDED = "variable byte limit exceeded"
_INVALID_METADATA = "variable byte metadata is invalid"

_BOUNDED_EMPTY = "empty"
_BOUNDED_CARDINALITY = "cardinality"
_BOUNDED_OVERFLOW = "overflow"
_BOUNDED_ACCEPTED = "accepted"


class _VariableByteLimitError(ValueError):
    """Fixed private failure without payload values."""


def _exact_byte_count(value):
    if type(value) is not int or value < 0:
        raise _VariableByteLimitError(_INVALID_COUNT)
    return value


def _metadata_invalid():
    raise _VariableByteLimitError(_INVALID_METADATA)


class _VariableByteBudget:
    """Mutable private accumulator with atomic inclusive consumption."""

    __slots__ = ("_remaining_bytes",)

    def __init__(self):
        self._remaining_bytes = MAX_COLLECTOR_VARIABLE_BYTES

    @property
    def remaining_bytes(self):
        return self._remaining_bytes

    def consume(self, count):
        count = _exact_byte_count(count)
        if count > self._remaining_bytes:
            raise _VariableByteLimitError(_LIMIT_EXCEEDED)
        self._remaining_bytes -= count


def _accept_bounded_rows(
    rows,
    budget,
    *,
    scan_limit,
    field_specs,
):
    """Validate one SQL-gated result and atomically debit accepted bytes."""

    if type(budget) is not _VariableByteBudget:
        _metadata_invalid()
    remaining_bytes = budget.remaining_bytes
    if (
        type(remaining_bytes) is not int
        or remaining_bytes < 0
        or remaining_bytes > MAX_COLLECTOR_VARIABLE_BYTES
    ):
        _metadata_invalid()
    if type(scan_limit) is not int or scan_limit < 0:
        _metadata_invalid()
    if type(rows) is not list or len(rows) > scan_limit + 1:
        _metadata_invalid()
    if not rows:
        return _BOUNDED_EMPTY, [], ()
    if any(type(row) is not dict for row in rows):
        _metadata_invalid()

    aggregate_keys = (
        "query_json_bytes",
        "query_text_bytes",
        "query_variable_bytes",
    )
    flag_keys = (
        "cardinality_limit_exceeded",
        "payload_limit_exceeded",
    )
    first = rows[0]
    aggregates = {}
    for key in aggregate_keys:
        value = first.get(key)
        if type(value) is not int or value < 0:
            _metadata_invalid()
        aggregates[key] = value
    flags = {}
    for key in flag_keys:
        value = first.get(key)
        if type(value) is not bool:
            _metadata_invalid()
        flags[key] = value

    json_total = 0
    text_total = 0
    overflow_fields = set()
    field_byte_keys = []
    clean_rows = []
    for original in rows:
        for key, expected in aggregates.items():
            if original.get(key) != expected or type(original.get(key)) is not int:
                _metadata_invalid()
        for key, expected in flags.items():
            if original.get(key) is not expected:
                _metadata_invalid()

        clean = dict(original)
        for value_key, byte_key, category, field_cap, allow_null in field_specs:
            if value_key not in original or byte_key not in original:
                _metadata_invalid()
            byte_count = original.get(byte_key)
            if type(byte_count) is not int or byte_count < 0:
                _metadata_invalid()
            if category == "json":
                json_total += byte_count
            elif category == "text":
                text_total += byte_count
            else:
                _metadata_invalid()
            if type(field_cap) is not int or field_cap < 0:
                _metadata_invalid()
            if byte_count > field_cap:
                overflow_fields.add(value_key)
            field_byte_keys.append(byte_key)

            value = original.get(value_key)
            if not flags["cardinality_limit_exceeded"] and not flags[
                "payload_limit_exceeded"
            ]:
                if value is None:
                    if not allow_null or byte_count != 0:
                        _metadata_invalid()
                elif type(value) is not str:
                    _metadata_invalid()
                else:
                    if len(value) > field_cap:
                        _metadata_invalid()
                    try:
                        actual_bytes = len(value.encode("utf-8"))
                    except UnicodeError:
                        raise _VariableByteLimitError(
                            _INVALID_METADATA
                        ) from None
                    if actual_bytes != byte_count:
                        _metadata_invalid()

        for key in aggregate_keys + flag_keys:
            clean.pop(key, None)
        for key in field_byte_keys:
            clean.pop(key, None)
        clean_rows.append(clean)

    if aggregates["query_json_bytes"] != json_total:
        _metadata_invalid()
    if aggregates["query_text_bytes"] != text_total:
        _metadata_invalid()
    if aggregates["query_variable_bytes"] != json_total + text_total:
        _metadata_invalid()

    cardinality_exceeded = len(rows) > scan_limit
    fields_allowed = not overflow_fields
    bytes_allowed = (
        fields_allowed
        and json_total <= MAX_JSON_QUERY_BYTES
        and text_total <= MAX_TEXT_QUERY_AGGREGATE_BYTES
        and aggregates["query_variable_bytes"] <= remaining_bytes
    )
    payload_exceeded = not cardinality_exceeded and not bytes_allowed
    if flags["cardinality_limit_exceeded"] is not cardinality_exceeded:
        _metadata_invalid()
    if flags["payload_limit_exceeded"] is not payload_exceeded:
        _metadata_invalid()

    if cardinality_exceeded or payload_exceeded:
        for row in rows:
            if any(row.get(spec[0]) is not None for spec in field_specs):
                _metadata_invalid()
        state = (
            _BOUNDED_CARDINALITY
            if cardinality_exceeded
            else _BOUNDED_OVERFLOW
        )
        return state, clean_rows, tuple(sorted(overflow_fields))

    budget.consume(aggregates["query_variable_bytes"])
    return _BOUNDED_ACCEPTED, clean_rows, ()


__all__ = []
