# Os códigos foram gerados com auxilio de I.A.
import sys
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

HEADER_PYTHON = "# Os códigos foram gerados com auxilio de I.A."
HEADER_HTML = "<!-- Os códigos foram gerados com auxilio de I.A. -->"
HEADER_CSS_JS = "/* Os códigos foram gerados com auxilio de I.A. */"

HEADER_MAP = {
    ".py": HEADER_PYTHON,
    ".sh": HEADER_PYTHON,
    ".env.example": HEADER_PYTHON,
    ".yaml": HEADER_PYTHON,
    ".yml": HEADER_PYTHON,
    ".html": HEADER_HTML,
    ".css": HEADER_CSS_JS,
    ".js": HEADER_CSS_JS,
}

IGNORE_DIRS = {
    ".venv", "venv", ".git", "__pycache__", "migrations", ".system_generated",
    ".idea", ".vscode", "static_collected", "node_modules"
}

IGNORE_FILES = {
    ".gitignore", "db.sqlite3", "requirements.txt"
}


def should_process(file_path: Path) -> bool:
    for part in file_path.parts:
        if part in IGNORE_DIRS:
            return False
    if file_path.name in IGNORE_FILES:
        return False
    if file_path.suffix in HEADER_MAP:
        return True
    if file_path.name == ".env.example":
        return True
    return False


def has_ai_header(content: str, ext: str) -> bool:
    expected = HEADER_MAP.get(ext, "")
    if not expected:
        return True
    first_lines = "\n".join(content.strip().splitlines()[:5])
    if "Os códigos foram gerados com auxilio de I.A." in first_lines:
        return True
    return False


def apply_ai_header(file_path: Path) -> bool:
    try:
        content = file_path.read_text(encoding="utf-8")
    except Exception as exc:
        print(f"Erro ao ler {file_path}: {exc}")
        return False

    ext = file_path.suffix
    if ext == "" and file_path.name == ".env.example":
        ext = ".env.example"

    if has_ai_header(content, ext):
        return False

    header = HEADER_MAP.get(ext, "")
    if not header:
        return False

    new_content = f"{header}\n{content}"
    file_path.write_text(new_content, encoding="utf-8")
    return True


def check_all_files(target_dirs=None, auto_apply=False):
    if target_dirs is None:
        target_dirs = ["apps", "hub", "templates", "scripts", "manage.py"]

    missing = []
    applied = []
    checked_count = 0

    for target in target_dirs:
        p = BASE_DIR / target
        if not p.exists():
            continue
        if p.is_file():
            files = [p]
        else:
            files = [f for f in p.rglob("*") if f.is_file()]

        for f in files:
            if not should_process(f):
                continue

            checked_count += 1
            ext = f.suffix
            if ext == "" and f.name == ".env.example":
                ext = ".env.example"

            content = f.read_text(encoding="utf-8")
            if not has_ai_header(content, ext):
                if auto_apply:
                    apply_ai_header(f)
                    applied.append(f)
                else:
                    missing.append(f)

    if auto_apply and applied:
        print(f"[OK] Cabeçalho de I.A. adicionado em {len(applied)} arquivo(s):")
        for f in applied:
            print(f"  + {f.relative_to(BASE_DIR)}")

    if missing:
        print(f"[ERRO] {len(missing)} arquivo(s) sem cabeçalho obrigatório de I.A.:")
        for f in missing:
            print(f"  - {f.relative_to(BASE_DIR)}")
        print("\nExecute 'python scripts/check_ai_header.py --apply' para adicionar automaticamente.")
        return False

    print(f"[SUCESSO] Todos os {checked_count} arquivos verificados possuem o cabeçalho de I.A. em conformidade.")
    return True


if __name__ == "__main__":
    auto_apply = "--apply" in sys.argv or "-a" in sys.argv
    success = check_all_files(auto_apply=auto_apply)
    sys.exit(0 if success else 1)