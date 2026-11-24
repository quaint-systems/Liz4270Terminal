# Copyright (c) 2026, CoffeeMuse
# SPDX-License-Identifier: ISC

"""KiCad's S-expressions: parse() to nested lists, dump() back to text.

An atom is a str. A quoted atom parses to Q, a str subclass, so dump() quotes it
again; a bare atom stays a plain str. Parsed numbers stay strings; dump() formats
int and float values itself, and writes True and False as yes and no.
"""

import re

_TOKENS = re.compile(r'\(|\)|"(?:\\.|[^"\\])*"|[^\s()"]+')
_ESCAPES = {'"': '"', '\\': '\\', 'n': '\n'}


class Q(str):
    """A quoted string atom."""


def _unquote(token):
    return Q(re.sub(r'\\(.)', lambda m: _ESCAPES.get(m.group(1), m.group(1)), token[1:-1]))


def parse(text):
    """The one S-expression in text, as nested lists."""
    stack = [[]]
    for token in _TOKENS.findall(text):
        if token == '(':
            stack.append([])
        elif token == ')':
            if len(stack) == 1:
                raise ValueError('unbalanced S-expression: too many )')
            done = stack.pop()
            stack[-1].append(done)
        elif token.startswith('"'):
            stack[-1].append(_unquote(token))
        else:
            stack[-1].append(token)
    if len(stack) != 1 or not stack[0]:
        raise ValueError('unbalanced S-expression: missing )')
    if len(stack[0]) > 1:
        raise ValueError('content after the first S-expression')
    return stack[0][0]


def number(x):
    """x as KiCad writes a coordinate: at most 4 decimals, no trailing zeros."""
    if isinstance(x, int):
        return str(x)
    text = f'{x:.4f}'.rstrip('0').rstrip('.')
    return '0' if text in ('-0', '') else text


def _atom(x):
    if isinstance(x, Q):
        return '"' + x.replace('\\', '\\\\').replace('"', '\\"').replace('\n', '\\n') + '"'
    if isinstance(x, bool):
        return 'yes' if x else 'no'
    if isinstance(x, (int, float)):
        return number(x)
    return x


def dump(expr, depth=0):
    """expr as text: a list of atoms on one line; a list holding lists over several, tab-indented."""
    if not isinstance(expr, list):
        return _atom(expr)
    split = next((i for (i, item) in enumerate(expr) if isinstance(item, list)), len(expr))
    head = '(' + ' '.join(_atom(a) for a in expr[:split])
    if split == len(expr):
        return head + ')'
    pad = '\t' * (depth + 1)
    lines = [head] + [pad + dump(item, depth + 1) for item in expr[split:]]
    return '\n'.join(lines) + '\n' + '\t' * depth + ')'


def find(expr, head):
    """The first child list of expr whose first atom is head, or None."""
    return next((item for item in expr[1:] if isinstance(item, list) and item and item[0] == head), None)


def find_all(expr, head):
    """Every child list of expr whose first atom is head."""
    return [item for item in expr[1:] if isinstance(item, list) and item and item[0] == head]
