#!/usr/bin/env python3
"""Add exact tool-deduction API proxies without changing existing locations."""
import argparse
from pathlib import Path
import re

START = '# BEGIN reviewed tool deduction API'
END = '# END reviewed tool deduction API'
ROUTES = ('= /tool-deductions', '^~ /tool-deductions/', '= /salary-tool-deductions')
BODY = '''    proxy_pass http://127.0.0.1:8001;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;'''
BLOCK = START+'\n'+'\n'.join('location '+route+' {\n'+BODY+'\n}' for route in ROUTES)+'\n'+END+'\n\n'

def ensure_routes(text):
    remainder = text.replace(BLOCK, '')
    if START in remainder or END in remainder:
        raise ValueError('Tool deduction proxy block drifted; inspect before applying')
    if re.search(r'(?m)^\s*location[^\n]*(?:tool-deductions|salary-tool-deductions)', remainder):
        raise ValueError('Conflicting tool deduction location; existing config preserved')
    count = text.count(BLOCK)
    if count > 1:
        raise ValueError('Duplicate tool deduction proxy blocks')
    if count == 1:
        return text
    markers = list(re.finditer(r'(?m)^\s*location\s*=\s*/site/pricing\s*\{', text))
    if len(markers) != 1:
        raise ValueError('Expected one known site/pricing server marker')
    pos = markers[0].start()
    return text[:pos]+BLOCK+text[pos:]

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('config',type=Path)
    parser.add_argument('--backup',type=Path,required=True)
    args=parser.parse_args()
    original=args.config.read_text();updated=ensure_routes(original)
    if updated==original:
        print('Tool deduction routes already configured');return
    # Exclusive creation prevents overwriting the only rollback copy.
    with args.backup.open('x') as backup:backup.write(original)
    args.config.write_text(updated)
    print('Three exact tool deduction proxy routes added; run nginx -t before reload')

if __name__=='__main__':main()
