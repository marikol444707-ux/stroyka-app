"""PDF rendering and upload validation for platform client contracts."""

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
import io
import json
import os
import re

from fastapi import HTTPException


MAX_SIGNED_CONTRACT_BYTES = 12 * 1024 * 1024


@dataclass(frozen=True)
class RenderedClientContractDocument:
    content: bytes
    filename: str
    plain_text: str


def _json_object(value):
    if isinstance(value, dict):
        return dict(value)
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except (TypeError, ValueError):
            return {}
        return parsed if isinstance(parsed, dict) else {}
    return {}


def _text(value, fallback="-"):
    normalized = " ".join(str(value or "").strip().split())
    return normalized or fallback


def _money(value, currency):
    try:
        number = Decimal(str(value or "0")).quantize(Decimal("0.01"))
    except (InvalidOperation, TypeError, ValueError):
        number = Decimal("0.00")
    return f"{number:,.2f}".replace(",", " ").replace(".", ",") + " " + _text(currency, "RUB")


def _limit(value, label):
    if value in (None, ""):
        return "без лимита " + label
    return f"{int(value)} {label}"


def _safe_filename(number):
    safe = re.sub(r"[^A-Za-z0-9А-Яа-яЁё._-]+", "-", str(number or "")).strip("-._")
    return (safe[:70] or "platform-client-contract") + ".pdf"


def _font_paths():
    regular_candidates = (
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/System/Library/Fonts/Supplemental/Arial.ttf",
        "/Library/Fonts/Arial Unicode.ttf",
    )
    bold_candidates = (
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
    )
    regular = next((path for path in regular_candidates if os.path.isfile(path)), None)
    bold = next((path for path in bold_candidates if os.path.isfile(path)), None)
    if not regular:
        raise RuntimeError("client_contract_pdf_cyrillic_font_missing")
    return regular, bold or regular


def _register_fonts():
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont

    regular_path, bold_path = _font_paths()
    if "StroykaContract" not in pdfmetrics.getRegisteredFontNames():
        pdfmetrics.registerFont(TTFont("StroykaContract", regular_path))
    if "StroykaContractBold" not in pdfmetrics.getRegisteredFontNames():
        pdfmetrics.registerFont(TTFont("StroykaContractBold", bold_path))
    return "StroykaContract", "StroykaContractBold"


def _party_summary(label, party):
    legal_id_label = "ОГРНИП" if party.get("ogrnip") else "ОГРН"
    legal_id = party.get("ogrnip") or party.get("ogrn")
    bank = ", ".join(filter(None, (
        _text(party.get("bankName"), ""),
        ("БИК " + _text(party.get("bankBik"), "")) if party.get("bankBik") else "",
        ("р/с " + _text(party.get("settlementAccount"), "")) if party.get("settlementAccount") else "",
        ("к/с " + _text(party.get("correspondentAccount"), "")) if party.get("correspondentAccount") else "",
    )))
    return [
        label,
        _text(party.get("legalName")),
        "ИНН " + _text(party.get("inn")),
        legal_id_label + " " + _text(legal_id),
        "КПП " + _text(party.get("kpp")) if party.get("kpp") else "",
        "Юридический адрес: " + _text(party.get("legalAddress")),
        "Банк: " + (bank or "-"),
        "Подписант: " + _text(party.get("signatoryName")) + ", действует на основании " + _text(party.get("signatoryBasis")),
    ]


def _validate_snapshot(contract):
    licensor = _json_object(contract.get("licensor_snapshot_json") or contract.get("licensorSnapshot"))
    client = _json_object(contract.get("client_snapshot_json") or contract.get("clientSnapshot"))
    terms = _json_object(contract.get("terms_snapshot_json") or contract.get("termsSnapshot"))
    required_party_fields = (
        "legalName",
        "inn",
        "legalAddress",
        "settlementAccount",
        "bankName",
        "bankBik",
        "correspondentAccount",
        "signatoryName",
        "signatoryBasis",
    )
    if any(not party.get(field) for party in (licensor, client) for field in required_party_fields):
        raise ValueError("client_contract_snapshot_incomplete")
    if not terms.get("plan") or terms.get("monthlyFee") in (None, "") or not terms.get("startsOn"):
        raise ValueError("client_contract_snapshot_incomplete")
    return licensor, client, terms


def render_client_contract_pdf(contract):
    """Render a contract solely from its immutable party and terms snapshots."""
    source = dict(contract or {})
    licensor, client, terms = _validate_snapshot(source)
    try:
        from reportlab.lib import colors
        from reportlab.lib.enums import TA_CENTER
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
        from reportlab.lib.units import mm
        from reportlab.platypus import (
            PageBreak,
            Paragraph,
            SimpleDocTemplate,
            Spacer,
            Table,
            TableStyle,
        )
    except ImportError as exc:
        raise RuntimeError("client_contract_pdf_dependency_missing") from exc

    regular_font, bold_font = _register_fonts()
    number = _text(source.get("number"), "без номера")
    contract_date = _text(source.get("contract_date") or source.get("contractDate"))
    fee = _money(terms.get("monthlyFee"), terms.get("currency"))
    period = _text(terms.get("startsOn")) + " - " + _text(terms.get("endsOn"), "бессрочно")
    limit_text = ", ".join((
        _limit(terms.get("maxProjects"), "объектов"),
        _limit(terms.get("maxUsers"), "пользователей"),
    ))

    plain_lines = [
        "ЛИЦЕНЗИОННЫЙ ДОГОВОР № " + number,
        "Дата договора: " + contract_date,
        *_party_summary("Лицензиар", licensor),
        *_party_summary("Лицензиат", client),
        "Тариф: " + _text(terms.get("plan")),
        "Период: " + period,
        "Стоимость: " + fee + " в месяц",
        "Лимиты: " + limit_text,
        "Автоматическое списание денежных средств не производится.",
    ]
    plain_text = "\n".join(line for line in plain_lines if line)

    buffer = io.BytesIO()
    document = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=18 * mm,
        leftMargin=18 * mm,
        topMargin=16 * mm,
        bottomMargin=16 * mm,
        title="Лицензионный договор " + number,
        author="Stroyka ERP",
    )
    sample = getSampleStyleSheet()
    body = ParagraphStyle(
        "ContractBody",
        parent=sample["BodyText"],
        fontName=regular_font,
        fontSize=9,
        leading=13,
        spaceAfter=5,
    )
    heading = ParagraphStyle(
        "ContractHeading",
        parent=body,
        fontName=bold_font,
        fontSize=11,
        leading=15,
        spaceBefore=7,
        spaceAfter=5,
    )
    title = ParagraphStyle(
        "ContractTitle",
        parent=heading,
        fontSize=15,
        leading=19,
        alignment=TA_CENTER,
        spaceAfter=12,
    )
    small = ParagraphStyle(
        "ContractSmall",
        parent=body,
        fontSize=8,
        leading=11,
    )
    party_heading = ParagraphStyle(
        "ContractPartyHeading",
        parent=small,
        fontName=bold_font,
        spaceAfter=4,
    )

    def paragraph(text, style=body):
        escaped = (
            str(text or "-")
            .replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
        )
        return Paragraph(escaped, style)

    story = [
        paragraph("ЛИЦЕНЗИОННЫЙ ДОГОВОР № " + number, title),
        Table(
            [[paragraph("г. Ставрополь", body), paragraph(contract_date, body)]],
            colWidths=[80 * mm, 78 * mm],
            style=TableStyle([
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("ALIGN", (1, 0), (1, 0), "RIGHT"),
            ]),
        ),
        Spacer(1, 6),
        paragraph(
            f"{_text(licensor.get('legalName'))}, именуемый далее «Лицензиар», в лице "
            f"{_text(licensor.get('signatoryName'))}, действующего на основании "
            f"{_text(licensor.get('signatoryBasis'))}, с одной стороны, и "
            f"{_text(client.get('legalName'))}, именуемое далее «Лицензиат», в лице "
            f"{_text(client.get('signatoryName'))}, действующего на основании "
            f"{_text(client.get('signatoryBasis'))}, с другой стороны, заключили настоящий договор."
        ),
        paragraph("1. Предмет договора", heading),
        paragraph(
            "1.1. Лицензиар предоставляет Лицензиату право использования информационной системы "
            "Stroyka ERP на условиях простой (неисключительной) лицензии, а также доступ к функциям "
            "и сопровождению в пределах выбранного тарифа."
        ),
        paragraph(
            "1.2. Право использования ограничено аккаунтом Лицензиата и не может передаваться "
            "третьим лицам без письменного согласия Лицензиара."
        ),
        paragraph("2. Срок и условия доступа", heading),
        paragraph("2.1. Период действия: " + period + "."),
        paragraph("2.2. Тариф: " + _text(terms.get("plan")) + ". Версия условий: " + _text(terms.get("termsVersion")) + "."),
        paragraph("2.3. Лимиты тарифа: " + limit_text + "."),
        paragraph("3. Стоимость и расчёты", heading),
        paragraph("3.1. Стоимость составляет " + fee + " в месяц."),
        paragraph(
            "3.2. Счета, акты и поступившие платежи оформляются и учитываются отдельно. "
            "Создание PDF, загрузка подписанного экземпляра или изменение статуса договора "
            "не подтверждают оплату."
        ),
        paragraph(
            "3.3. Автоматическое списание денежных средств не производится. Платёж фиксируется "
            "только после отдельного подтверждения фактического поступления средств."
        ),
        paragraph("4. Права и обязанности", heading),
        paragraph(
            "4.1. Лицензиар обеспечивает доступность системы в пределах применимых технических "
            "условий и вправе обновлять программное обеспечение без ухудшения оплаченного объёма доступа."
        ),
        paragraph(
            "4.2. Лицензиат обеспечивает сохранность учётных данных, законность загружаемых материалов "
            "и соблюдение назначенных ему лимитов."
        ),
        paragraph("5. Заключительные положения", heading),
        paragraph(
            "5.1. Юридически значимые изменения условий фиксируются отдельным документом или новой "
            "версией договора. Реквизиты и условия ниже являются снимком на дату создания договора."
        ),
        PageBreak(),
        paragraph("6. Реквизиты и подписи сторон", heading),
    ]

    def party_cell(label, party):
        return [
            paragraph(label, party_heading),
            *[
                paragraph(line, small)
                for line in _party_summary("", party)[1:]
                if line
            ],
        ]

    story.extend([
        Table(
            [[party_cell("Лицензиар", licensor), party_cell("Лицензиат", client)]],
            colWidths=[79 * mm, 79 * mm],
            style=TableStyle([
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#667085")),
                ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#D0D5DD")),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                ("TOPPADDING", (0, 0), (-1, -1), 8),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
            ]),
        ),
        Spacer(1, 30),
        Table(
            [[
                paragraph("________________ / " + _text(licensor.get("signatoryName")), small),
                paragraph("________________ / " + _text(client.get("signatoryName")), small),
            ]],
            colWidths=[79 * mm, 79 * mm],
        ),
        Spacer(1, 16),
        paragraph(
            "Документ сформирован из зафиксированных реквизитов и условий договора. "
            "Формирование документа не выполняет оплату и не изменяет доступ к системе.",
            small,
        ),
    ])

    def footer(canvas_obj, doc):
        canvas_obj.saveState()
        canvas_obj.setFont(regular_font, 7)
        canvas_obj.setFillColor(colors.HexColor("#667085"))
        canvas_obj.drawString(18 * mm, 9 * mm, "Stroyka ERP · договор " + number)
        canvas_obj.drawRightString(A4[0] - 18 * mm, 9 * mm, "Страница " + str(doc.page))
        canvas_obj.restoreState()

    document.build(story, onFirstPage=footer, onLaterPages=footer)
    return RenderedClientContractDocument(
        content=buffer.getvalue(),
        filename=_safe_filename(number),
        plain_text=plain_text,
    )


def validate_signed_contract_upload(filename, content_type, content):
    """Validate that a signed contract is a bounded PDF, not a renamed file."""
    name = os.path.basename(str(filename or "").strip())
    if not content:
        raise HTTPException(status_code=422, detail="Подписанный PDF пуст.")
    if len(content) > MAX_SIGNED_CONTRACT_BYTES:
        raise HTTPException(status_code=413, detail="Подписанный PDF слишком большой.")
    if not name.lower().endswith(".pdf"):
        raise HTTPException(status_code=415, detail="Загрузите подписанный договор в формате PDF.")
    normalized_type = str(content_type or "").split(";", 1)[0].strip().lower()
    if normalized_type not in ("application/pdf", "application/octet-stream"):
        raise HTTPException(status_code=415, detail="Загрузите подписанный договор в формате PDF.")
    if not content.startswith(b"%PDF-"):
        raise HTTPException(status_code=415, detail="Файл не является PDF-документом.")
    return {
        "filename": name[:255],
        "contentType": "application/pdf",
        "size": len(content),
    }
