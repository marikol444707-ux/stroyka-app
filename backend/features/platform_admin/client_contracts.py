"""Pure rules for platform client contracts.

The module intentionally does not open a database connection or write files.
Routes can use the preview result before starting a write transaction.
"""

from copy import deepcopy
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
import hashlib
import json
import re


CONTRACT_STATUSES = frozenset({
    "draft",
    "issued",
    "active",
    "expired",
    "terminated",
    "cancelled",
})

_STATUS_TRANSITIONS = {
    "draft": frozenset({"issued", "cancelled"}),
    "issued": frozenset({"active", "cancelled"}),
    "active": frozenset({"expired", "terminated"}),
    "expired": frozenset(),
    "terminated": frozenset(),
    "cancelled": frozenset(),
}

_PARTY_ALIASES = {
    "legalForm": ("legalForm", "legal_form"),
    "legalName": ("legalName", "legal_name", "fullName", "full_name", "name"),
    "shortName": ("shortName", "short_name"),
    "inn": ("inn",),
    "kpp": ("kpp",),
    "ogrn": ("ogrn",),
    "ogrnip": ("ogrnip",),
    "legalAddress": ("legalAddress", "legal_address"),
    "phone": ("phone", "contactPhone", "contact_phone"),
    "email": ("email", "contactEmail", "contact_email"),
    "settlementAccount": ("settlementAccount", "settlement_account", "rs"),
    "bankName": ("bankName", "bank_name"),
    "bankBik": ("bankBik", "bank_bik", "bik"),
    "correspondentAccount": (
        "correspondentAccount",
        "correspondent_account",
        "ks",
    ),
    "signatoryName": (
        "signatoryName",
        "signatory_name",
        "directorName",
        "director_name",
        "contactName",
        "contact_name",
    ),
    "signatoryBasis": ("signatoryBasis", "signatory_basis", "basis"),
}

_DIGIT_FIELDS = frozenset({
    "inn",
    "kpp",
    "ogrn",
    "ogrnip",
    "settlementAccount",
    "bankBik",
    "correspondentAccount",
})


def _value(mapping, *names, default=None):
    if not isinstance(mapping, dict):
        return default
    for name in names:
        if name in mapping and mapping[name] is not None:
            return mapping[name]
    return default


def _text(value):
    if value is None:
        return ""
    return " ".join(str(value).strip().split())


def _digits(value):
    return re.sub(r"\D", "", _text(value))


def _phone(value):
    digits = _digits(value)
    if len(digits) == 11 and digits.startswith("8"):
        return "+7" + digits[1:]
    if len(digits) == 11 and digits.startswith("7"):
        return "+" + digits
    if len(digits) == 10:
        return "+7" + digits
    return ("+" + digits) if digits else ""


def _infer_legal_form(normalized):
    explicit = normalized.get("legalForm")
    if explicit:
        return explicit
    legal_name = normalized.get("legalName", "").upper()
    if (
        normalized.get("ogrnip")
        or len(normalized.get("ogrn", "")) == 15
        or legal_name.startswith("ИП ")
        or "ИНДИВИДУАЛЬНЫЙ ПРЕДПРИНИМАТЕЛЬ" in legal_name
    ):
        return "individual_entrepreneur"
    return "legal_entity"


def normalize_legal_party(party):
    """Return a detached, camelCase legal-party snapshot."""
    normalized = {}
    for output_name, aliases in _PARTY_ALIASES.items():
        value = _value(party, *aliases)
        if output_name in _DIGIT_FIELDS:
            normalized[output_name] = _digits(value)
        elif output_name == "phone":
            normalized[output_name] = _phone(value)
        elif output_name == "email":
            normalized[output_name] = _text(value).lower()
        else:
            normalized[output_name] = _text(value)
    normalized["legalForm"] = _infer_legal_form(normalized)
    if (
        normalized["legalForm"] == "individual_entrepreneur"
        and not normalized["ogrnip"]
        and len(normalized["ogrn"]) == 15
    ):
        normalized["ogrnip"] = normalized["ogrn"]
        normalized["ogrn"] = ""
    return normalized


def _blocker(code, field, message):
    return {"code": code, "field": field, "message": message}


def _party_blockers(party, prefix, label):
    blockers = []
    if not party["legalName"]:
        blockers.append(_blocker(
            prefix + "_legal_name_required",
            prefix + ".legalName",
            "Укажите полное наименование стороны: " + label + ".",
        ))
    if not party["inn"]:
        blockers.append(_blocker(
            prefix + "_inn_required",
            prefix + ".inn",
            "Укажите ИНН стороны: " + label + ".",
        ))
    elif len(party["inn"]) not in (10, 12):
        blockers.append(_blocker(
            prefix + "_inn_invalid",
            prefix + ".inn",
            "ИНН стороны «{}» должен содержать 10 или 12 цифр.".format(label),
        ))

    if party["legalForm"] == "individual_entrepreneur":
        if not party["ogrnip"]:
            blockers.append(_blocker(
                prefix + "_ogrnip_required",
                prefix + ".ogrnip",
                "Укажите ОГРНИП стороны: " + label + ".",
            ))
        elif len(party["ogrnip"]) != 15:
            blockers.append(_blocker(
                prefix + "_ogrnip_invalid",
                prefix + ".ogrnip",
                "ОГРНИП стороны «{}» должен содержать 15 цифр.".format(label),
            ))
    else:
        if not party["ogrn"]:
            blockers.append(_blocker(
                prefix + "_ogrn_required",
                prefix + ".ogrn",
                "Укажите ОГРН стороны: " + label + ".",
            ))
        elif len(party["ogrn"]) != 13:
            blockers.append(_blocker(
                prefix + "_ogrn_invalid",
                prefix + ".ogrn",
                "ОГРН стороны «{}» должен содержать 13 цифр.".format(label),
            ))

    if not party["legalAddress"]:
        blockers.append(_blocker(
            prefix + "_legal_address_required",
            prefix + ".legalAddress",
            "Укажите юридический адрес стороны: " + label + ".",
        ))

    bank_fields = (
        "settlementAccount",
        "bankName",
        "bankBik",
        "correspondentAccount",
    )
    if any(not party[field] for field in bank_fields):
        blockers.append(_blocker(
            prefix + "_bank_details_required",
            prefix + ".bankDetails",
            "Заполните банковские реквизиты стороны: " + label + ".",
        ))
    elif (
        len(party["settlementAccount"]) != 20
        or len(party["bankBik"]) != 9
        or len(party["correspondentAccount"]) != 20
    ):
        blockers.append(_blocker(
            prefix + "_bank_details_invalid",
            prefix + ".bankDetails",
            "Проверьте расчётный счёт, БИК и корреспондентский счёт стороны: "
            + label
            + ".",
        ))

    if not party["signatoryName"] or not party["signatoryBasis"]:
        blockers.append(_blocker(
            prefix + "_signatory_required",
            prefix + ".signatory",
            "Укажите подписанта и основание полномочий стороны: " + label + ".",
        ))
    return blockers


def _parse_date(value):
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    text = _text(value)
    if not text:
        return None
    try:
        return date.fromisoformat(text)
    except ValueError:
        return None


def _decimal(value):
    try:
        number = Decimal(str(value).replace(" ", "").replace(",", "."))
    except (InvalidOperation, TypeError, ValueError):
        return None
    if not number.is_finite() or number < 0:
        return None
    return number.quantize(Decimal("0.01"))


def _nonnegative_integer(value):
    if value in (None, ""):
        return None
    if isinstance(value, bool):
        return None
    try:
        number = int(value)
    except (TypeError, ValueError):
        return None
    return number if number >= 0 and str(value).strip() == str(number) else None


def _contract_value(contract, camel_name, snake_name=None, default=None):
    names = (camel_name,) if snake_name is None else (camel_name, snake_name)
    return _value(contract, *names, default=default)


def build_contract_number(year, sequence):
    try:
        year = int(year)
        sequence = int(sequence)
    except (TypeError, ValueError):
        raise ValueError("contract number requires integer year and sequence")
    if year < 2000 or year > 9999 or sequence < 1:
        raise ValueError("contract number year or sequence is out of range")
    return "STK-{}-{:04d}".format(year, sequence)


def can_transition_contract_status(current_status, target_status):
    if current_status not in CONTRACT_STATUSES or target_status not in CONTRACT_STATUSES:
        return False
    if current_status == target_status:
        return True
    return target_status in _STATUS_TRANSITIONS[current_status]


def _json_mapping(value):
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
            return parsed if isinstance(parsed, dict) else {}
        except (TypeError, ValueError):
            return {}
    return {}


def build_contract_status_transition(
    contract,
    target_status,
    existing_contracts=(),
):
    """Validate one lifecycle step without mutating the stored contract."""
    current_status = _text(_contract_value(contract, "status")).lower()
    target_status = _text(target_status).lower()
    blockers = []

    if target_status not in CONTRACT_STATUSES:
        blockers.append(_blocker(
            "contract_status_invalid",
            "status",
            "Укажите допустимый статус договора.",
        ))
    elif not can_transition_contract_status(current_status, target_status):
        blockers.append(_blocker(
            "contract_status_transition_invalid",
            "status",
            "Нельзя перевести договор из статуса «{}» в «{}».".format(
                current_status or "неизвестно",
                target_status,
            ),
        ))

    changed = not blockers and current_status != target_status
    if not changed:
        return {
            "ok": not blockers,
            "changed": False,
            "currentStatus": current_status,
            "targetStatus": target_status,
            "blockers": blockers,
        }

    generated_file = _text(_contract_value(
        contract,
        "generatedFileUrl",
        "generated_file_url",
    ))
    signed_file = _text(_contract_value(
        contract,
        "signedFileUrl",
        "signed_file_url",
    ))
    if target_status in {"issued", "active"} and not generated_file:
        blockers.append(_blocker(
            "generated_contract_pdf_required",
            "generatedFileUrl",
            "Сначала сформируйте PDF договора.",
        ))
    if target_status == "active" and not signed_file:
        blockers.append(_blocker(
            "signed_contract_pdf_required",
            "signedFileUrl",
            "Для активации загрузите подписанный PDF договора.",
        ))

    if target_status == "active":
        licensor = normalize_legal_party(_json_mapping(_contract_value(
            contract,
            "licensorSnapshot",
            "licensor_snapshot_json",
        )))
        client = normalize_legal_party(_json_mapping(_contract_value(
            contract,
            "clientSnapshot",
            "client_snapshot_json",
        )))
        blockers.extend(_party_blockers(licensor, "licensor", "правообладатель"))
        blockers.extend(_party_blockers(client, "client", "клиент"))

        starts_on = _parse_date(_contract_value(contract, "startsOn", "starts_on"))
        ends_on = _parse_date(_contract_value(contract, "endsOn", "ends_on"))
        if starts_on is None:
            blockers.append(_blocker(
                "contract_start_date_required",
                "startsOn",
                "Укажите дату начала договора.",
            ))
        elif ends_on is not None and ends_on < starts_on:
            blockers.append(_blocker(
                "contract_period_invalid",
                "endsOn",
                "Дата окончания не может быть раньше даты начала.",
            ))

        terms = _json_mapping(_contract_value(
            contract,
            "termsSnapshot",
            "terms_snapshot_json",
        ))
        if not _text(terms.get("plan")):
            blockers.append(_blocker(
                "contract_plan_required",
                "termsSnapshot.plan",
                "В договоре не зафиксирован тариф.",
            ))
        if _decimal(terms.get("monthlyFee")) is None:
            blockers.append(_blocker(
                "monthly_fee_invalid",
                "termsSnapshot.monthlyFee",
                "В договоре не зафиксирована корректная стоимость.",
            ))
        if not re.fullmatch(r"[A-Z]{3}", _text(terms.get("currency"))):
            blockers.append(_blocker(
                "currency_invalid",
                "termsSnapshot.currency",
                "В договоре не зафиксирована валюта.",
            ))

        if starts_on is not None:
            conflicts = find_overlapping_active_contracts(
                existing_contracts,
                _contract_value(contract, "companyId", "company_id"),
                _contract_value(contract, "contractType", "contract_type"),
                starts_on,
                ends_on,
                exclude_contract_id=_contract_value(contract, "id"),
            )
            if conflicts:
                blockers.append(_blocker(
                    "active_contract_period_overlap",
                    "startsOn",
                    "У клиента уже есть действующий договор этого типа на пересекающийся период.",
                ))

    return {
        "ok": not blockers,
        "changed": not blockers,
        "currentStatus": current_status,
        "targetStatus": target_status,
        "blockers": blockers,
    }


def _periods_overlap(first_start, first_end, second_start, second_end):
    first_end = first_end or date.max
    second_end = second_end or date.max
    return first_start <= second_end and second_start <= first_end


def find_overlapping_active_contracts(
    existing_contracts,
    company_id,
    contract_type,
    starts_on,
    ends_on,
    exclude_contract_id=None,
):
    starts_on = _parse_date(starts_on)
    ends_on = _parse_date(ends_on)
    if starts_on is None:
        raise ValueError("starts_on must be an ISO date")
    conflicts = []
    for contract in existing_contracts or ():
        contract_id = _contract_value(contract, "id")
        if exclude_contract_id is not None and contract_id == exclude_contract_id:
            continue
        if _contract_value(contract, "companyId", "company_id") != company_id:
            continue
        if _contract_value(
            contract,
            "contractType",
            "contract_type",
        ) != contract_type:
            continue
        if _contract_value(contract, "status") != "active":
            continue
        existing_start = _parse_date(
            _contract_value(contract, "startsOn", "starts_on")
        )
        existing_end = _parse_date(
            _contract_value(contract, "endsOn", "ends_on")
        )
        if existing_start and _periods_overlap(
            starts_on,
            ends_on,
            existing_start,
            existing_end,
        ):
            conflicts.append(contract)
    return conflicts


def _request_fingerprint(contract):
    stable = {
        key: contract.get(key)
        for key in (
            "platformAccountId",
            "companyId",
            "licensorProfileId",
            "contractType",
            "contractDate",
            "startsOn",
            "endsOn",
            "plan",
            "monthlyFee",
            "currency",
            "maxProjects",
            "maxUsers",
            "termsVersion",
        )
    }
    encoded = json.dumps(
        stable,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def build_client_contract_preview(
    payload,
    company,
    licensor,
    existing_contracts=(),
):
    """Validate and freeze a client-contract draft without side effects."""
    blockers = []
    platform_account_id = _value(
        payload,
        "platformAccountId",
        "platform_account_id",
    )
    company_id = _value(payload, "companyId", "company_id")
    licensor_profile_id = _value(
        payload,
        "licensorProfileId",
        "licensor_profile_id",
    )

    if _value(company, "id") != company_id:
        blockers.append(_blocker(
            "company_id_mismatch",
            "companyId",
            "Выбранная карточка клиента не совпадает с компанией договора.",
        ))
    if _value(company, "platformAccountId", "platform_account_id") != platform_account_id:
        blockers.append(_blocker(
            "company_platform_account_mismatch",
            "platformAccountId",
            "Компания не принадлежит выбранному аккаунту платформы.",
        ))
    if not licensor_profile_id:
        blockers.append(_blocker(
            "licensor_profile_required",
            "licensorProfileId",
            "Сначала заполните профиль правообладателя платформы.",
        ))
    elif _value(licensor, "id") != licensor_profile_id:
        blockers.append(_blocker(
            "licensor_profile_mismatch",
            "licensorProfileId",
            "Выбран неверный профиль правообладателя.",
        ))
    if _value(
        licensor,
        "platformAccountId",
        "platform_account_id",
    ) != platform_account_id:
        blockers.append(_blocker(
            "licensor_platform_account_mismatch",
            "platformAccountId",
            "Профиль правообладателя не принадлежит аккаунту платформы.",
        ))
    if _value(licensor, "active", default=True) is not True:
        blockers.append(_blocker(
            "licensor_profile_inactive",
            "licensorProfileId",
            "Профиль правообладателя неактивен.",
        ))

    licensor_snapshot = normalize_legal_party(licensor)
    client_snapshot = normalize_legal_party(company)
    blockers.extend(_party_blockers(
        licensor_snapshot,
        "licensor",
        "правообладатель",
    ))
    blockers.extend(_party_blockers(
        client_snapshot,
        "client",
        "клиент",
    ))

    contract_date = _parse_date(
        _value(payload, "contractDate", "contract_date")
    )
    starts_on = _parse_date(_value(payload, "startsOn", "starts_on"))
    raw_ends_on = _value(payload, "endsOn", "ends_on")
    ends_on = _parse_date(raw_ends_on)
    if contract_date is None:
        blockers.append(_blocker(
            "contract_date_invalid",
            "contractDate",
            "Укажите дату договора в формате ГГГГ-ММ-ДД.",
        ))
    if starts_on is None:
        blockers.append(_blocker(
            "contract_start_invalid",
            "startsOn",
            "Укажите дату начала договора в формате ГГГГ-ММ-ДД.",
        ))
    if raw_ends_on not in (None, "") and ends_on is None:
        blockers.append(_blocker(
            "contract_end_invalid",
            "endsOn",
            "Укажите дату окончания договора в формате ГГГГ-ММ-ДД.",
        ))
    if starts_on and ends_on and ends_on < starts_on:
        blockers.append(_blocker(
            "contract_period_invalid",
            "endsOn",
            "Дата окончания договора не может быть раньше даты начала.",
        ))

    monthly_fee = _decimal(_value(
        payload,
        "monthlyFee",
        "monthly_fee",
        default=_value(company, "monthlyFee", "monthly_fee"),
    ))
    if monthly_fee is None:
        blockers.append(_blocker(
            "monthly_fee_invalid",
            "monthlyFee",
            "Ежемесячная стоимость должна быть конечным неотрицательным числом.",
        ))

    currency = _text(_value(payload, "currency", default="RUB"))
    if not re.fullmatch(r"[A-Z]{3}", currency):
        blockers.append(_blocker(
            "currency_invalid",
            "currency",
            "Валюта должна состоять из трёх заглавных латинских букв.",
        ))

    max_projects_raw = _value(
        payload,
        "maxProjects",
        "max_projects",
        default=_value(company, "maxProjects", "max_projects"),
    )
    max_users_raw = _value(
        payload,
        "maxUsers",
        "max_users",
        default=_value(company, "maxUsers", "max_users"),
    )
    max_projects = _nonnegative_integer(max_projects_raw)
    max_users = _nonnegative_integer(max_users_raw)
    if max_projects_raw not in (None, "") and max_projects is None:
        blockers.append(_blocker(
            "max_projects_invalid",
            "maxProjects",
            "Лимит объектов должен быть целым неотрицательным числом.",
        ))
    if max_users_raw not in (None, "") and max_users is None:
        blockers.append(_blocker(
            "max_users_invalid",
            "maxUsers",
            "Лимит пользователей должен быть целым неотрицательным числом.",
        ))

    contract_type = _text(_value(
        payload,
        "contractType",
        "contract_type",
        default="platform_license",
    ))
    if not re.fullmatch(r"[a-z][a-z0-9_]{0,49}", contract_type):
        blockers.append(_blocker(
            "contract_type_invalid",
            "contractType",
            "Тип договора имеет недопустимый формат.",
        ))
    status = _text(_value(payload, "status", default="draft"))
    if status not in CONTRACT_STATUSES:
        blockers.append(_blocker(
            "contract_status_invalid",
            "status",
            "Указан неизвестный статус договора.",
        ))

    idempotency_key = _text(_value(
        payload,
        "idempotencyKey",
        "idempotency_key",
    ))
    if not idempotency_key or len(idempotency_key) > 128:
        blockers.append(_blocker(
            "idempotency_key_invalid",
            "idempotencyKey",
            "Ключ защиты от повторного создания обязателен и не длиннее 128 символов.",
        ))

    plan = _text(_value(
        payload,
        "plan",
        default=_value(company, "plan"),
    ))
    if not plan:
        blockers.append(_blocker(
            "plan_required",
            "plan",
            "Укажите тариф договора.",
        ))

    contract = {
        "platformAccountId": platform_account_id,
        "companyId": company_id,
        "licensorProfileId": licensor_profile_id,
        "idempotencyKey": idempotency_key,
        "contractType": contract_type,
        "contractDate": contract_date.isoformat() if contract_date else None,
        "startsOn": starts_on.isoformat() if starts_on else None,
        "endsOn": ends_on.isoformat() if ends_on else None,
        "plan": plan,
        "monthlyFee": format(monthly_fee, ".2f") if monthly_fee is not None else None,
        "currency": currency,
        "maxProjects": max_projects,
        "maxUsers": max_users,
        "status": status,
        "termsVersion": _text(_value(
            payload,
            "termsVersion",
            "terms_version",
        )),
        "licensorSnapshot": deepcopy(licensor_snapshot),
        "clientSnapshot": deepcopy(client_snapshot),
    }
    contract["termsSnapshot"] = {
        "contractType": contract_type,
        "plan": plan,
        "monthlyFee": contract["monthlyFee"],
        "currency": currency,
        "maxProjects": max_projects,
        "maxUsers": max_users,
        "startsOn": contract["startsOn"],
        "endsOn": contract["endsOn"],
        "termsVersion": contract["termsVersion"],
    }
    contract["requestFingerprint"] = _request_fingerprint(contract)

    idempotent_contract_id = None
    should_create = True
    matching_keys = [
        existing
        for existing in existing_contracts or ()
        if _contract_value(
            existing,
            "platformAccountId",
            "platform_account_id",
        ) == platform_account_id
        and _contract_value(
            existing,
            "idempotencyKey",
            "idempotency_key",
        ) == idempotency_key
    ] if idempotency_key else []
    if matching_keys:
        should_create = False
        same_company = [
            existing for existing in matching_keys
            if _contract_value(existing, "companyId", "company_id") == company_id
        ]
        if len(matching_keys) == 1 and len(same_company) == 1:
            existing_fingerprint = _contract_value(
                same_company[0],
                "requestFingerprint",
                "request_fingerprint",
            )
            if existing_fingerprint and existing_fingerprint != contract["requestFingerprint"]:
                blockers.append(_blocker(
                    "idempotency_key_conflict",
                    "idempotencyKey",
                    "Этот ключ уже использован для другого содержимого договора.",
                ))
            else:
                idempotent_contract_id = _contract_value(same_company[0], "id")
        else:
            blockers.append(_blocker(
                "idempotency_key_conflict",
                "idempotencyKey",
                "Этот ключ уже использован для другого клиента.",
            ))

    if status == "active" and starts_on:
        overlaps = find_overlapping_active_contracts(
            existing_contracts,
            company_id,
            contract_type,
            starts_on,
            ends_on,
        )
        if overlaps:
            blockers.append(_blocker(
                "active_contract_period_overlap",
                "startsOn",
                "У клиента уже есть действующий договор этого типа на пересекающийся период.",
            ))

    if blockers:
        should_create = False

    return {
        "ok": not blockers,
        "dryRun": True,
        "writesAttempted": 0,
        "readyForDraft": not blockers,
        "readyForActivation": not blockers,
        "shouldCreate": should_create,
        "idempotentContractId": idempotent_contract_id,
        "blockers": blockers,
        "contract": contract,
    }
