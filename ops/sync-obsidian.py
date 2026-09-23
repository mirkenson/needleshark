#!/usr/bin/env python3
"""Export the committed Git tree to Obsidian, preserving manual edits."""

import argparse
import hashlib
import io
import json
import re
import subprocess
import tarfile
import tempfile
from pathlib import Path, PurePosixPath
from urllib.parse import quote


REPO = Path(__file__).resolve().parents[1]
DEFAULT_PROJECT = Path.home() / "Documents/Sazonov BD/1 ПРОЕКТЫ/Needle Shark"
MIRROR = "Сайт/Материалы из Git"
MANIFEST = "Сайт/Синхронизация Git.json"


def git(repo, *args):
    return subprocess.check_output(["git", "-C", str(repo), *args])


def sha(data):
    return hashlib.sha256(data).hexdigest()


def fenced(text, language="json"):
    longest = max((len(x) for x in re.findall(r"`+", text)), default=0)
    fence = "`" * max(3, longest + 1)
    return f"{fence}{language}\n{text.rstrip()}\n{fence}\n"


def snapshot(repo):
    if git(repo, "status", "--porcelain", "--untracked-files=no").strip():
        raise ValueError("Сначала сохраните изменения отслеживаемых файлов в коммит.")
    commit = git(repo, "rev-parse", "HEAD").decode().strip()
    files = {}
    with tarfile.open(fileobj=io.BytesIO(git(repo, "archive", "--format=tar", commit))) as archive:
        for member in archive:
            if member.isdir():
                continue
            path = PurePosixPath(member.name)
            if not member.isfile() or path.is_absolute() or ".." in path.parts:
                raise ValueError(f"Неподдерживаемый путь Git: {member.name}")
            name = path.name.lower()
            # Examples are public documentation; actual credentials/data never belong here.
            if (name == ".env" or (name.startswith(".env.") and not name.endswith(".example"))
                    or name.endswith((".key", ".pem", ".p12", ".pfx", ".sqlite3", ".dump"))
                    or (name.endswith(".env") and not name.endswith(".example"))):
                raise ValueError(f"Проверьте потенциально закрытый файл в Git: {member.name}")
            files[member.name] = archive.extractfile(member).read()
    tracked = set(git(repo, "ls-tree", "-rz", "--name-only", commit).decode().rstrip("\0").split("\0"))
    if set(files) != tracked:
        raise ValueError("Архив отличается от дерева Git; проверьте export-ignore и подмодули.")
    return commit, files


def export_files(repo, commit, sources):
    result = {f"{MIRROR}/{name}": data for name, data in sources.items()}
    # Keep the approved advertising knowledge branch directly accessible in the vault.
    for name, data in sources.items():
        if name.startswith("docs/advertising/"):
            result[f"Сайт/Реклама/{name.removeprefix('docs/advertising/')}"] = data
    index = ["# Файлы сайта из Git", "", f"Коммит: `{commit}`.", "",
             f"Полный снимок: {len(sources)} файлов, {sum(map(len, sources.values())):,} байт.", "",
             "Документы открываются как заметки; код, JSON и медиа сохранены в исходном формате. "
             "Скрытые файлы могут не отображаться в дереве Obsidian, но включены в снимок. "
             "История версий остаётся в Git; список коммитов — в соседней заметке «История Git».", "",
             "[Карта сайта](00%20Сайт.md) · [Синхронизация](Синхронизация%20с%20Git.md)", ""]
    group = None
    for name in sorted(sources):
        current = name.split("/")[0] if "/" in name else "Корень"
        if group != current:
            index.extend([f"## {current}", ""])
            group = current
        index.append(f"- [{name}]({quote('Материалы из Git/' + name, safe='/')})")
    result["Сайт/Файлы из Git.md"] = ("\n".join(index) + "\n").encode()

    reports = ["# Отчёты проверок сайта", "", "Исторические результаты с датами и ограничениями. "
               "Перенос в Obsidian не означает повторной проверки сайта или сервера.", "",
               "[Карта сайта](00%20Сайт.md)", ""]
    for name, data in sorted(sources.items()):
        if name.startswith("docs/verification/") and name.endswith(".json"):
            stem = Path(name).stem
            target = f"Сайт/Отчёты проверок/{stem}.md"
            body = (f"# {stem}\n\n[Все отчёты](../Отчёты%20проверок.md) · "
                    f"[Исходный JSON](../{quote('Материалы из Git/' + name, safe='/')})\n\n"
                    + fenced(data.decode()))
            result[target] = body.encode()
            reports.append(f"- [{stem}]({quote('Отчёты проверок/' + stem + '.md', safe='/')})")
    result["Сайт/Отчёты проверок.md"] = ("\n".join(reports) + "\n").encode()
    for name, title in [("catalog/products.json", "Данные каталога"), ("blog/posts.json", "Данные статей")]:
        if name in sources:
            body = (f"# {title}\n\nПолные данные из `{name}`, коммит `{commit[:12]}`. "
                    "Правки сначала вносятся в источник Git.\n\n[Карта сайта](00%20Сайт.md)\n\n"
                    + fenced(sources[name].decode()))
            result[f"Сайт/{title}.md"] = body.encode()
    history = git(repo, "log", commit, "--date=short", "--format=%ad | %h | %s").decode()
    result["Сайт/История Git.md"] = ("# История Git\n\nКоммиты, доступные из экспортированной версии. "
        "Это журнал сообщений, а не копия базы `.git` или всех веток.\n\n[Карта сайта](00%20Сайт.md)\n\n"
        + fenced(history, "text")).encode()
    sync = f"""# Синхронизация с Git

Источник: локальный репозиторий Needle Shark. Снимок коммита `{commit}`.

Контекст: [PROJECT_CONTEXT](Материалы%20из%20Git/docs/PROJECT_CONTEXT.md).
Правила: [OBSIDIAN](Материалы%20из%20Git/docs/OBSIDIAN.md).
Полнота: [все файлы](Файлы%20из%20Git.md), SHA-256 записаны в `Синхронизация Git.json`.

После каждого существенного изменения агент обновляет контекст в Git, сохраняет коммит,
выполняет `python3 ops/sync-obsidian.py`, затем `python3 ops/sync-obsidian.py --check`
из репозитория и отправляет коммит в GitHub. Это часть завершения задачи; фонового таймера нет.

Правки в зеркале сначала переносятся в соответствующий источник Git. Скрипт прекращает
обновление при ручных изменениях и не перезаписывает их. Собственные заметки проекта,
карты разделов и ссылки вне управляемого списка скрипт не меняет. Исчезнувшие из Git
файлы сохраняются на прежнем месте и перечисляются как архивные в манифесте.

Копируются только файлы коммита: без `.git`, незакоммиченных материалов, `outputs/`,
секретов, серверной базы и заявок. Полный снимок не является резервной копией сервера.

[Карта сайта](00%20Сайт.md)
"""
    result["Сайт/Синхронизация с Git.md"] = sync.encode()
    return result


def safe_path(root, relative):
    part = PurePosixPath(relative)
    if part.is_absolute() or ".." in part.parts or not part.parts or part.parts[0] != "Сайт":
        raise ValueError(f"Небезопасный путь: {relative}")
    target = root.joinpath(*part.parts)
    for p in (root, *target.relative_to(root).parents):
        # Check each actual ancestor, including a symlinked project directory.
        actual = p if p.is_absolute() else root / p
        if actual.is_symlink():
            raise ValueError(f"Символическая ссылка в целевом пути: {relative}")
    if target.is_symlink():
        raise ValueError(f"Символическая ссылка: {relative}")
    return target


def write_atomic(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=path.parent, prefix=".needle-sync-", delete=False) as stream:
        temp = Path(stream.name)
        stream.write(data)
    try:
        temp.replace(path)
    finally:
        temp.unlink(missing_ok=True)


def sync(repo, project, check=False):
    project = project.absolute()
    commit, source = snapshot(repo)
    desired = export_files(repo, commit, source)
    manifest_path = safe_path(project, MANIFEST)
    old = json.loads(manifest_path.read_text()) if manifest_path.exists() else {}
    previous = old.get("files", {})
    retired = dict(old.get("retired", {}))
    if old and old.get("schema") != 1:
        raise ValueError("Неизвестная версия манифеста")
    for name in previous.keys() - desired.keys():
        retired[name] = previous[name]
    for name in desired:
        retired.pop(name, None)
    conflicts = []
    changed = []
    expected = {}
    # Preflight every path before writing anything. Never silently overwrite local work.
    for name, data in desired.items():
        target = safe_path(project, name)
        expected[name] = sha(data)
        current = sha(target.read_bytes()) if target.exists() else None
        if current == expected[name]:
            continue
        baseline = previous.get(name, old.get("retired", {}).get(name))
        if current is not None and current != baseline:
            conflicts.append(name)
        else:
            changed.append(name)
    if conflicts:
        raise ValueError("Ручные изменения в Obsidian; ничего не записано:\n" + "\n".join(conflicts))
    manifest = {"schema": 1, "commit": commit, "source_file_count": len(source),
                "source_bytes": sum(map(len, source.values())), "files": expected, "retired": retired}
    manifest_bytes = (json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode()
    manifest_changed = not manifest_path.exists() or manifest_path.read_bytes() != manifest_bytes
    if check:
        if changed or manifest_changed:
            raise ValueError(f"Снимок требует обновления: {len(changed)} файлов; манифест: {manifest_changed}")
    else:
        for name in changed:
            write_atomic(safe_path(project, name), desired[name])
        if manifest_changed:
            write_atomic(manifest_path, manifest_bytes)
    return {"commit": commit, "source_files": len(source), "managed_files": len(desired),
            "source_bytes": sum(map(len, source.values())), "written": 0 if check else len(changed),
            "retired": len(retired), "check": check}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", type=Path, default=DEFAULT_PROJECT)
    parser.add_argument("--check", action="store_true", help="Проверить совпадение без записи")
    args = parser.parse_args()
    try:
        print(json.dumps(sync(REPO, args.project, args.check), ensure_ascii=False, indent=2))
    except (ValueError, OSError, subprocess.CalledProcessError) as exc:
        parser.exit(1, f"{exc}\n")


if __name__ == "__main__":
    main()
