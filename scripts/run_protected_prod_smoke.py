#!/usr/bin/env python3
"""Run the existing production smoke with credentials from a private file."""

import argparse
import getpass
import os
import re
import stat
from pathlib import Path


DEFAULT_ENV_FILE = Path("/etc/stroyka/prod-smoke.env")
PRODUCTION_BASE_URL = "https://stroyka26.pro"
MAX_FILE_BYTES = 16 * 1024
REQUIRED_KEYS = frozenset({
    "SMOKE_EMAIL",
    "SMOKE_PASSWORD",
    "SMOKE_COMPANY_ID",
})
OPTIONAL_KEYS = frozenset({"SMOKE_TOTP_SECRET"})
ALLOWED_KEYS = REQUIRED_KEYS | OPTIONAL_KEYS
SENSITIVE_ENV_KEYS = ALLOWED_KEYS | {"SMOKE_2FA_CODE"}
_EMAIL_RE = re.compile(r"[^@\s]{1,254}@[^@\s]{1,253}")
_TOTP_SECRET_RE = re.compile(r"[A-Z2-7]{16,128}")
_TWO_FACTOR_CODE_RE = re.compile(r"[0-9]{6}")
_COMPANY_ID_RE = re.compile(r"[1-9][0-9]{0,18}")


class ConfigurationError(ValueError):
    """The protected smoke credential file is unsafe or invalid."""


def _read_private_file(path):
    path = Path(path)
    no_follow = getattr(os, "O_NOFOLLOW", None)
    if no_follow is None:
        raise ConfigurationError("platform must support non-symlink file reads")
    try:
        descriptor = os.open(path, os.O_RDONLY | no_follow)
    except OSError as error:
        raise ConfigurationError(
            "credential path must be a readable regular non-symlink file"
        ) from error
    try:
        metadata = os.fstat(descriptor)
        if not stat.S_ISREG(metadata.st_mode):
            raise ConfigurationError(
                "credential path must be a regular non-symlink file"
            )
        if metadata.st_uid != os.geteuid():
            raise ConfigurationError(
                "credential file must be owned by the current user"
            )
        mode = stat.S_IMODE(metadata.st_mode)
        if mode not in {0o400, 0o600}:
            raise ConfigurationError(
                "credential file permissions must be 0600 or stricter"
            )
        with os.fdopen(descriptor, "rb", closefd=True) as credential_file:
            descriptor = None
            payload = credential_file.read(MAX_FILE_BYTES + 1)
    finally:
        if descriptor is not None:
            os.close(descriptor)
    if len(payload) > MAX_FILE_BYTES:
        raise ConfigurationError("credential file is too large")
    try:
        return payload.decode("utf-8")
    except UnicodeDecodeError as error:
        raise ConfigurationError("credential file must be valid UTF-8") from error


def _parse_config(payload):
    config = {}
    for line_number, line in enumerate(payload.splitlines(), start=1):
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            raise ConfigurationError(
                f"credential line {line_number} must use KEY=value"
            )
        key, value = line.split("=", 1)
        if key not in ALLOWED_KEYS:
            raise ConfigurationError(
                f"credential line {line_number} contains an unsupported key"
            )
        if key in config:
            raise ConfigurationError(
                f"credential line {line_number} duplicates a key"
            )
        if not value:
            raise ConfigurationError(
                f"credential line {line_number} has an empty value"
            )
        config[key] = value
    missing = REQUIRED_KEYS - config.keys()
    if missing:
        raise ConfigurationError("credential file is missing required keys")
    return config


def _validate_config(config):
    email = config["SMOKE_EMAIL"]
    if (
        "\x00" in email
        or len(email) > 320
        or _EMAIL_RE.fullmatch(email) is None
    ):
        raise ConfigurationError("SMOKE_EMAIL is invalid")
    password = config["SMOKE_PASSWORD"]
    if "\x00" in password or not 1 <= len(password) <= 1024:
        raise ConfigurationError("SMOKE_PASSWORD is invalid")
    totp_secret = config.get("SMOKE_TOTP_SECRET")
    if (
        totp_secret is not None
        and _TOTP_SECRET_RE.fullmatch(totp_secret) is None
    ):
        raise ConfigurationError("SMOKE_TOTP_SECRET is invalid")
    company_id = config["SMOKE_COMPANY_ID"]
    if (
        _COMPANY_ID_RE.fullmatch(company_id) is None
        or int(company_id) > 9223372036854775807
    ):
        raise ConfigurationError("SMOKE_COMPANY_ID is invalid")
    return dict(config)


def load_config(path):
    return _validate_config(_parse_config(_read_private_file(path)))


def _prompt_two_factor_code():
    try:
        code = getpass.getpass("Current 6-digit 2FA code: ")
    except EOFError as error:
        raise ConfigurationError(
            "current 2FA code requires an interactive terminal"
        ) from error
    if _TWO_FACTOR_CODE_RE.fullmatch(code) is None:
        raise ConfigurationError(
            "current 2FA code must contain exactly six digits"
        )
    return code


def build_environment(config, inherited=None, two_factor_code=None):
    environment = dict(os.environ if inherited is None else inherited)
    for key in SENSITIVE_ENV_KEYS:
        environment.pop(key, None)
    environment.update(config)
    if two_factor_code is not None:
        environment["SMOKE_2FA_CODE"] = two_factor_code
    environment["BASE_URL"] = PRODUCTION_BASE_URL
    environment["SMOKE_PROTECTED_ONLY"] = "1"
    environment["SMOKE_BUSINESS_READ_ONLY"] = "1"
    return environment


def _arguments(argv):
    parser = argparse.ArgumentParser(
        description=(
            "Run protected production checks without business write probes."
        ),
    )
    parser.add_argument(
        "--env-file",
        type=Path,
        default=Path(os.getenv("STROYKA_SMOKE_ENV_FILE", DEFAULT_ENV_FILE)),
        help="private credential file (default: /etc/stroyka/prod-smoke.env)",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="validate the credential file without starting the smoke",
    )
    return parser.parse_args(argv)


def main(argv=None):
    arguments = _arguments(argv)
    config = load_config(arguments.env_file)
    if arguments.check:
        print("PROTECTED_SMOKE_CONFIG_OK")
        return 0
    two_factor_code = None
    if "SMOKE_TOTP_SECRET" not in config:
        two_factor_code = _prompt_two_factor_code()
    environment = build_environment(
        config, two_factor_code=two_factor_code,
    )
    os.chdir(Path(__file__).resolve().parent.parent)
    os.execvpe("npm", ["npm", "run", "smoke:prod"], environment)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ConfigurationError as error:
        raise SystemExit(f"PROTECTED_SMOKE_CONFIG_ERROR: {error}") from None
