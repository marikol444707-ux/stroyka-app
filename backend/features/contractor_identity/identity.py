"""Shared strict identifiers for contractor evidence and explicit selections."""

PERFORMER_ROLES = {'мастер', 'субподрядчик', 'бригадир'}


def positive_id(value):
    if type(value) is not int or not 0 < value <= 2147483647:
        raise ValueError('INVALID_ID')
    return value
