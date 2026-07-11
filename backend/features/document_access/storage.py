import datetime as dt
import hashlib
import hmac
import urllib.error
import urllib.parse
import urllib.request

from fastapi import HTTPException


class NoRedirectHandler(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def _signing_key(secret, date_stamp, region):
    key_date = hmac.new(("AWS4" + secret).encode("utf-8"), date_stamp.encode("utf-8"), hashlib.sha256).digest()
    key_region = hmac.new(key_date, region.encode("utf-8"), hashlib.sha256).digest()
    key_service = hmac.new(key_region, b"s3", hashlib.sha256).digest()
    return hmac.new(key_service, b"aws4_request", hashlib.sha256).digest()


def _close_safely(stream):
    try:
        stream.close()
    except Exception:
        pass


def _signed_s3_request(
    *,
    method,
    key,
    endpoint_url,
    bucket,
    region,
    access_key,
    secret_key,
    now=None,
):
    endpoint_url = str(endpoint_url or "").rstrip("/")
    endpoint = urllib.parse.urlparse(endpoint_url)
    if (
        endpoint.scheme != "https"
        or not endpoint.hostname
        or endpoint.username
        or endpoint.password
        or endpoint.query
        or endpoint.fragment
    ):
        raise HTTPException(status_code=503, detail="Для защищенной S3-выдачи требуется HTTPS endpoint")
    if not bucket or not region or not access_key or not secret_key:
        raise HTTPException(status_code=503, detail="S3-хранилище временно недоступно")

    raw_key = str(key or "").strip()
    normalized_key = raw_key.strip("/")
    if not normalized_key or raw_key != normalized_key or "\\" in normalized_key or "\x00" in normalized_key:
        raise HTTPException(status_code=409, detail="Некорректный путь S3-файла")

    quoted_bucket = urllib.parse.quote(str(bucket), safe="")
    quoted_key = urllib.parse.quote(normalized_key, safe="/")
    url = endpoint_url + "/" + quoted_bucket + "/" + quoted_key
    parsed = urllib.parse.urlparse(url)
    payload_hash = hashlib.sha256(b"").hexdigest()
    current_time = now or dt.datetime.now(dt.timezone.utc)
    amz_date = current_time.strftime("%Y%m%dT%H%M%SZ")
    date_stamp = current_time.strftime("%Y%m%d")
    headers = {
        "host": parsed.netloc,
        "x-amz-content-sha256": payload_hash,
        "x-amz-date": amz_date,
    }
    if method == "GET":
        headers["accept-encoding"] = "identity"
    signed_header_names = sorted(headers)
    canonical_headers = "".join(f"{name}:{headers[name]}\n" for name in signed_header_names)
    signed_headers = ";".join(signed_header_names)
    canonical_request = "\n".join([
        method,
        parsed.path or "/",
        "",
        canonical_headers,
        signed_headers,
        payload_hash,
    ])
    credential_scope = f"{date_stamp}/{region}/s3/aws4_request"
    string_to_sign = "\n".join([
        "AWS4-HMAC-SHA256",
        amz_date,
        credential_scope,
        hashlib.sha256(canonical_request.encode("utf-8")).hexdigest(),
    ])
    signature = hmac.new(
        _signing_key(str(secret_key), date_stamp, str(region)),
        string_to_sign.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    headers["Authorization"] = (
        "AWS4-HMAC-SHA256 "
        f"Credential={access_key}/{credential_scope}, "
        f"SignedHeaders={signed_headers}, Signature={signature}"
    )
    return urllib.request.Request(url, headers=headers, method=method)


def _response_status(response):
    status = getattr(response, "status", None)
    if status is None:
        status = response.getcode()
    try:
        return int(status)
    except (TypeError, ValueError):
        return 0


def open_s3_object(
    *,
    key,
    endpoint_url,
    bucket,
    region,
    access_key,
    secret_key,
    max_bytes,
    opener=None,
    now=None,
    timeout=30,
):
    """Open one bounded S3 object with SigV4 while refusing credential-forwarding redirects."""
    max_bytes = int(max_bytes or 0)
    if max_bytes <= 0:
        raise HTTPException(status_code=503, detail="Лимит размера файла не настроен")
    request = _signed_s3_request(
        method="GET",
        key=key,
        endpoint_url=endpoint_url,
        bucket=bucket,
        region=region,
        access_key=access_key,
        secret_key=secret_key,
        now=now,
    )
    request_opener = opener or urllib.request.build_opener(NoRedirectHandler())
    try:
        response = request_opener.open(request, timeout=timeout)
    except urllib.error.HTTPError as error:
        status = error.code
        _close_safely(error)
        if status == 404:
            raise HTTPException(status_code=404, detail="Файл отсутствует в S3-хранилище") from None
        raise HTTPException(status_code=503, detail="S3-хранилище временно недоступно") from None
    except (urllib.error.URLError, TimeoutError, OSError):
        raise HTTPException(status_code=503, detail="S3-хранилище временно недоступно") from None

    if _response_status(response) != 200:
        _close_safely(response)
        raise HTTPException(status_code=503, detail="S3 вернул неполный ответ")
    content_encoding = str(response.headers.get("Content-Encoding") or "").strip().lower()
    if content_encoding not in ("", "identity"):
        _close_safely(response)
        raise HTTPException(status_code=503, detail="S3 вернул преобразованное содержимое файла")
    raw_length = response.headers.get("Content-Length")
    try:
        content_length = int(raw_length)
    except (TypeError, ValueError):
        _close_safely(response)
        raise HTTPException(status_code=503, detail="S3 не вернул размер файла") from None
    if content_length < 0:
        _close_safely(response)
        raise HTTPException(status_code=503, detail="S3 вернул некорректный размер файла")
    if content_length > max_bytes:
        _close_safely(response)
        raise HTTPException(status_code=413, detail="Файл превышает допустимый размер защищенной выдачи")
    return response, content_length


def delete_s3_object(
    *,
    key,
    endpoint_url,
    bucket,
    region,
    access_key,
    secret_key,
    opener=None,
    now=None,
    timeout=30,
):
    """Delete one S3 object without forwarding signed credentials through redirects."""
    request = _signed_s3_request(
        method="DELETE",
        key=key,
        endpoint_url=endpoint_url,
        bucket=bucket,
        region=region,
        access_key=access_key,
        secret_key=secret_key,
        now=now,
    )
    request_opener = opener or urllib.request.build_opener(NoRedirectHandler())
    try:
        response = request_opener.open(request, timeout=timeout)
    except urllib.error.HTTPError as error:
        status = error.code
        _close_safely(error)
        if status == 404:
            return False
        raise HTTPException(status_code=503, detail="S3 не подтвердил удаление файла") from None
    except (urllib.error.URLError, TimeoutError, OSError):
        raise HTTPException(status_code=503, detail="S3-хранилище временно недоступно") from None
    try:
        if _response_status(response) not in (200, 204):
            raise HTTPException(status_code=503, detail="S3 не подтвердил удаление файла")
        return True
    finally:
        _close_safely(response)
