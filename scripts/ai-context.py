"""Offline, bounded module navigation. Never reads application data or secrets."""
from __future__ import annotations
import argparse
import fnmatch
import json
from pathlib import Path, PurePosixPath
import sys

ROOT = Path(__file__).resolve().parents[1]
FULL = ['commercial/tests']


def load(root=ROOT):
    return json.loads((root / 'docs/ai/modules.json').read_text(encoding='utf-8'))['modules']


def validate(modules, root=ROOT):
    errors = []
    for name, module in modules.items():
        for field in ('summary', 'contract'):
            if not isinstance(module.get(field), str) or not 1 <= len(module[field]) <= 700:
                errors.append(f'{name}: invalid/bloated {field}')
        for path in module['entrypoints'] + module['tests']:
            p = PurePosixPath(path)
            if p.is_absolute() or '..' in p.parts or not (root / path).is_file():
                errors.append(f'{name}: missing/unsafe path {path}')
        if not module['tests']:
            errors.append(f'{name}: no tests')
        for dependency in module['depends_on']:
            if dependency not in modules:
                errors.append(f'{name}: unknown dependency {dependency}')
    visiting, visited = set(), set()
    def walk(name):
        if name in visiting:
            errors.append(f'{name}: dependency cycle')
            return
        if name in visited or name not in modules:
            return
        visiting.add(name)
        for dep in modules[name]['depends_on']:
            walk(dep)
        visiting.remove(name)
        visited.add(name)
    for name in modules:
        walk(name)
    return errors


def affected(modules, paths):
    selected, unknown = set(), []
    for original in paths:
        path = original.replace('\\', '/')
        while path.startswith('./'):
            path = path[2:]
        matches = {name for name, m in modules.items()
                   if path in m['tests'] or any(fnmatch.fnmatchcase(path, p) for p in m['owns'])}
        selected.update(matches)
        if not matches:
            unknown.append(path)
    # Include consumers transitively; a shared dependency can affect all its callers.
    while True:
        expanded = selected | {n for n, m in modules.items() if selected.intersection(m['depends_on'])}
        if expanded == selected:
            break
        selected = expanded
    tests = FULL if unknown or not paths else sorted({t for n in selected for t in modules[n]['tests']})
    return {'modules': sorted(selected), 'unknown': unknown, 'tests': tests,
            'command': 'python -m pytest ' + ' '.join(tests) + ' -q',
            'scope': 'Python only; run full CI and relevant browser/live integration gates before release.'}


def card(name, module):
    return '\n'.join([name + ': ' + module['summary'], 'Contract: ' + module['contract'],
        'Read: ' + ', '.join(module['entrypoints']),
        'Dependencies: ' + (', '.join(module['depends_on']) or 'none'),
        'Tests: python -m pytest ' + ' '.join(module['tests']) + ' -q'])


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['list', 'show', 'check', 'affected'])
    parser.add_argument('items', nargs='*')
    parser.add_argument('--max-chars', type=int, default=6000)
    args = parser.parse_args(argv)
    if not 256 <= args.max_chars <= 12000:
        parser.error('--max-chars must be between 256 and 12000')
    modules = load()
    errors = validate(modules)
    if errors:
        print('\n'.join(errors), file=sys.stderr)
        return 1
    if args.command == 'check':
        output = f'{len(modules)} module contracts validated (paths/dependencies/budgets; not runtime behavior).'
    elif args.command == 'list':
        output = '\n'.join(n + ': ' + m['summary'] for n, m in modules.items())
    elif args.command == 'affected':
        output = json.dumps(affected(modules, args.items), indent=2)
    else:
        if not args.items or any(n not in modules for n in args.items):
            parser.error('show requires known module names; run list')
        output = '\n\n'.join(card(n, modules[n]) for n in args.items)
    if len(output) > args.max_chars:
        print('Context budget exceeded; request fewer modules. No partial contract emitted.', file=sys.stderr)
        return 2
    print(output)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
