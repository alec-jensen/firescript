# firescript Philosophy

firescript is intended to be a simple but powerful and fast language with safety by design. This is accomplished through a strict type system, explicit design, and simple to learn but powerful compile-time memory management. It is intended to be usable in a variety of domains, from systems programming to web development, as it compiles to a C backend or JavaScript + WebAssembly in the future.

## Key Principles

- **Simplicity:** The language syntax and semantics are designed to be easy to learn and understand, minimizing complexity while maximizing expressiveness.
- **Safety:** Strong static typing, null safety, and compile-time checks help prevent common programming errors.
  - Null safety is enforced by default; nullable types must be explicitly declared.
  - Memory safety is ensured through compile-time ownership and borrowing rules, preventing issues like dangling pointers
  - There is no undefined behavior; all operations are well-defined.
- **Performance:** Although the syntax is high-level, firescript is designed to compile to efficient low-level code, with no runtime overhead.
- **Explicitness:** The language favors explicit declarations and operations over implicit behavior, making code easier to read and reason about.