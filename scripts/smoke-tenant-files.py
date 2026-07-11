#!/usr/bin/env python3
import base64
import hashlib
import hmac
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
API = os.getenv("SMOKE_API", "https://stroyka26.pro").rstrip("/")


def env_value(name):
    value = os.getenv(name, "").strip()
    if value:
        return value
    env_path = ROOT / "backend" / ".env"
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            if line.strip().startswith(name + "="):
                return line.split("=", 1)[1].strip().strip('"').strip("'")
    return ""


def api(method, path, *, token="", data=None, body=None, headers=None, expected=200):
    request_headers = dict(headers or {})
    if token:
        request_headers["Authorization"] = "Bearer " + token
    if data is not None:
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        request_headers["Content-Type"] = "application/json"
    request = urllib.request.Request(API + path, data=body, headers=request_headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=45) as response:
            status = response.status
            raw = response.read()
    except urllib.error.HTTPError as error:
        status = error.code
        raw = error.read()
    text = raw.decode("utf-8", errors="replace")
    if status != expected:
        raise RuntimeError(f"{method} {path}: got {status}, expected {expected}. Body: {text[:900]}")
    if not text:
        return {}
    try:
        return json.loads(text)
    except json.JSONDecodeError as error:
        response_kind = "HTML от nginx/SPA" if re.search(r"<!doctype|<html", text, re.IGNORECASE) else "не JSON"
        raise RuntimeError(
            f"{method} {path}: HTTP {status}, ожидался JSON, получен {response_kind}. Body: {text[:900]}"
        ) from error


def api_bytes(method, path, *, token="", headers=None, expected=200):
    request_headers = dict(headers or {})
    if token:
        request_headers["Authorization"] = "Bearer " + token
    request = urllib.request.Request(API + path, headers=request_headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=45) as response:
            status = response.status
            raw = response.read()
            response_headers = {key.lower(): value for key, value in response.headers.items()}
    except urllib.error.HTTPError as error:
        status = error.code
        raw = error.read()
        response_headers = {key.lower(): value for key, value in error.headers.items()}
    if status != expected:
        text = raw.decode("utf-8", errors="replace")
        raise RuntimeError(f"{method} {path}: got {status}, expected {expected}. Body: {text[:900]}")
    return raw, response_headers


def fetch_url(url):
    absolute_url = urllib.parse.urljoin(API + "/", str(url or ""))
    request = urllib.request.Request(absolute_url, method="GET")
    try:
        with urllib.request.urlopen(request, timeout=45) as response:
            return response.status, response.read()
    except urllib.error.HTTPError as error:
        return error.code, error.read()


def wait_until_storage_is_gone(url, attempts=5):
    last_status = None
    for attempt in range(attempts):
        last_status, _raw = fetch_url(url)
        if last_status in (404, 410):
            return
        if attempt + 1 < attempts:
            time.sleep(1)
    raise RuntimeError(f"Физический файл остался доступен после cleanup: HTTP {last_status}")


def totp_code(secret):
    secret = re.sub(r"\s+", "", str(secret or "")).upper()
    secret += "=" * (-len(secret) % 8)
    key = base64.b32decode(secret, casefold=True)
    counter = int(time.time()) // 30
    digest = hmac.new(key, counter.to_bytes(8, "big"), hashlib.sha1).digest()
    offset = digest[-1] & 0x0F
    return str((int.from_bytes(digest[offset:offset + 4], "big") & 0x7FFFFFFF) % 1000000).zfill(6)


def login(email, password):
    body = api("POST", "/login", data={"email": email, "password": password})
    if body.get("authToken"):
        return body["authToken"]
    if body.get("twoFactorSetupRequired"):
        secret = env_value("SMOKE_TOTP_SECRET") or body.get("manualKey") or ""
        confirmed = api("POST", "/login/2fa/setup-confirm", data={
            "setupToken": body.get("setupToken"),
            "code": totp_code(secret),
        })
        return confirmed.get("authToken") or ""
    if body.get("twoFactorRequired"):
        code = env_value("SMOKE_2FA_CODE") or (totp_code(env_value("SMOKE_TOTP_SECRET")) if env_value("SMOKE_TOTP_SECRET") else "")
        if not code:
            raise SystemExit("FAIL login: задайте SMOKE_2FA_CODE или SMOKE_TOTP_SECRET")
        verified = api("POST", "/login/2fa/verify", data={
            "challengeToken": body.get("challengeToken"),
            "code": code,
        })
        return verified.get("authToken") or ""
    raise SystemExit("FAIL login: authToken не получен")


def multipart(fields, filename, content, content_type="image/png"):
    boundary = "----stroyka-smoke-" + uuid.uuid4().hex
    chunks = []
    for name, value in fields.items():
        chunks.extend([
            f"--{boundary}\r\n".encode(),
            f'Content-Disposition: form-data; name="{name}"\r\n\r\n'.encode(),
            str(value).encode("utf-8"), b"\r\n",
        ])
    chunks.extend([
        f"--{boundary}\r\n".encode(),
        f'Content-Disposition: form-data; name="file"; filename="{filename}"\r\n'.encode(),
        f"Content-Type: {content_type}\r\n\r\n".encode(),
        content, b"\r\n", f"--{boundary}--\r\n".encode(),
    ])
    return b"".join(chunks), "multipart/form-data; boundary=" + boundary


def main():
    email = env_value("SMOKE_EMAIL")
    password = env_value("SMOKE_PASSWORD")
    if not email or not password:
        raise SystemExit("Нужно задать SMOKE_EMAIL и SMOKE_PASSWORD")
    token = login(email, password)
    projects = api("GET", "/projects", token=token)
    project = next((item for item in projects if "CODEX" in str(item.get("name") or "").upper()), projects[0] if projects else None)
    if not project or not project.get("id") or not project.get("companyId"):
        raise SystemExit("FAIL: нет доступного объекта с companyId")
    company_id = int(project["companyId"])
    headers = {"X-Company-Id": str(company_id)}
    file_id = None
    try:
        png = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII=")
        fields = {
            "projectId": project["id"],
            "projectName": project.get("name") or "",
            "context": "smoke-tenant-files",
        }
        body, content_type = multipart(fields, "codex-tenant-file-smoke.png", png)
        uploaded = api("POST", "/upload-photo", token=token, body=body, headers={**headers, "Content-Type": content_type})
        file_id = uploaded.get("fileId")
        if not file_id:
            raise RuntimeError("upload-photo не вернул fileId")
        if int(uploaded.get("companyId") or 0) != company_id or int(uploaded.get("projectId") or 0) != int(project["id"]):
            raise RuntimeError("Файл получил неверную компанию или объект")
        metadata = api("GET", f"/tenant-files/{file_id}", token=token, headers=headers)
        if metadata.get("context") != "smoke-tenant-files" or int(metadata.get("companyId") or 0) != company_id:
            raise RuntimeError("Метаданные tenant-файла не совпали")
        expected_content_url = f"/tenant-files/{file_id}/content"
        if uploaded.get("contentUrl") != expected_content_url or metadata.get("contentUrl") != expected_content_url:
            raise RuntimeError("Сервер не вернул защищенный URL файла")
        protected_content, protected_headers = api_bytes(
            "GET",
            expected_content_url,
            token=token,
            headers=headers,
        )
        if hashlib.sha256(protected_content).digest() != hashlib.sha256(png).digest():
            raise RuntimeError("Защищенная выдача вернула другое содержимое файла")
        if not protected_headers.get("content-type", "").lower().startswith("image/png"):
            raise RuntimeError("Защищенная выдача вернула неверный Content-Type")
        if protected_headers.get("cache-control", "").lower() != "private, no-store":
            raise RuntimeError("Защищенная выдача не запретила публичное кеширование")
        compatibility_url = uploaded.get("url") or metadata.get("url")
        compatibility_status, compatibility_content = fetch_url(compatibility_url)
        if compatibility_status != 200 or hashlib.sha256(compatibility_content).digest() != hashlib.sha256(png).digest():
            raise RuntimeError("Compatibility URL не вернул загруженный физический файл")
        api("DELETE", f"/tenant-files/{file_id}", token=token, headers=headers)
        api("GET", f"/tenant-files/{file_id}", token=token, headers=headers, expected=404)
        api_bytes("GET", f"/tenant-files/{file_id}/content", token=token, headers=headers, expected=404)
        file_id = None
        wait_until_storage_is_gone(compatibility_url)
        print(json.dumps({
            "ok": True,
            "projectId": project["id"],
            "projectName": project.get("name"),
            "companyId": company_id,
            "checked": [
                "authenticated multipart upload",
                "stored company/project ownership",
                "authorized metadata read",
                "authorized protected content read with exact bytes",
                "physical object and ownership cleanup",
                "deleted metadata/content return 404 and compatibility object disappears",
            ],
        }, ensure_ascii=False, indent=2))
    finally:
        active_error = sys.exc_info()[1]
        if file_id:
            try:
                api("DELETE", f"/tenant-files/{file_id}", token=token, headers=headers)
                print(f"cleanup: removed tenant file {file_id}")
            except Exception as error:
                if active_error:
                    raise RuntimeError(f"Основная ошибка: {active_error}; cleanup тоже не выполнен: {error}") from error
                raise RuntimeError(f"Cleanup tenant-файла {file_id} не выполнен: {error}") from error


if __name__ == "__main__":
    main()
