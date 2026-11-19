# language model redesign (toward 1.0)

> Status: **[PLANNED]** — design document. Nothing described here is implemented unless it
> says so explicitly. All syntax is provisional. The roadmap that schedules this work is
> [version_planning.md](version_planning.md). Until each part ships, the user-facing docs under
> `/docs/reference` remain the source of truth for what the compiler does today.

## Why

firescript's memory model grew from a Python-shaped intuition: two categories of type
(Copyable and Owned) where the category decides what `a = b` means. Experience with C++ and Rust
suggests a better foundation: **every type is a value, copying is the default, moving and
borrowing are explicit.** The same pass covers const-correctness, member visibility, and an OOP
model that reads like Java but compiles to flat, statically dispatched code.

Where this document says "today", it describes the compiler as audited in November 2026.

## 1. Values, copy, and move [PLANNED]

### 1.1 Every type is a value

There is no Owned/Copyable split visible to users. Every type is a value; classes are stored
inline (like C++ objects), not behind an implicit heap pointer.

- `a = b` and passing an argument by value **copy** the value, memberwise.
- A copy of a trivially copyable type (primitives, classes whose fields are all trivially
  copyable) is a bitwise copy and has no cleanup.
- A class's copy copies each field using that field's own copy. Types that manage a buffer
  (`string`, `Vec<T>`, fixed arrays of such) define their copy as a deep copy.
- A class may define its own deep-copy hook (first-party, like a C++ copy constructor). Name and
  syntax are open (`copy(&this) -> T` is the working assumption).
- A class with a field that cannot be copied is **move-only** unless it defines a copy. Example:
  a `File` handle. This is derived by the compiler; users never write a category.

```firescript
class Point { x: int32; y: int32; }          // trivially copyable (derived)
class Doc    { title: string; tags: Vec<string>; } // copyable, copy is deep (derived from fields)
class Handle { file: File; }                 // move-only (File has no copy)

p: Point = Point(1, 2);
q: Point = p;            // copy
d: Doc = Doc(...);
e: Doc = d;              // copy (deep, via string/Vec copy)
h: Handle = open(...);
k: Handle = h;           // error: Handle cannot be copied; use move
k: Handle = move h;      // ok
```

### 1.2 Move is explicit

`move x` transfers the value out of `x`; `x` is unusable afterward (use-after-move is still a
compile error, via the existing move-state analysis). The exact spelling (`move x` vs `move(x)`)
is open. Returning a local by value is an implicit move.

### 1.3 Drops

Deterministic, compiler-inserted destruction is unchanged in spirit. A type needs a destructor
if it, or any field, manages a resource; the compiler derives this. The `@owns_elements` class
decorator used by `Vec` today becomes derivable from field types.

### 1.4 Internal predicates

The compiler keeps three internal predicates (never user keywords): *trivially copyable*, *needs
destructor*, *copyable*. Diagnostics speak in terms of "cannot be copied; use move".

### 1.5 Consequences

- `copyable class` is removed.
- `CopyableOption` / `CopyableResult` / `CopyableTuple` collapse into `Option` / `Result` /
  `Tuple`.
- The "cannot borrow a Copyable type" rule is removed.
- The planned `Owned` / `Copyable` generic constraints are dropped. Generics stay monomorphized;
  generic code that copies a `T` is checked at instantiation.
- Passing a large value by value copies it. Convention: take `&T` for read-only parameters. A
  lint for large implicit copies is a candidate.
- Class layout in FLIR lowering changes from heap-pointer to inline.

## 2. References [PLANNED]

### 2.1 Syntax and kinds

- `&T` — shared, read-only reference (transitively const; see §4).
- `&mut T` — mutable reference, **exclusive**.
- Receivers keep `&this` and `&mut this`. Today a parameter is written `&name: T`; moving the `&`
  into the type is open, and the docs/parser mismatch should be resolved with this change.

### 2.2 Exclusivity

While a `&mut` to a value is live, no other reference to it (shared or mutable) is live. Checked
over lexical scope (no full non-lexical-lifetime analysis initially). Today there is no
exclusivity check at all.

### 2.3 Where references may appear

- Allowed as parameters and locals.
- A reference may be **returned** only if it is derived from a reference parameter or `this`
  (elision: with one reference input the output borrows from it; `&this` methods may return
  borrows of their fields). No lifetime annotations.
- References **cannot be stored in fields** for now. Never returning or storing a reference to a
  local is what makes dangling references impossible.

Returning a value by value is always fine and is a move: the caller receives ownership.

### 2.4 Deferred pointer-like types

`Box<T>` (unique heap ownership, needed for recursive types and owned polymorphism) and
`Shared<T>` (reference counted, the explicit opt-in to dynamic lifetime) are planned stdlib
types but are **not part of the first cut**. There are no raw pointers. Until `Box` exists,
recursive types (lists, trees) and owned polymorphic values are not expressible.

## 3. Const [PLANNED]

Today `const` on a local or class field is parsed but **not enforced**, and `const` class fields
do not parse. (Top-level literal constants work.) The redesign:

- **Binding const:** `const x: T = e;` forbids reassigning `x`.
- **Object const:** access through `&T` is read-only and **transitive**: no field assignment, no
  calling a method that takes `&mut this`, through any depth of owned fields. Through `Box` it
  stays deep; through `Shared` mutation requires an explicit opt-in.
- **Const methods:** `&this` methods are the const methods. A `&T` can call them; it cannot call
  `&mut this` methods.
- **Const fields** are assignable only in the constructor.
- References are not reseatable, so no "const pointer vs pointer to const" distinction exists.
- A `mutable` field escape hatch (C++ style, for caches) is out of scope for now.

Const and exclusivity are one mechanism (shared vs mutable access) and are implemented together.

## 4. Visibility [PLANNED]

Class members get `private`, `protected`, and `public`, modeled on C++ (default and exact
semantics to be decided; module-level `export` is unchanged). Today there is no member
visibility. This is a semantic-analyzer check with no backend impact.

## 5. Classes, abstract classes, interfaces, Object [PLANNED]

Java-style, not C++-style.

- **class** — concrete; single inheritance.
- **abstract class** — may have fields, concrete methods, and abstract methods; not
  instantiable.
- **interface** — methods only (abstract, plus defaults), no fields; a class implements many.
- **`Object`** — every class derives from `Object`; it supplies the common methods (working set:
  `toString`, `equals`, `hashCode`).

### 5.1 Making it cheap

- Classes are inline flat structs; methods are plain functions taking a receiver; calls are
  static by default.
- A vtable pointer exists only in classes whose hierarchy has a method that is overridden **and**
  reached through dynamic dispatch. Because firescript is a whole-program compiler, it can see
  every subclass and devirtualize any method nothing overrides. `Object` as a root is therefore
  mostly a type-system relationship, not a per-object tax.
- Interfaces default to **static dispatch**: `fn f<T: Comparable>(x: T)` is monomorphized.
  Dynamic dispatch goes through `&Interface` (a fat reference: data pointer plus vtable pointer).
- Polymorphism is through references (and later `Box`), never by value, so there is no slicing.
  Consequence: a bare `Shape s = Circle(...)` for an abstract `Shape` is an error; use `&Shape`.
- Single inheritance with the base laid out as a prefix.

### 5.2 Today

Inheritance (`class D from B`) is a parse-time copy-down of base fields and methods with static
overriding; there are no vtables, no subtyping, no abstract classes, no interfaces. Interface
names in generic constraints are parsed as type names only. `docs/reference/classes.md`
documents overriding as working; without dispatch it works only statically.

### 5.3 Primitives and Object

A bare `int32` has no header, so it cannot be viewed as `&Object` without boxing (as in Java).
Until `Box` exists, primitives get `Object`'s methods **statically** through bindings (§6) but
are not dynamically `Object`s.

## 6. Primitive bindings [PLANNED]

Binding a library class to a primitive type lets `a.abs()` work on an `int32`.

```firescript
@bind(int32)
class Integer32 : Integer {
    fn abs(this: int32) -> int32 { ... }
}
```

- The binding directive is enabled only for the standard library. (Today, directives are **not**
  actually restricted to std: any user file can write `directive enable_lowlevel_runtime;`.
  Gating needs to be enforced as part of this work. Only `@builtin_method` is path-restricted
  today.)
- `a.abs()` lowers to a static call `Integer32.abs(a)`: zero runtime cost.
- The compiler keeps a binding table (type to class). A method call on a primitive resolves
  through it and **implicitly loads** the defining module; no import is required. Module load
  order must be deterministic (source order, never table iteration order).
- `Integer` is an **interface** implemented by each binding (`Integer8` … `Integer64`, unsigned
  variants), not a base class, so no boxing is needed. Code that accepts any precision is generic:
  `fn f<T: Integer>(x: T)`.
- Today `@builtin_method` covers only the string and array families; there is no int or float
  family. The bindings replace and generalize it.

## 7. Function interfaces and lambdas [PLANNED]

```firescript
interface fn Callback(a: int32, b: float64) -> void;
```

- An `interface fn` is an interface with exactly one abstract method. A function or lambda with
  a matching signature converts to it. Matching is **structural** (no `implements` on a lambda),
  unlike classes, which are nominal.
- An inline anonymous form (`fn(int32, float64) -> void`) is sugar; the named form is an alias.
- Generic function interfaces use existing monomorphization (`interface fn Mapper<T, R>(x: T) -> R;`).
- Dispatch follows §5.1: a by-value `Callback` parameter is generic over the concrete closure
  type (monomorphized, inlinable); `&Callback` is a fat reference.
- **Captures:** non-capturing lambdas and plain functions are a bare function pointer. Capturing
  lambdas are an anonymous struct holding the captures (borrowed, or copied/moved in).
  Mutability falls out of the receiver rules: calling through `&Callback` needs a closure that
  does not mutate its captures; a mutating closure needs `&mut Callback`; a closure that
  consumes a moved-in value is taken by value and callable once.
- **Escaping closures** (returned or stored) need heap storage and therefore `Box`; the first
  version allows only non-escaping closures that borrow from the enclosing scope. This extends
  the existing sketch in `docs/reference/memory_management.md` §5.
- Today there are no lambdas, function values, or function types (`type_system.md` marks function
  types `[PLANNED]`).
- Python-style function and class wrappers (decorators) are a later goal. They are intended to
  expand at compile time so they stay zero-cost and do not require escaping closures.

## 8. Conversions and type tests [PLANNED]

### 8.1 Replacing `as`

Once primitive bindings (§6) exist, the `as` cast keyword is removed. Today `as` handles numeric
conversions, built-ins to string, and string to numeric (`"42" as int32`).

- To string: `x.toString()` (from `Object`, or the primitive's binding).
- Numeric conversions are methods on the bound class with the target in the name, e.g.
  `a.toInt64()`, `f.toInt32()`. Each states its semantics (a truncating conversion and a
  rounding one are different methods), and generic code can use an interface bound such as
  `T: Number` and call `x.toFloat64()`.
- String to number is a parse method that returns a `Result`, so failure is expressible.
- Open: whether lossless widening (e.g. `int32` to `int64`) is implicit. Lossy or fallible
  conversions are always explicit.
- `as` stays until bindings ship and is then deprecated.

### 8.2 Membership

There is no `in` operator beyond `for x in y`. Membership is a library call (`contains`),
e.g. a method on an `Iterable`/`Container` interface. This keeps the cost visible and avoids a
grammar ambiguity with `for-in`.

### 8.3 Runtime type tests

Library methods on `Object`, not keywords:

- `x.isInstance<T>()` — true if `x` is a `T` or any subclass; for an interface `T`, true if the
  class implements it.
- `x.isExactly<T>()` — true only if the concrete type is exactly `T`; rejected at compile time
  for an interface or abstract class `T`. Needed for symmetric `equals()` implementations.
- `x.downcast<T>()` — returns a nullable reference (`&T?`) using the `isInstance` rule.
  This requires nullable reference types; whether references can be nullable is an open
  question for the `&T` work.

Cost: exact check compares a type ID; the class is-a check is an O(1) range test over a
depth-first numbering of the single-inheritance hierarchy (the whole program is known);
interface is-a checks consult a per-class interface table. A class used with these methods
counts as dynamically used and gets a vtable pointer (§5.1).

An `is` keyword with a flow-narrowing binding (`if (s is Circle c) { ... }`) is deferred. It is
the one thing a function cannot do; it is added later only if `downcast` plus a null check proves
too clumsy in real code. The instanceof-style check is deliberately not a getClass/`Class`
object: that would add a reflection concept.

## 9. Errors and exceptions [PLANNED]

Today there is no catchable error mechanism. `std.fs` returns `FileResult` objects, `Result<T,E>`
and `Option<T>` exist as library types, and runtime traps (integer overflow, division by zero,
out-of-range indexing, invalid float-to-int conversions) print a message and terminate the
program (`docs/reference/error_handling.md`). The design below is for 0.9.0, after the object
model (§5) it depends on.

### 9.1 The rule: operations throw, function calls return a `Result`

There is exactly one way to signal each kind of failure:

- **Operations throw.** A language operation that can fail raises an exception: integer
  overflow (`+ - * / % **`, unary minus, `++`/`--`), division and modulo by zero, array indexing
  out of bounds, a float-to-int cast of NaN/infinity/out-of-range, and so on. These are the
  runtime traps of `docs/reference/error_handling.md`, made catchable.
- **Function calls return a `Result`.** A function that can fail returns `Result<T, E>` (or
  `Option<T>` when there is no error to report). A function that cannot fail returns a plain
  value. Fallibility is visible in the signature and never raised behind the caller's back.
- Exceptions are rooted at `Exception extends Object`, with a message and an optional cause, in a
  Python-style hierarchy: `Exception` -> `ArithmeticException` -> `OverflowException`,
  `DivisionByZeroException`; `IndexOutOfBoundsException`; `InvalidConversionException`; and so on.
  `try { } catch (T e) { } finally { }` matches by runtime type (the `isInstance` rule of §8.3), so
  `catch (ArithmeticException e)` catches the whole subtree. Syntax is provisional.
- An exception raised inside a callee propagates through its callers until caught (an overflow
  deep in a call chain is still an exception), so callers do not need to be `Result`-aware of
  operations inside callees.
- Catching a trap is the programmer acknowledging they will handle it; not catching it terminates
  the program with a stack trace (§9.3). A blanket `catch (Exception e)` is legal but discouraged,
  and a lint warns on it.
- The same hierarchy classifies errors carried in a `Result`: `Result<File, FileOpenException>`
  (`FileOpenException` -> `IOException` -> `Exception`) is an ordinary error value, not something
  that is thrown. `std.fs` opening a file returns such a `Result`.
- The runtime-trap work that precedes exceptions routes every trap through one runtime entry point
  so that it can later throw instead of exiting.

### 9.2 Consequences and open questions

- **Ergonomics of `Result` everywhere.** If every fallible call returns a `Result`, propagating an
  error through several calls needs a short form. A propagation operator (a postfix `?` or a
  `try`-expression that returns early with the error) is strongly recommended; without it,
  every call site needs an explicit match. Open.
- **`unwrap()` and friends.** `Result.unwrap()` cannot return a value when the result is an error.
  Proposal: it raises an exception (`UnwrapException` carrying the error), as the one explicit,
  named bridge from a `Result` to an exception. Open.
- **Collections.** `list.get(i)` is a function, so under the rule it returns an `Option`/`Result`.
  Indexing with `list[i]` would be an operation and would throw. That points at an indexing
  interface (`Indexable`) so collections support `[]`; open for 0.9.0.
- **No user-written `throw` statement in the initial design.** Exceptions come from operations.
  Whether a `catch` block can rethrow (`throw e;`) is open.
- **Naming.** Explicit arithmetic functions follow the same rule: `wrapping_*`/`saturating_*`
  cannot fail and return plain values, and `checked_*` can fail and returns a `Result`. Whether
  method names are camelCase (the standard library's majority) or snake_case is open.

### 9.3 Stack traces

Debug builds produce Python-quality tracebacks (`Traceback (most recent call last):`, file, line,
function, then `ExceptionType: message`, plus chained causes). Mechanism: frame pointers in debug
builds, a deterministic address-to-(function, file, line) table embedded in the binary (sorted by
address, so builds stay byte-identical), and the chain of return addresses captured when an
exception is thrown and formatted lazily when printed. Release builds omit the tables and the
capture. An uncaught exception prints its traceback to stderr and exits with a nonzero status.

### 9.4 Implementation sketch

- No stack unwinder is required initially. The compiler infers, over the whole program, which
  functions can throw. A throwing function (one containing an operation that can raise, or calling one that can) returns
  an extra error value, and each call site checks it and branches. A throw is then an early return, and the compiler already inserts drops on every
  early exit, so owned values are released correctly and `finally` is a cleanup block.
- Callers of functions that cannot throw pay nothing. Because every integer operation can trap,
  almost every function will be inferred as throwing; the per-call check is the cost. A table-based
  unwinder (zero happy-path cost, more runtime machinery) is a later optimization. The semantics
  above do not depend on which implementation is used.
- A raised exception is a heap-allocated object owned by the in-flight exception and moved into the
  catch variable, so it depends on `Box`/owned polymorphism (§2.4) arriving with the object model.

## 10. Migration notes

Work implied by this design, from the November 2026 audit:

- **Consolidate move/drop logic.** Move checking lives in `semantic_analyzer.py`, again in
  `preprocessor.py` (own signature tables, drop insertion), and again in the FIR ownership
  verifier. Rework this into one source of truth before changing the rules.
- **Fix documentation drift** found in the audit: `owned this` / `owned` parameters are accepted
  by the parser although the docs mark the consuming receiver `[PLANNED]`; `fn m(this)` on an
  owned class is silently a read-only borrow; `const` is documented as enforced but is not; docs
  write `&T` in types while the parser takes `&` before the parameter name; `.clone()` is
  `[PLANNED]` yet FIR has a `CloneInst`; `docs/internal/development/builtin_methods.md` is
  referenced but does not exist.
- **Docs to rewrite** once the model ships: `docs/reference/memory_management.md` (declared
  authoritative), `docs/glossary.md`, and the Owned/Copyable mentions in `classes.md`,
  `functions.md`, `scoping.md`, `arrays.md`, `variables.md`, `operators.md`, `type_system.md`,
  `overview.md`, `std/types.md`, `std/collections.md`, `std/text.md`, the FIR/FLIR internal
  specs, `CLAUDE.md`'s feature table, and the changelog.
- **Tests:** the existing memory tests encode the old model and need an intentional, documented
  update (per the project's rules on editing tests), plus new coverage for each rule above.

## 11. Open questions

- Spelling of move (`move x` vs `move(x)`) and of the deep-copy hook.
- Whether `&` moves into the type position for parameters.
- Default member visibility and the exact meaning of `protected`.
- How `Object`'s common methods are declared and overridden.
- Whether references can be nullable (needed by `downcast`); whether lossless numeric widening is implicit.
- Exact `std.fs` split between `Result` and thrown `IOException`s; whether a lint should warn on blanket `catch (Exception e)` by default.
- Whether and when `Box` / `Shared` land relative to capturing closures.
