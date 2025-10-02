# syscalls docs

Syscalls are only intended to be used in the standard library. When we need them in the standard library, you add this directive at the top of the file:

```firescript
directive enable_syscalls;
```

## Available Syscalls

Enabling syscalls gives you access to the following functions:

| Syscall                   | Description                                                          |
|---------------------------|----------------------------------------------------------------------|
| syscall_open(path, mode)  | Opens a file at `path` with the given `mode` ("r", "w", "a", etc.). Returns a file descriptor or file object referencing the open file. |
| syscall_read(fd, buf, n)  | Reads up to `n` bytes from file descriptor or file object `fd` into buffer `buf`. Returns number of bytes read or error code. |
| syscall_write(fd, buf, n) | Writes up to `n` bytes from buffer `buf` to file descriptor or file object `fd`. Returns number of bytes written or error code. |
| syscall_close(fd)         | Closes file descriptor or file object `fd`. Returns 0 on success or error code. |
| syscall_remove(path)      | Removes (deletes) the file at the given `path`.                      |
| syscall_rename(old, new)  | Renames file `old` to `new`.                                         |
| syscall_stat(path, stat)  | Gets metadata for file at `path` into `stat` struct.                 |
| syscall_exec(cmd, args)   | Executes shell command `cmd` with arguments `args`.                  |
| syscall_getenv(name, buf) | Gets the value of the environment variable `name` into `buf`.        |
| syscall_system(cmd)       | Executes shell command `cmd` via the system shell.                   |
| syscall_exit(code)        | Exits the process with exit code `code`.                             |
| syscall_time()            | Returns the current system time (seconds since epoch).               |
| syscall_sleep(ms)         | Sleeps for `ms` milliseconds.                                        |

## How File and Descriptor Objects Work

- **File handles/descriptors are returned by `syscall_open` and uniquely identify an open file.**
- **Parallel I/O:** You can open multiple files at once. Each operation (`read`, `write`, `close`) targets a specific file via its descriptor/object, allowing independent and parallel operations on multiple files.
- **Lifetime:** The file descriptor/object remains valid until explicitly closed via `syscall_close`. After closing, further operations on that handle are invalid.
- **Threading/Concurrency:** If the firescript runtime or standard library supports threading, syscalls are designed so that concurrent threads can operate on different file descriptors in parallel, with OS-level guarantees of isolation and safety.
- **Error Handling:** Functions typically return 0 or a positive value on success, and a negative error code on failure (e.g., invalid descriptor, permission denied).

### Example Usage

```firescript
directive enable_syscalls;

// Open two files for parallel access
int fd1 = syscall_open("output1.txt", "w");
int fd2 = syscall_open("output2.txt", "w");

if fd1 >= 0 and fd2 >= 0 {
    // Write to both files independently
    syscall_write(fd1, "foo", 3);
    syscall_write(fd2, "bar", 3);

    syscall_close(fd1);
    syscall_close(fd2);
}
```

### Notes

- Syscalls are low-level; errors are returned as negative numbers where applicable.
- Buffer types and argument conventions are subject to firescript's standard library conventions.