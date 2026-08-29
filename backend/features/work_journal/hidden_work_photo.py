"""Server-side photo requirement for hidden construction work."""

HIDDEN_WORK_PHOTO_REQUIRED_DETAIL = (
    "Скрытую работу нельзя подтвердить без фотоотчёта. "
    "Приложите фото до отправки или подтверждения работы."
)


def hidden_work_photo_required(*, hidden_work, status, photo_url) -> bool:
    """Return True when a confirmed hidden-work row has no photo evidence."""
    return (
        bool(hidden_work)
        and str(status or "").strip() == "Подтверждено"
        and not str(photo_url or "").strip()
    )
