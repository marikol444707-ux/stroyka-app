"""Canonical prompt contract for hidden-works detection."""

import json


HIDDEN_WORKS_DETECTION_INSTRUCTIONS = (
    "Ты отвечаешь СТРОГО валидным JSON без markdown и пояснений. Только JSON."
)
HIDDEN_WORKS_DETECTION_MAX_OUTPUT_TOKENS = 128

_HIDDEN_WORKS_TASK = (
    "Ниже список наименований строительных работ из сметы. Определи, какие из них являются "
    "СКРЫТЫМИ работами, требующими оформления Акта освидетельствования скрытых работ (АОСР) по "
    "СП 48.13330.2019 — это работы, скрываемые последующими конструкциями (земляные, фундаменты, "
    "армирование, бетонирование, гидро-/паро-/теплоизоляция, стяжки, скрытые инженерные сети — "
    "кабели/трубопроводы в стенах и полах, заземление, закладные и т.п.). Отделочные и монтажные "
    "видимые работы НЕ являются скрытыми. Ключевой признак: результат работы закрывается "
    "последующим этапом и становится недоступен для контроля без вскрытия. Видимое оконечное "
    "оборудование — розетки, выключатели, светильники, вентиляционные решётки, диффузоры, "
    "радиаторы, сантехнические приборы и ревизионные люки — не являются скрытыми, даже если "
    "подключаются к скрытой сети. Разделяй сеть и её оконечный элемент: воздуховод за потолком — "
    "скрытая работа, вентиляционная решётка — видимая; проводка под штукатуркой — скрытая работа, "
    "розетка — видимая."
)


def _validated_names(names):
    if (
        type(names) not in (list, tuple)
        or not names
        or any(type(name) is not str or not name.strip() for name in names)
    ):
        raise ValueError("hidden_works_detection_prompt_invalid") from None
    return tuple(names)


def build_hidden_works_response_format(names):
    """Build the bounded JSON schema accepted by the pinned llama.cpp server."""
    validated = _validated_names(names)
    return {
        "type": "json_schema",
        "schema": {
            "type": "object",
            "properties": {
                "hidden": {
                    "type": "array",
                    "items": {
                        "type": "integer",
                        "enum": list(range(len(validated))),
                    },
                    "maxItems": len(validated),
                },
            },
            "required": ["hidden"],
            "additionalProperties": False,
        },
    }


def build_hidden_works_detection_prompt(names):
    validated = _validated_names(names)
    return (
        _HIDDEN_WORKS_TASK
        + "\n\n"
        "Список работ (JSON-массив):\n"
        + json.dumps(validated, ensure_ascii=False)
        + "\n\n"
        + 'Верни СТРОГО JSON без markdown: {"hidden": ["точное название работы из списка", ...]}'
    )


def build_indexed_hidden_works_detection_prompt(names):
    validated = _validated_names(names)
    indexed = [
        {"id": position, "name": name}
        for position, name in enumerate(validated)
    ]
    return (
        _HIDDEN_WORKS_TASK
        + "\n\nСписок работ с числовыми id (JSON-массив):\n"
        + json.dumps(indexed, ensure_ascii=False)
        + "\n\nВерни только id скрытых работ, без названий и пояснений. "
        + 'СТРОГО JSON: {"hidden": [0, 2]}'
    )


def parse_hidden_work_indices(output_text, names):
    validated = _validated_names(names)
    if type(output_text) is not str or not output_text:
        raise ValueError("hidden_works_detection_response_invalid") from None

    def reject_duplicate_keys(pairs):
        document = {}
        for key, value in pairs:
            if key in document:
                raise ValueError
            document[key] = value
        return document

    try:
        document = json.loads(
            output_text,
            object_pairs_hook=reject_duplicate_keys,
        )
        if type(document) is not dict or set(document) != {"hidden"}:
            raise ValueError
        indexes = document["hidden"]
        if type(indexes) is not list or len(indexes) > len(validated):
            raise ValueError
        selected = set()
        for position in indexes:
            if (
                type(position) is not int
                or not 0 <= position < len(validated)
                or position in selected
            ):
                raise ValueError
            selected.add(position)
    except (TypeError, ValueError):
        raise ValueError(
            "hidden_works_detection_response_invalid",
        ) from None
    return tuple(
        name
        for position, name in enumerate(validated)
        if position in selected
    )
