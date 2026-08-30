"""Canonical prompt contract for hidden-works detection."""

import json


HIDDEN_WORKS_DETECTION_INSTRUCTIONS = (
    "Ты отвечаешь СТРОГО валидным JSON без markdown и пояснений. Только JSON."
)
HIDDEN_WORKS_DETECTION_MAX_OUTPUT_TOKENS = 128


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
                        "type": "string",
                        "enum": list(validated),
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
        "розетка — видимая.\n\n"
        "Список работ (JSON-массив):\n"
        + json.dumps(validated, ensure_ascii=False)
        + "\n\n"
        + 'Верни СТРОГО JSON без markdown: {"hidden": ["точное название работы из списка", ...]}'
    )
