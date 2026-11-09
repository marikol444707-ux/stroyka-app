"""Preserve the company-owned material directory mode in production builds."""
from pathlib import Path
import shlex
import sys


KEY = 'COMPANY_MATERIAL_ALIASES_ENABLED'


def resolve(service_environment, backend_env_path):
    value = '0'
    path = Path(backend_env_path) if backend_env_path else None
    if path and path.is_file():
        for line in path.read_text().splitlines():
            key, separator, candidate = line.strip().partition('=')
            if separator and key.strip() == KEY:
                value = candidate.strip().strip('"').strip("'")
                break
    for entry in shlex.split(service_environment):
        key, separator, candidate = entry.partition('=')
        if separator and key == KEY:
            value = candidate
    if value not in ('0', '1'):
        raise ValueError(f'{KEY}: ожидается 0 или 1')
    return 'REACT_APP_' + KEY + '=' + value


if __name__ == '__main__':
    try:
        print(resolve(sys.argv[1] if len(sys.argv) > 1 else '',
                      sys.argv[2] if len(sys.argv) > 2 else ''))
    except ValueError as error:
        print(str(error), file=sys.stderr)
        sys.exit(2)
