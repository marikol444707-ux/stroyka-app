"""Export only warehouse UI flags matching the backend release configuration."""
import shlex
import sys
from pathlib import Path


def resolve(service_environment, backend_env_path):
    keys = {
        'WAREHOUSE_DISTRIBUTION_ENABLED',
        'WAREHOUSE_DISTRIBUTION_TRANSFERS_ENABLED',
        'OWNED_DISTRIBUTION_QUALITY_ENABLED',
    }
    values = {}
    path = Path(backend_env_path) if backend_env_path else None
    if path and path.is_file():
        for line in path.read_text().splitlines():
            key, separator, value = line.strip().partition('=')
            if separator and key.strip() in keys:
                values[key.strip()] = value.strip().strip('\"\'')
    for entry in shlex.split(service_environment):
        key, separator, value = entry.partition('=')
        if separator and key in keys:
            values[key] = value
    distribution = values.get('WAREHOUSE_DISTRIBUTION_ENABLED') == '1'
    transfers = values.get('WAREHOUSE_DISTRIBUTION_TRANSFERS_ENABLED') == '1'
    if values.get('OWNED_DISTRIBUTION_QUALITY_ENABLED') == '1' and not (distribution and transfers):
        raise ValueError('Журнал качества требует включённых распределений и перемещений по партиям')
    return [
        'REACT_APP_WAREHOUSE_DISTRIBUTION_ENABLED=' + str(distribution).lower(),
        'REACT_APP_WAREHOUSE_DISTRIBUTION_TRANSFERS_ENABLED=' + str(distribution and transfers).lower(),
    ]


if __name__ == '__main__':
    try:
        print('\n'.join(resolve(sys.argv[1] if len(sys.argv) > 1 else '',
                                sys.argv[2] if len(sys.argv) > 2 else '')))
    except ValueError as error:
        print(str(error), file=sys.stderr)
        sys.exit(2)
