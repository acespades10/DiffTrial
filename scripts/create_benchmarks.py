"""Materialize the twelve original, versioned DiffTrial tasks and protected tests."""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPECS = [
    (
        "py-intervals",
        "Merge touching intervals",
        "python",
        "Merge sorted or unsorted closed intervals, including intervals that share an endpoint. Do not mutate the input.",
        "def repair(items):\n    result = []\n    for start, end in sorted(items):\n        if result and start < result[-1][1]:\n            result[-1][1] = max(result[-1][1], end)\n        else:\n            result.append([start, end])\n    return result\n",
        "assert repair([[1, 3], [2, 4]]) == [[1, 4]]",
        "assert repair([[4, 7], [1, 4], [9, 9]]) == [[1, 7], [9, 9]]\n    assert repair([]) == []",
        "start < result[-1][1]",
        "start <= result[-1][1]",
    ),
    (
        "py-weighted",
        "Honor zero weights",
        "python",
        "Return the weighted mean of (value, weight) pairs. Zero weights contribute nothing. Reject a nonpositive total weight with ValueError.",
        "def repair(items):\n    total = sum(weight or 1 for _, weight in items)\n    if total <= 0:\n        raise ValueError('positive total required')\n    return sum(value * (weight or 1) for value, weight in items) / total\n",
        "assert repair([(10, 1), (20, 1)]) == 15",
        "assert repair([(100, 0), (6, 2)]) == 6\n    import pytest\n    with pytest.raises(ValueError):\n        repair([(5, 0)])",
        "weight or 1",
        "weight",
    ),
    (
        "py-pages",
        "Keep the final partial page",
        "python",
        "Split values into pages of size n. Retain a partial final page. Reject n <= 0 with ValueError.",
        "def repair(values, n):\n    if n <= 0:\n        raise ValueError('positive size required')\n    return [values[i:i+n] for i in range(0, len(values) - n + 1, n)]\n",
        "assert repair([1, 2, 3, 4], 2) == [[1, 2], [3, 4]]",
        "assert repair([1, 2, 3], 2) == [[1, 2], [3]]\n    assert repair([1], 3) == [[1]]\n    assert repair([], 2) == []",
        "len(values) - n + 1",
        "len(values)",
    ),
    (
        "py-expiry",
        "Expire at the deadline",
        "python",
        "Return keys whose expiration time is strictly later than now. A key expires exactly at its deadline; preserve insertion order.",
        "def repair(expirations, now):\n    return [key for key, expiry in expirations.items() if expiry >= now]\n",
        "assert repair({'a': 10, 'b': 2}, 5) == ['a']",
        "assert repair({'a': 5, 'b': 6, 'c': 5}, 5) == ['b']\n    assert repair({}, 0) == []",
        "expiry >= now",
        "expiry > now",
    ),
    (
        "py-unicode",
        "Match Unicode identifiers",
        "python",
        "Group identifiers case-insensitively using Unicode casefold after NFC normalization. Preserve the original strings and insertion order in each group.",
        "import unicodedata\n\ndef repair(values):\n    groups = {}\n    for value in values:\n        key = unicodedata.normalize('NFC', value).lower()\n        groups.setdefault(key, []).append(value)\n    return groups\n",
        "assert repair(['Ace', 'ACE']) == {'ace': ['Ace', 'ACE']}",
        "assert repair(['Straße', 'STRASSE']) == {'strasse': ['Straße', 'STRASSE']}\n    assert repair(['é', 'e\\u0301']) == {'é': ['é', 'e\\u0301']}",
        ".lower()",
        ".casefold()",
    ),
    (
        "py-ledger",
        "Retain zero-value ledger entries",
        "python",
        "Return entries with a non-null amount. Zero is a valid amount. Do not mutate entries or drop negative adjustments.",
        "def repair(entries):\n    return [entry for entry in entries if entry.get('amount')]\n",
        "assert repair([{'amount': 3}, {'amount': None}]) == [{'amount': 3}]",
        "assert repair([{'amount': 0}, {'amount': -2}, {}]) == [{'amount': 0}, {'amount': -2}]",
        "if entry.get('amount')",
        "if entry.get('amount') is not None",
    ),
    (
        "ts-versions",
        "Compare numeric version segments",
        "typescript",
        "Compare dotted numeric version strings. Return -1, 0 or 1. Missing segments are zero; compare segments numerically, not lexicographically.",
        "export function repair(a: string, b: string): number {\n  const left = a.split('.');\n  const right = b.split('.');\n  for (let i = 0; i < Math.max(left.length, right.length); i++) {\n    const x = left[i] ?? '0', y = right[i] ?? '0';\n    if (x !== y) return x < y ? -1 : 1;\n  }\n  return 0;\n}\n",
        "expect(repair('1.2', '1.3')).toBe(-1);",
        "expect(repair('1.10', '1.2')).toBe(1);\n  expect(repair('1', '1.0.0')).toBe(0);",
        "const x = left[i] ?? '0', y = right[i] ?? '0';",
        "const x = Number(left[i] ?? '0'), y = Number(right[i] ?? '0');",
    ),
    (
        "ts-capacity",
        "Respect an empty queue capacity",
        "typescript",
        "Return up to capacity values from the start. Capacity zero returns no items, and negative capacity raises RangeError.",
        "export function repair<T>(items: T[], capacity: number): T[] {\n  if (capacity < 0) throw new RangeError('negative capacity');\n  return items.slice(0, capacity || items.length);\n}\n",
        "expect(repair([1, 2, 3], 2)).toEqual([1, 2]);",
        "expect(repair([1, 2], 0)).toEqual([]);\n  expect(() => repair([1], -1)).toThrow(RangeError);",
        "capacity || items.length",
        "capacity",
    ),
    (
        "ts-dates",
        "Advance dates across month boundaries",
        "typescript",
        "Given an ISO UTC date, return the ISO UTC date the next day. Handle month, year and leap-day boundaries without using local time.",
        "export function repair(day: string): string {\n  const date = new Date(day + 'T00:00:00Z');\n  date.setUTCDate(date.getUTCDate() + 1);\n  return day.slice(0, 8) + String(date.getUTCDate()).padStart(2, '0');\n}\n",
        "expect(repair('2024-02-10')).toBe('2024-02-11');",
        "expect(repair('2024-02-29')).toBe('2024-03-01');\n  expect(repair('2024-12-31')).toBe('2025-01-01');",
        "day.slice(0, 8) + String(date.getUTCDate()).padStart(2, '0')",
        "date.toISOString().slice(0, 10)",
    ),
    (
        "ts-records",
        "Keep the newest duplicate record",
        "typescript",
        "Deduplicate records by id, retaining the last value for each id. The order of ids follows their first appearance. Do not mutate input.",
        "export function repair(items: {id: string; value: number}[]) {\n  const found = new Map<string, {id: string; value: number}>();\n  for (const item of items) {\n    if (!found.has(item.id)) found.set(item.id, item);\n  }\n  return [...found.values()];\n}\n",
        "expect(repair([{id: 'a', value: 1}])).toEqual([{id: 'a', value: 1}]);",
        "expect(repair([{id: 'a', value: 1}, {id: 'b', value: 2}, {id: 'a', value: 3}])).toEqual([{id: 'a', value: 3}, {id: 'b', value: 2}]);",
        "if (!found.has(item.id)) found.set(item.id, item);",
        "found.set(item.id, item);",
    ),
    (
        "ts-chunks",
        "Keep a trailing chunk",
        "typescript",
        "Split items into chunks of positive integer size. Keep a partial final chunk and reject zero, negative or fractional sizes with RangeError.",
        "export function repair<T>(items: T[], size: number): T[][] {\n  if (!Number.isInteger(size) || size <= 0) throw new RangeError('invalid size');\n  const result: T[][] = [];\n  for (let i = 0; i + size <= items.length; i += size) result.push(items.slice(i, i + size));\n  return result;\n}\n",
        "expect(repair([1, 2, 3, 4], 2)).toEqual([[1, 2], [3, 4]]);",
        "expect(repair([1, 2, 3], 2)).toEqual([[1, 2], [3]]);\n  expect(() => repair([1], 0)).toThrow(RangeError);",
        "i + size <= items.length",
        "i < items.length",
    ),
    (
        "ts-average",
        "Divide a partial window correctly",
        "typescript",
        "Return a trailing moving average for each position using up to window items. Divide by the available item count in the initial partial windows. Reject nonpositive or fractional windows.",
        "export function repair(values: number[], window: number): number[] {\n  if (!Number.isInteger(window) || window <= 0) throw new RangeError('invalid window');\n  return values.map((_, i) => {\n    const slice = values.slice(Math.max(0, i - window + 1), i + 1);\n    return slice.reduce((a, b) => a + b, 0) / window;\n  });\n}\n",
        "expect(repair([2, 4], 1)).toEqual([2, 4]);",
        "expect(repair([2, 4, 6], 3)).toEqual([2, 3, 4]);\n  expect(repair([], 3)).toEqual([]);",
        "/ window",
        "/ slice.length",
    ),
]


def main():
    catalog, fixtures = [], {}
    for ident, title, profile, issue, code, existing, regression, old, new in SPECS:
        folder = ROOT / "benchmarks" / ident
        (folder / "src").mkdir(parents=True, exist_ok=True)
        (folder / "tests").mkdir(exist_ok=True)
        ext = "py" if profile == "python" else "ts"
        (folder / "src" / f"repair.{ext}").write_text(code, encoding="utf-8", newline="\n")
        for name, assertions in [("existing", existing), ("regression", regression)]:
            if profile == "python":
                text = f"from src.repair import repair\n\ndef test_{name}():\n    {assertions}\n"
                filename = f"test_{name}.py"
            else:
                text = f"import {{ expect, test }} from 'vitest';\nimport {{ repair }} from '../src/repair';\ntest('{name}', () => {{\n  {assertions}\n}});\n"
                filename = f"{name}.test.ts"
            (folder / "tests" / filename).write_text(text, encoding="utf-8", newline="\n")
        if profile == "python":
            for name in ("requirements.txt", "requirements.lock"):
                (folder / name).write_text(
                    "# No project dependencies. pytest and ruff are pinned in the runner image.\n"
                )
        else:
            (folder / "package.json").write_text(
                json.dumps(
                    {
                        "name": ident,
                        "version": "1.0.0",
                        "private": True,
                        "type": "module",
                        "devDependencies": {"vitest": "5.1.0", "typescript": "5.9.3"},
                    },
                    indent=2,
                )
                + "\n"
            )
        catalog.append(
            {
                "id": ident,
                "title": title,
                "profile": profile,
                "issue": issue,
                "version": "1.0.0",
                "protected_tests": ["tests/"],
                "category": "boundary_and_data_integrity",
            }
        )
        fixtures[ident] = {"path": f"src/repair.{ext}", "content": code.replace(old, new)}
    (ROOT / "benchmarks" / "catalog.json").write_text(json.dumps(catalog, indent=2) + "\n")
    (ROOT / "tests" / "fixtures").mkdir(parents=True, exist_ok=True)
    (ROOT / "tests" / "fixtures" / "repairs.json").write_text(
        json.dumps(fixtures, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )


if __name__ == "__main__":
    main()
