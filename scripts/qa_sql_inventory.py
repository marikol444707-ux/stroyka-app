"""Lossless lexical inventory for the reviewed legacy SQL, not a SQL executor.

Not a general PostgreSQL parser. Ambiguous backslash quoting is rejected.
Classification is separate and must be reviewed for procedural/CTE statements.
"""
import re


def split_statements(sql):
    parts, start, i = [], 0, 0
    while i < len(sql):
        if sql.startswith('--', i):
            end = sql.find('\n', i)
            i = len(sql) if end < 0 else end + 1
        elif sql.startswith('/*', i):
            depth = 1
            i += 2
            while i < len(sql) and depth:
                if sql.startswith('/*', i):
                    depth += 1
                    i += 2
                elif sql.startswith('*/', i):
                    depth -= 1
                    i += 2
                else:
                    i += 1
            if depth:
                raise ValueError('unterminated comment')
        elif sql[i] in "'\"":
            quote = sql[i]
            i += 1
            while i < len(sql):
                if sql[i] == '\\':
                    raise ValueError('backslash quoting requires explicit review')
                if sql[i] == quote:
                    i += 1
                    if i < len(sql) and sql[i] == quote:
                        i += 1
                    else:
                        break
                else:
                    i += 1
            else:
                raise ValueError('unterminated quote')
        elif sql[i] == '$' and (match := re.match(r'\$(?:[A-Za-z_][A-Za-z_0-9]*)?\$', sql[i:])):
            tag = match.group()
            end = sql.find(tag, i + len(tag))
            if end < 0:
                raise ValueError('unterminated dollar quote')
            i = end + len(tag)
        elif sql[i] == ';':
            parts.append(sql[start:i+1])
            i += 1
            start = i
        else:
            i += 1
    if sql[start:].strip():
        raise ValueError('unterminated final statement')
    if parts:
        parts[-1] += sql[start:]
    elif sql:
        raise ValueError('no statements')
    return parts


def leading_keyword(sql):
    # Only line comments occur before statements in this reviewed source.
    text = re.sub(r'(?m)^\s*--[^\n]*(?:\n|$)', '', sql).lstrip()
    match = re.match(r'[A-Za-z]+', text)
    if not match:
        raise ValueError('unreviewed statement prefix')
    return match.group().upper()
