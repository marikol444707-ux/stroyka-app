"""Explicit public fields for the construction customer's cabinet."""

PROJECT_FIELDS = frozenset((
    'id', 'companyId', 'name', 'client', 'status', 'budget', 'deadline', 'progress',
    'floors', 'liters', 'warrantyStartDate', 'warrantyEndDate', 'warrantyContact', 'archived',
))
JOURNAL_FIELDS = frozenset((
    'id', 'companyId', 'projectId', 'project', 'description', 'unit', 'quantity',
    'date', 'status', 'photoUrl', 'confirmedAt', 'sectionName', 'workPackage',
    'estimateId', 'estimateItemKey', 'estimateItemName', 'unexpectedWorkId', 'hiddenWork',
))


def customer_project_card(row):
    return {key: value for key, value in row.items() if key in PROJECT_FIELDS}


def customer_journal_entry(row):
    return {key: value for key, value in row.items() if key in JOURNAL_FIELDS}
