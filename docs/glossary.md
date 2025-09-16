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

### Expanded Definitions

- **Copyable:** Includes `intN`, `floatN`, `bool`, `char`, `string`, arrays, and other fixed-size scalars. Copies are bitwise; no destructor runs.
- **Owned:** Includes user-defined objects, closures, or any type that requires a destructor. Ownership is unique unless an explicit sharing container (future `Rc`, `Arc`) is used.
- **Move:** Occurs on assignment, passing to a parameter of owned type, or returning a value. After a move, the source binding cannot be used (use-after-move error).
- **Borrow:** Lightweight, read-only access. Cannot be stored in owned fields or escape its originating scope/call. Does not incur runtime overhead.
- **Clone:** Creates an independent owned value. Semantics (deep vs copy-on-write) determined by the type implementation but always preserves logical independence.
- **Drop:** Compiler-inserted destructor invocation (`drop(this)`) ensuring timely resource release (files, sockets, buffers) without tracing GC.