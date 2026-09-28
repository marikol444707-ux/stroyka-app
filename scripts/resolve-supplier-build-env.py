"""Export allowlisted supplier UI switches from backend release configuration."""
import shlex
import sys
from pathlib import Path

NAMES = ('PAYMENTS', 'OPENING_CONFIRMATIONS', 'ALLOCATED_REFUNDS',
         'PAYMENT_ALLOCATIONS', 'SETTLEMENTS', 'MIXED_OPENINGS', 'MIXED_OPENING_REVIEW')
KEYS = {f'SUPPLIER_{name}_ENABLED' for name in NAMES}


def resolve(service_environment, backend_env_path):
    values = {}
    path = Path(backend_env_path) if backend_env_path else None
    if path and path.is_file():
        for line in path.read_text().splitlines():
            key, separator, value = line.strip().partition('=')
            if separator and key.strip() in KEYS:
                values.setdefault(key.strip(), value.strip().strip('\"').strip("'"))
    for entry in shlex.split(service_environment):
        key, separator, value = entry.partition('=')
        if separator and key in KEYS:
            values[key] = value
    for key, value in values.items():
        if value not in ('0', '1'):
            raise ValueError(f'{key}: ожидается 0 или 1')
    enabled = lambda name: values.get(f'SUPPLIER_{name}_ENABLED', '0') == '1'
    dependencies = {'OPENING_CONFIRMATIONS': ('PAYMENTS',),
                    'MIXED_OPENINGS': ('PAYMENTS', 'OPENING_CONFIRMATIONS', 'MIXED_OPENING_REVIEW'),
                    'ALLOCATED_REFUNDS': ('PAYMENTS', 'PAYMENT_ALLOCATIONS', 'SETTLEMENTS')}
    for feature, required in dependencies.items():
        if enabled(feature):
            for name in required:
                if not enabled(name):
                    raise ValueError(f'SUPPLIER_{feature}_ENABLED требует SUPPLIER_{name}_ENABLED=1')
    return [f'REACT_APP_SUPPLIER_{name}_ENABLED={str(enabled(name)).lower()}' for name in (*NAMES[:3], 'MIXED_OPENINGS')]


if __name__ == '__main__':
    try:
        print('\n'.join(resolve(sys.argv[1] if len(sys.argv) > 1 else '',
                                sys.argv[2] if len(sys.argv) > 2 else '')))
    except ValueError as error:
        print(str(error), file=sys.stderr)
        sys.exit(2)
