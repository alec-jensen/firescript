# syscalls docs

Syscalls are only intended to be used in the standard library. When we need them in the standard library, you add this directive at the top of the file:

```firescript
directive enable_syscalls;
```

## Return Type: `SyscallResult`

All syscalls return a `SyscallResult` copyable class defined in the standard library:

```firescript
copyable class SyscallResult {
    int32 status;
    string data;
}
```

- `status` — An integer status code. `0` or a positive value (e.g. bytes read/written) indicates success. A negative value indicates an error.
- `data` — A string containing any output produced by the syscall (e.g. bytes read, environment variable value). **Not guaranteed to have a meaningful value** — for syscalls that do not produce output (e.g. `syscall_write`, `syscall_close`), `data` will be an empty string.

> **Note:** A tuple return type would be more natural here, but tuples are not yet implemented in firescript. `SyscallResult` serves as the interim solution.

## Available Syscalls

Enabling syscalls gives you access to the following functions. Only the basic I/O syscalls are currently implemented; the remaining ones are planned.

| Syscall                    | Description                                                                                                   | `status`                        | `data`                        |
|----------------------------|---------------------------------------------------------------------------------------------------------------|---------------------------------|-------------------------------|
| `syscall_open(path, mode)` | Opens the file at `path` with the given `mode` (`"r"`, `"w"`, `"a"`, etc.). Returns a file descriptor.       | fd (≥ 0) or negative error code | empty                         |
| `syscall_read(fd, n)`      | Reads up to `n` bytes from file descriptor `fd`.                                                              | bytes read or negative error code | the bytes read as a string  |
| `syscall_write(fd, buf)`   | Writes string `buf` to file descriptor `fd`.                                                                  | bytes written or negative error code | empty                    |
| `syscall_close(fd)`        | Closes file descriptor `fd`.                                                                                  | 0 on success or negative error code | empty                    |
| `syscall_remove(path)`     | *(planned)* Removes the file at `path`.                                                                       | 0 on success or negative error code | empty                    |
| `syscall_rename(old, new)` | *(planned)* Renames file `old` to `new`.                                                                      | 0 on success or negative error code | empty                    |
| `syscall_exec(cmd, args)`  | *(planned)* Executes command `cmd` with `string[]` arguments `args`.                                          | exit code or negative error code | empty                    |
| `syscall_getenv(name)`     | *(planned)* Gets the value of environment variable `name`.                                                    | 0 on success or negative error code | the variable's value     |
| `syscall_system(cmd)`      | *(planned)* Executes shell command `cmd` via the system shell.                                                | exit code or negative error code | empty                    |
| `syscall_exit(code)`       | *(planned)* Exits the process with exit code `code`.                                                          | does not return               | does not return               |
| `syscall_time()`           | *(planned)* Returns the current system time as seconds since the Unix epoch.                                  | seconds since epoch           | empty                         |
| `syscall_sleep(ms)`        | *(planned)* Sleeps for `ms` milliseconds.                                                                     | 0 on success or negative error code | empty                   |

## How File Descriptors Work

- **File descriptors are integers returned in `status` by `syscall_open`.** Pass them to subsequent `read`, `write`, and `close` calls.
- **Parallel I/O:** You can open multiple files at once. Each operation targets a specific file via its descriptor, allowing independent operations on multiple files.
- **Lifetime:** The file descriptor remains valid until explicitly closed via `syscall_close`. After closing, further operations on that descriptor are invalid.
- **Error Handling:** `status` is `0` or positive on success and negative on error.

### Example Usage

```firescript
directive enable_syscalls;

SyscallResult open1 = syscall_open("output1.txt", "w");
SyscallResult open2 = syscall_open("output2.txt", "w");

if open1.status >= 0 and open2.status >= 0 {
    syscall_write(open1.status, "foo");
    syscall_write(open2.status, "bar");

    syscall_close(open1.status);
    syscall_close(open2.status);
}

SyscallResult r = syscall_read(open1.status, 64);
if r.status >= 0 {
    // r.data contains the bytes read
}
```

### Notes

- Syscalls are low-level and intended to be wrapped by higher-level standard library functions (e.g. `std.io`). Avoid using them directly in user code.
- `syscall_open` returns the file descriptor in `status`, not in `data`, to keep the integer value directly usable.