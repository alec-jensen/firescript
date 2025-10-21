def get_line_and_coumn_from_index(file: str, index: int) -> tuple[int, int]:
    line = 1
    column = 0

    for i, char in enumerate(file):
        if i == index:
            break

        if char == "\n":
            line += 1
            column = 0
        else:
            column += 1

    return line, column


def get_line(file: str, line: int) -> str:
    return file.splitlines()[line - 1]
