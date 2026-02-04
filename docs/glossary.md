# Glossary

This glossary contains definitions of terms commonly used in the firescript documentation. For authoritative rules on ownership and lifetimes see [Memory Management](./reference/memory_management.md).

## Memory Management Terms

| Term | Definition |
|------|------------|
| Copyable | Fixed-size value with no destructor; copied bitwise. |
| Owned | Resource/heap-managing value with unique ownership semantics. |
| Move | Transfer of ownership; original binding becomes invalid. |
| Borrow (`&T`) | Read-only, non-owning view whose lifetime is limited to an expression or call boundary. |
| Clone | Explicit duplication of an owned value’s contents (deep or COW per type). |
| Drop | Deterministic destruction at an inserted point (last use or scope exit). |
| Module | A piece of firescript code that is imported or included in another firescript file. |
| Package | A module or collection of modules that is installed via the package manager. |
| Library | A module or collection of modules that is provided with the firescript installation. |

### Expanded Definitions

- **Copyable:** Includes `intN`, `floatN`, `bool`, and `char`. These are fixed-size scalars stored on the stack. Copies are bitwise; no destructor runs.
- **Owned:** Includes user-defined objects, closures, arrays, and strings. These values are stored on the heap with pointers on the stack. Ownership is unique unless an explicit sharing container (future `Rc`, `Arc`) is used.
- **Move:** Occurs on assignment, passing to a parameter of owned type, or returning a value. After a move, the source binding cannot be used (use-after-move error).
- **Borrow:** Lightweight, read-only access. Cannot be stored in owned fields or escape its originating scope/call. Does not incur runtime overhead.
- **Clone:** Creates an independent owned value. Semantics (deep vs copy-on-write) determined by the type implementation but always preserves logical independence.
- **Drop:** Compiler-inserted destructor invocation (`drop(this)`) ensuring timely resource release (files, sockets, buffers) without tracing GC.
- **Module:** A single `.fire` file or a collection of files that can be imported. Modules encapsulate code and can expose public APIs.
- **Package:** A distributable unit of code, often hosted in a package registry. Packages can contain multiple modules and dependencies.
- **Library:** A set of pre-written modules provided with the firescript installation, offering standard functionality (e.g., `std.io`, `std.math`).