import fnmatch
from pathlib import Path

IGNORED_DIR_NAMES = {
    ".git", "node_modules", "venv", ".venv", "__pycache__", "dist", "build",
    ".next", ".nuxt", ".pytest_cache", ".mypy_cache", ".ruff_cache", "target",
    ".idea", ".vscode", ".turbo", "coverage", ".cache",
}

SECRET_FILE_GLOBS = [
    ".env", ".env.*", "*.pem", "*.key", "id_rsa*", "id_ed25519*", "*.pfx",
    "*.p12", "credentials*", "*.crt", "*secret*",
]

BINARY_EXTENSIONS = {
    ".png", ".jpg", ".jpeg", ".gif", ".ico", ".webp", ".bmp", ".pdf",
    ".zip", ".tar", ".gz", ".7z", ".rar", ".exe", ".dll", ".so", ".dylib",
    ".woff", ".woff2", ".ttf", ".eot", ".mp3", ".mp4", ".mov", ".avi",
    ".pyc", ".class", ".jar", ".db", ".sqlite", ".sqlite3",
}

MAX_LIST_ENTRIES = 500
MAX_TREE_NODES = 2000
MAX_READ_CHARS_FOR_LLM = 40_000
MAX_READ_BYTES_FOR_DISPLAY = 5_000_000


class FsSafetyError(Exception):
    """Raised when a filesystem operation would escape the sandboxed root,
    touch a secret-looking file, or otherwise violate a safety guardrail."""


def is_ignored_dir(name: str) -> bool:
    return name in IGNORED_DIR_NAMES or name.startswith(".") and name not in {".", ".."}


def is_secret_file(name: str) -> bool:
    lowered = name.lower()
    return any(fnmatch.fnmatch(lowered, pattern) for pattern in SECRET_FILE_GLOBS)


def is_binary_by_extension(name: str) -> bool:
    return Path(name).suffix.lower() in BINARY_EXTENSIONS


def resolve_root(root_dir: str) -> Path:
    root = Path(root_dir).expanduser().resolve()
    if not root.exists():
        raise FsSafetyError(f"Directory does not exist: {root_dir}")
    if not root.is_dir():
        raise FsSafetyError(f"Not a directory: {root_dir}")
    return root


def resolve_safe_path(root: Path, rel_path: str) -> Path:
    candidate = (root / rel_path).resolve()
    try:
        candidate.relative_to(root)
    except ValueError as exc:
        raise FsSafetyError(f"Path '{rel_path}' escapes the workspace root.") from exc
    if is_secret_file(candidate.name):
        raise FsSafetyError(f"Refusing to access secret-looking file: {rel_path}")
    for part in candidate.relative_to(root).parts[:-1]:
        if is_ignored_dir(part):
            raise FsSafetyError(f"Path '{rel_path}' is inside an ignored directory.")
    return candidate


def _visible_children(dir_path: Path) -> list[Path]:
    """Immediate children of a directory, sorted (dirs first, then
    alphabetically) and with ignored dirs / secret-looking files already
    filtered out — the shared traversal rule behind both listing functions
    below."""
    children = sorted(dir_path.iterdir(), key=lambda p: (p.is_file(), p.name.lower()))
    return [
        c
        for c in children
        if not (c.is_dir() and is_ignored_dir(c.name))
        and not (c.is_file() and is_secret_file(c.name))
    ]


def list_dir_shallow(root: Path, rel_path: str = ".") -> list[dict[str, str]]:
    target = resolve_safe_path(root, rel_path)
    if not target.is_dir():
        raise FsSafetyError(f"Not a directory: {rel_path}")

    children = _visible_children(target)[:MAX_LIST_ENTRIES]
    return [{"name": c.name, "type": "dir" if c.is_dir() else "file"} for c in children]


def build_tree(root: Path, max_nodes: int = MAX_TREE_NODES) -> dict:
    count = 0

    def walk(dir_path: Path) -> dict:
        nonlocal count
        node: dict = {"name": dir_path.name or str(dir_path), "type": "dir", "children": []}
        try:
            children = _visible_children(dir_path)
        except PermissionError:
            return node
        for child in children:
            if count >= max_nodes:
                break
            count += 1
            if child.is_dir():
                node["children"].append(walk(child))
            else:
                node["children"].append({"name": child.name, "type": "file"})
        return node

    return walk(root)


def is_probably_binary(path: Path) -> bool:
    if is_binary_by_extension(path.name):
        return True
    try:
        with path.open("rb") as f:
            chunk = f.read(8192)
        return b"\x00" in chunk
    except OSError:
        return True


def read_text_file(root: Path, rel_path: str, max_chars: int | None = None) -> str:
    target = resolve_safe_path(root, rel_path)
    if not target.is_file():
        raise FsSafetyError(f"Not a file: {rel_path}")
    if target.stat().st_size > MAX_READ_BYTES_FOR_DISPLAY:
        raise FsSafetyError(f"File too large to read: {rel_path}")
    if is_probably_binary(target):
        raise FsSafetyError(f"Refusing to read binary file: {rel_path}")

    content = target.read_text(encoding="utf-8", errors="replace")
    if max_chars is not None and len(content) > max_chars:
        content = content[:max_chars] + f"\n... [truncated, {len(content) - max_chars} more characters]"
    return content


def write_text_file(root: Path, rel_path: str, content: str) -> None:
    target = resolve_safe_path(root, rel_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
