#!/usr/bin/env python3
"""Validate that Oracle SQL files are read-only and use conservative patterns."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

FORBIDDEN = re.compile(
    r"\b(INSERT|UPDATE|DELETE|MERGE|CREATE|ALTER|DROP|TRUNCATE|GRANT|REVOKE|"
    r"CALL|EXECUTE|BEGIN|DECLARE|COMMIT|ROLLBACK)\b",
    re.IGNORECASE,
)
SELECT_STAR = re.compile(r"\bSELECT\s+(?:\w+\.)?\*", re.IGNORECASE)
BIND = re.compile(r":[A-Za-z][A-Za-z0-9_]*")


def sql_files(target: Path) -> list[Path]:
    if target.is_file():
        return [target]
    return sorted(target.rglob("*.sql"))


def validate(path: Path) -> list[str]:
    text = path.read_text(encoding="utf-8")
    without_comments = re.sub(r"--.*?$|/\*.*?\*/", "", text, flags=re.MULTILINE | re.DOTALL)
    errors: list[str] = []
    statement = without_comments.strip()
    if not statement.upper().startswith("SELECT"):
        errors.append("a instrução deve iniciar com SELECT")
    if FORBIDDEN.search(statement):
        errors.append("contém palavra-chave proibida")
    if SELECT_STAR.search(statement):
        errors.append("contém SELECT *")
    if not re.search(r"^-- name:", text, re.MULTILINE | re.IGNORECASE):
        errors.append("metadado '-- name:' ausente")
    parameters = re.search(
        r"^-- parameters:\s*(.+?)\s*$", text, re.MULTILINE | re.IGNORECASE
    )
    if (
        parameters
        and parameters.group(1).strip().lower() not in {"nenhum", "none"}
        and not BIND.search(statement)
    ):
        errors.append("declara parâmetros, mas não contém bind variable")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("target", type=Path, help="Arquivo SQL ou diretório")
    args = parser.parse_args()
    files = sql_files(args.target)
    if not files:
        print("Nenhum arquivo SQL encontrado.", file=sys.stderr)
        return 2
    failed = False
    for path in files:
        errors = validate(path)
        if errors:
            failed = True
            print(f"REPROVADO {path}: {'; '.join(errors)}")
        else:
            print(f"APROVADO {path}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
