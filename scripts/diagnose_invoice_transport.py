#!/usr/bin/env python3
"""Compare synthetic invoice image/PDF requests; never reads or posts business data."""
import argparse
import base64
import io
import json
import logging
import os
from pathlib import Path
import re
import shlex
import subprocess
import sys


def synthetic_parts():
    from PIL import Image, ImageDraw
    image = Image.new('RGB', (640, 240), 'white')
    ImageDraw.Draw(image).text((24, 24), 'SYNTHETIC INVOICE\nCEMENT\nQuantity: 2', fill='black')
    png, pdf = io.BytesIO(), io.BytesIO()
    image.save(png, format='PNG')
    image.save(pdf, format='PDF')
    return ('data:image/png;base64,' + base64.b64encode(png.getvalue()).decode('ascii'),
            'data:application/pdf;base64,' + base64.b64encode(pdf.getvalue()).decode('ascii'))


def safe_synthetic_error(error, secrets):
    """Only for errors of this script's synthetic input, never a real invoice."""
    status = getattr(error, 'status_code', None)
    result = {'httpStatus': status if type(status) is int and 400 <= status <= 599 else None}
    allowed = ('BadRequestError', 'AuthenticationError', 'PermissionDeniedError', 'NotFoundError',
               'RateLimitError', 'InternalServerError', 'APIConnectionError', 'APITimeoutError')
    name = type(error).__name__
    result['exceptionType'] = name if name in allowed else 'other'
    body = getattr(error, 'body', None)
    if type(body) not in (dict, list, str):
        result['syntheticErrorDetail'] = 'no_structured_error_body'
        return result
    try:
        message = json.dumps(body, ensure_ascii=True)
    except (ValueError, TypeError):
        result['syntheticErrorDetail'] = 'unserializable_error_body'
        return result
    for value in sorted((value for value in secrets if type(value) is str and value), key=len, reverse=True):
        message = message.replace(value, '[redacted]').replace(json.dumps(value)[1:-1], '[redacted]')
    message = re.sub(r'data:[^\s"\']+', '[synthetic-data]', message)
    message = re.sub(r'(?i)(?:api[-_ ]?key|bearer)[ :"=]+[A-Za-z0-9._/-]+', '[credential]', message)
    result['syntheticErrorDetail'] = message[:1200]
    return result


def probe(api_key, folder_id, *, client=None, parts_factory=synthetic_parts):
    from backend.features.model_gateway.yandex_adapter import _provider_input, YANDEX_CAPABILITY_MODELS
    from backend.features.model_gateway.contract import ModelInputPart, build_model_request
    report = {'syntheticOnly': True, 'databaseAccess': False, 'warehouseWrites': False, 'cases': []}
    if not api_key or not folder_id:
        return dict(report, error='model_credentials_missing')
    model = YANDEX_CAPABILITY_MODELS['invoice_scan'][0]
    if client is None:
        from openai import OpenAI
        client = OpenAI(api_key=api_key, project=folder_id,
                        base_url='https://ai.api.cloud.yandex.net/v1', max_retries=0)
    png, pdf = parts_factory()
    text = ModelInputPart('text', 'Return JSON with the quantity of CEMENT in this synthetic invoice.')
    cases = (
        ('text_only', (text,)),
        ('two_images', (text, ModelInputPart('image_data_url', png), ModelInputPart('image_data_url', png))),
        ('two_images_and_pdf', (text, ModelInputPart('image_data_url', png), ModelInputPart('image_data_url', png),
                                ModelInputPart('file_data_url', pdf, 'synthetic-invoice.pdf'))),
    )
    for name, parts in cases:
        item = {'case': name, 'model': model}
        try:
            request = build_model_request(capability='invoice_scan', instructions='Read the synthetic invoice. Return JSON only.',
                                          input_parts=parts, temperature=.1, max_output_tokens=12000, deadline_seconds=20)
            response = client.responses.create(model='gpt://' + folder_id + '/' + model,
                                               temperature=request.temperature, instructions=request.instructions,
                                               input=_provider_input(request), max_output_tokens=request.max_output_tokens,
                                               timeout=float(request.deadline_seconds))
            output = getattr(response, 'output_text', None)
            item['result'] = 'accepted' if type(output) is str and output.strip() else 'empty_output'
        except Exception as error:
            item['result'] = 'rejected'
            item.update(safe_synthetic_error(error, (api_key, folder_id)))
        report['cases'].append(item)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--app-root', type=Path, default=Path('/var/www/stroyka-app'))
    parser.add_argument('--service', default='stroyka')
    parser.add_argument('--probe', action='store_true', help='Send three synthetic model calls; model usage may be billed.')
    parser.add_argument('--runtime-env', action='store_true', help=argparse.SUPPRESS)
    args = parser.parse_args()
    if not args.probe:
        print(json.dumps({'state': 'not_run', 'syntheticOnly': True, 'databaseAccess': False, 'warehouseWrites': False}))
        return 0
    try:
        root = args.app_root.resolve()
        os.chdir(root)
        sys.path.insert(0, str(root))
        if not args.runtime_env:
            from scripts.unified_release import runtime_environment
            env = runtime_environment(root, args.service)
            header = Path('/usr/local/bin/uvicorn').read_text().splitlines()[0]
            if not header.startswith('#!'):
                raise ValueError('interpreter unavailable')
            interpreter = shlex.split(header[2:])
            command = [*interpreter, '-B', str(Path(__file__).resolve()), '--runtime-env', '--probe', '--app-root', str(root)]
            result = subprocess.run(command, cwd=root, env=env, capture_output=True, text=True, timeout=80)
            # Only forward a valid diagnostic JSON report, never raw child stderr.
            report = json.loads(result.stdout)
            print(json.dumps(report))
            return result.returncode
        logging.disable(logging.CRITICAL)
        report = probe(os.environ.get('YANDEX_API_KEY', ''), os.environ.get('YANDEX_FOLDER_ID', ''))
        print(json.dumps(report))
        return 0
    except Exception:
        print(json.dumps({'error': 'synthetic_probe_unavailable', 'warehouseWrites': False}))
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
