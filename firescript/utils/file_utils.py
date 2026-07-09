import os


def safe_relpath(path: str, start: str | None = None) -> str:
    """os.path.relpath, falling back to the input path if it can't be made
    relative (e.g. Windows ValueError when path and start are on different
    drives). Used only for cosmetic display paths in error messages."""
    try:
        return os.path.relpath(path, start)
    except ValueError:
        return path


def get_line_and_coumn_from_index(file: str, index: int) -> tuple[int, int]:
    line = 1
    column = 1

    for i, char in enumerate(file):
        if i == index:
            break

        if char == "\n":
            line += 1
            column = 1
        else:
            column += 1

    return line, column


def get_line(file: str, line: int) -> str:
    return file.splitlines()[line - 1]
