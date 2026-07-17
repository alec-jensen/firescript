# compiler directives

compiler directives are special instructions to the compiler that affect compilation behavior. They are not part of the runtime language and do not produce any code themselves.

Directives are not intended to be used in source files except in specific scenarios (e.g., enabling syscalls in the standard library). They are primarily for internal use by the compiler and standard library.

## Directive Syntax

```firescript
directive <name> [<arg1> [, <arg2> ...]];
```

- `directive` keyword starts the directive.
- `<name>` is the name of the directive (e.g., `enable_syscalls`).
- Optional arguments can be provided, separated by commas.

### Examples

- Enable syscalls in a file:

```firescript
directive enable_syscalls;
```

- Enable compiler-inserted drops (preprocessor inserts drop() calls):

Should ONLY be used internally by the preprocessor.

```firescript
directive enable_drops;
```

- Enable process argument intrinsics (`process_argc` / `process_argv_at`):

```firescript
directive enable_process_args;
```

## Available Directives

- `enable_syscalls`: Allows the use of syscalls in the file. This is required for files in the standard library that need syscall access (e.g. std.io).
- `enable_drops`: Enables the preprocessor to insert deterministic drop() calls for Owned values (e.g., arrays) at scope boundaries and early exits.
- `enable_lowlevel_stdout`: Allows the use of low-level stdout function.
- `enable_lowlevel_stdin`: Allows the use of low-level stdin function.
- `enable_process_args`: Allows use of process argument intrinsics (`process_argc()` and `process_argv_at(index)`) and low-level string helper intrinsics (`str_length`, `str_char_at`, `str_index_of`, `str_slice`) in the file. This is intended for standard library internals (for example, `std.cli.args`).
- `enable_lowlevel_runtime`: Allows use of the runtime-implementation primitives. **Exclusively for `firescript/std/internal/*.fire`** (the firescript-implemented runtime, split by concern across several files -- `alloc.fire`, `strings.fire`, `number_conversions.fire`, `float_conversions.fire`, `io.fire`, `syscalls.fire`, etc. -- all merged into every program built with the FIR backends; any of these files may call any other's functions with no import between them). Primitives:
  - Raw memory: `mem_load_u8(addr) -> uint8`, `mem_store_u8(addr, v)`, `mem_load_u64(addr) -> uint64`, `mem_store_u64(addr, v)`, `mem_copy(dst, src, n)` — addresses are `uint64`.
  - Bitcasts: `str_to_addr(string) -> uint64`, `addr_to_str(uint64) -> string`.
  - Runtime state: `runtime_state_get() -> uint64` / `runtime_state_set(uint64)` — a single mutable pointer-sized cell holding the runtime's root state block.
  - Win32 externs (lower to kernel32.dll imports): `win_get_process_heap`, `win_heap_alloc`, `win_heap_free`, `win_get_std_handle`, `win_write_file`, `win_read_file`, `win_create_file_a`, `win_close_handle`, `win_delete_file_a`, `win_move_file_ex_a`, `win_copy_file_a`, `win_get_last_error`, `win_get_command_line_a`, `win_get_file_size`, `win_exit_process`. Handles and pointers are `uint64`.

  Functions in the runtime module named `fs_rt_*` implement the FLIR runtime ABI; the FIR lowering routes runtime calls to them when defined, falling back to backend-provided shims otherwise (which allows incremental porting).
- `enable_builtin_methods`: Allows the `@builtin_method("family", "name", **flags)` decorator on a function declaration. **Exclusively for `firescript/std/internal/*.fire`.** The decorated function becomes the backing implementation of a dot-method (`.name()`) on every value of the given receiver family (`"string"`, `"array"`) across every compiled program, with no user import -- see `firescript/builtin_methods.py` for the registry that scans for these at compile time, and its docstring / `firescript/std/internal/strings.fire` and `builtin_arrays.fire` for authoring examples.