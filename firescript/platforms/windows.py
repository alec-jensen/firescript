"""Windows runtime bindings: fir intrinsic -> (kernel32 symbol, return type, param types).

This is the entire OS surface the firescript runtime (std/internal/*.fire)
depends on: heap allocation, stdio handles, file I/O, and process exit, all
via kernel32.dll. `flir/lowering.py` looks names up here when lowering the
`win_*` low-level intrinsics.
"""

from __future__ import annotations

from flir.ir import I32, U32, U64, VOID

WINDOWS_RUNTIME_EXTERNS = {
    "win_get_process_heap": ("GetProcessHeap", U64, []),
    "win_heap_alloc": ("HeapAlloc", U64, [U64, U32, U64]),
    "win_heap_free": ("HeapFree", U32, [U64, U32, U64]),
    "win_get_std_handle": ("GetStdHandle", U64, [I32]),
    "win_write_file": ("WriteFile", I32, [U64, U64, U32, U64, U64]),
    "win_read_file": ("ReadFile", I32, [U64, U64, U32, U64, U64]),
    "win_create_file_a": ("CreateFileA", U64, [U64, U32, U32, U64, U32, U32, U64]),
    "win_close_handle": ("CloseHandle", I32, [U64]),
    "win_delete_file_a": ("DeleteFileA", I32, [U64]),
    "win_move_file_ex_a": ("MoveFileExA", I32, [U64, U64, U32]),
    "win_copy_file_a": ("CopyFileA", I32, [U64, U64, I32]),
    "win_get_last_error": ("GetLastError", U32, []),
    "win_get_command_line_a": ("GetCommandLineA", U64, []),
    "win_get_file_size": ("GetFileSize", U32, [U64, U64]),
    "win_set_file_pointer": ("SetFilePointer", U32, [U64, I32, U64, U32]),
    "win_exit_process": ("ExitProcess", VOID, [U32]),
}
