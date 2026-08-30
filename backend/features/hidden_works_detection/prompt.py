"""Canonical prompt contract for hidden-works detection."""

import json


HIDDEN_WORKS_DETECTION_INSTRUCTIONS = (
    "Ты отвечаешь СТРОГО валидным JSON без markdown и пояснений. Только JSON."
)


def build_hidden_works_detection_prompt(names):
    if (
        type(names) not in (list, tuple)
        or not names
        or any(type(name) is not str or not name.strip() for name in names)
    ):
        raise ValueError("hidden_works_detection_prompt_invalid") from None
    return (
        "Ниже список наименований строительных работ из сметы. Определи, какие из них являются "
        "СКРЫТЫМИ работами, требующими оформления Акта освидетельствования скрытых работ (АОСР) по "
        "СНиП 12-01-2004 — это работы, скрываемые последующими конструкциями (земляные, фундаменты, "
        "армирование, бетонирование, гидро-/паро-/теплоизоляция, стяжки, скрытые инженерные сети — "
        "кабели/трубопроводы в стенах и полах, заземление, закладные и т.п.). Отделочные и монтажные "
        "видимые работы НЕ являются скрытыми.\n\n"
        "Список работ (JSON-массив):\n"
        + json.dumps(names, ensure_ascii=False)
        + "\n\n"
        + 'Верни СТРОГО JSON без markdown: {"hidden": ["точное название работы из списка", ...]}'
    )
