# Memory Management

> Status: This is the authoritative specification of firescript's ownership-based memory model. Some described behaviors (e.g., last-use drop insertion, borrow checking) may not yet be enforced in current builds. If another document conflicts with this page, this page takes precedence.

## Overview

firescript uses a deterministic ownership model rather than a tracing garbage collector. Values are categorized as either Trivially Copyable (TC) or Owned (Non‑Trivially Copyable, NTC). Owned values move by default; borrowing (`&T`) provides a temporary, read‑only view *only for Owned types*. Trivially Copyable types are always passed and assigned by value (bitwise copy); they cannot be borrowed. The compiler (planned) inserts destruction (“drop”) at the last proven use or at scope end. Ordinary owned values incur no runtime reference counting.

This page is layered: first core concepts, then detailed rules. Other documentation pages should link here instead of redefining terminology.

## Core Concepts (Concept Map)

1. Categorize each value: TC or Owned (NTC)
2. Moving an Owned value transfers ownership; the previous binding becomes invalid
3. Borrowing (`&T`) is only allowed for Owned types; it grants a read-only, non-owning view tied to the original owner’s lifetime
4. TC types are simply copied; “move” is indistinguishable from copy; borrowing does not exist for TC
5. The compiler performs last-use analysis to place deterministic drop points (Owned types only)
6. Scope exit drops any remaining owned values
7. Cloning is explicit (`.clone()` / `clone(x)`) for Owned values

## Terminology

Core terms (Trivially Copyable, Owned / Non-Trivially Copyable, Move, Borrow, Clone, Drop) are defined centrally in the glossary. This document applies those definitions normatively and adds the constraint:

- Borrow (`&T`) is only defined for Owned types. Attempting to borrow a TC type (e.g., `&int`) is a compile error.

## How This Interacts With Other Features

- Scoping: Scope exit triggers drops of any still-owned values (see [Scoping](./scoping.md)).
- Functions: Owned parameters move; borrowed parameters (`&T`) (Owned types only) do not transfer ownership (see [Functions](./functions.md)).
- Future Closures: Captures of Owned variables default to move; borrow captures are allowed only if the closure cannot escape.

## Detailed Rules

### 1. Value Categories

- Trivially Copyable (TC): Fixed-size scalars with no destructor (e.g., `intN`, `floatN`, `bool`, `char`, `string`, and fixed-size arrays). Copy is bitwise; there is no drop. Borrowing a TC type is disallowed (`&int` is invalid).
- Owned / Non-Trivially Copyable (NTC): Heap-backed or resource-managing values (e.g., user-defined objects, closures). Ownership is unique; assignment/pass/return *moves* ownership. Destruction runs at drop points.

Cloning NTC values is explicit via `.clone()` or `clone(x)`.

### 2. Regions and Lifetimes

- Each lexical scope defines a region. An owned value lives in the region of its current owner.
- On scope exit, all owned values remaining in the region are dropped (reverse creation order).
- The compiler performs last-use analysis and inserts earlier drops when safe.
- TC values have no lifetime actions; they are ignored by drop logic.

Moving a value transfers it to the destination region:
- Passing to a function that takes `owned T` moves into the callee’s region.
- Returning `T` moves into the caller’s region.
- Assigning to a variable moves into that variable’s region.

### 3. Function Parameters and Returns

Parameters may be:

- `owned T`: (T is Owned) callee receives ownership; caller loses it unless returned.
- `&T`: (T is Owned) borrowed, read-only; callee cannot retain or return it in a longer-lived form.

For TC types:
- There is only pass-by-value (copy). No borrow syntax is permitted. `intN`, `bool`, etc. are always copied; moves do not invalidate the source.

Returns:
- Returning `T` (Owned) transfers ownership to the caller.
- Returning `&T` (Owned) only allowed if the referenced value is owned by the caller (non-escaping). Borrow returns of TC types are invalid (they cannot be borrowed).

Notes:
- At call sites, borrow inference applies only when the callee expects `&OwnedType`.
- Attempting to pass a TC value where `&T` is required is a type error (cannot borrow TC).

### 4. Borrowing Rules (Owned Types Only)

- Borrowing is only defined for Owned types.
- A borrowed `&OwnedType` is a non-owning, read-only view.
- A borrow cannot be stored in any owned field or global location that outlives the borrow expression/call.
- Mutability of Owned values occurs via methods on an owned receiver or a consuming pattern (no mutable borrow form yet).
- If a function must retain or store a value, it must take ownership (`owned T`) or clone inside the borrow’s scope.

### 5. Closures and Coroutines

- Capturing by move transfers ownership into the closure’s region (Owned types only).
- Capturing by borrow is only allowed for non-escaping closures and only for Owned types.
- TC values captured are copied; no borrow form exists. (TC capture has no ownership effect.)
- Escaping closures cannot have borrowed captures.

### 6. Destruction and `Drop`

- Owned (NTC) types may define `drop(this)`.
- Drops occur deterministically:
  - At last use (if provable).
  - At scope exit.
  - Along all control-flow exits (return, break, exception).
- Moves prevent duplicate drops (previous binding invalidated).
- TC values never have drops.

Example:

```firescript
File f = File.open("log.txt");
f.write("hello");
// f dropped here even on early return/exception; File.drop closes the descriptor.
```

### 7. Method Receivers

Method receiver kinds apply only to Owned types (TC methods implicitly copy the receiver):

- Borrowed receiver (default for Owned): signature form `name(...) ReturnType` implicitly receives `&OwnedType this` (read-only).
- Consuming receiver: `name(owned this, ...) ReturnType` (or `name(this, ...)`) takes ownership; caller’s binding is invalid unless the method returns it.

For TC types:
- Methods always receive the value by copy; “consuming” semantics do not apply.

Consuming example:

```firescript
Account upgrade(owned this) {
  // ... mutate internal state
  return this;
}

acct = acct.upgrade(); // rebind because ownership moved and was returned
```

### 8. Control Flow and Last Use (Owned Types)

- Conditional joins: if both branches use a value, drop inserted after merge; otherwise at last branch that uses it.
- Loops: Values used across iterations drop after loop. Iteration-temporary owned values drop at iteration end.
- TC values ignored by last-use logic (always trivially copyable).

### 9. Conversions and Sharing

- To create multiple independent owners of an Owned value: `.clone()`.
- Opt-in reference-counted or shared abstractions may be provided (e.g., `Rc<T>`, `Arc<T>`, arenas). These layer explicit runtime or bulk management semantics on top of the ownership core.
- TC values never require sharing constructs.

### 10. Interop and Backends

- Native: Drops become direct destructor calls.
- JavaScript: Destruction logic executes at specified points; underlying JS GC handles memory backing where applicable; resource closures are deterministic.

### 11. Diagnostics

- Use-after-move (Owned) is an error: primary note at move, secondary at invalid use.
- Illegal borrow of a TC type (e.g., `&int`) is an error: “Cannot borrow trivially copyable type ‘int’; pass by value.”
- Borrow escape detection flags returning or storing a borrow beyond its allowed lifetime.
- Deterministic destruction order may be visualized (tooling).

### Declaring a TC Class

A class may be annotated `copyable` to become Trivially Copyable if it satisfies:
1. All fields are TC.
2. No `drop` defined.
3. Fixed-size representation.
4. No disallowed interior references.

Example:

```firescript
copyable class Vec2 {
    float32 x; // float32 is TC
    float32 y;
}
```

`Vec2` values copy bitwise; moves do not invalidate the source.

## Examples

The following examples illustrate planned semantics. Some features (e.g., full last-use optimization) may not yet be implemented.

### Example: Move vs Copy (Takeaway: Owned moves; TC copies)

```firescript
Object o1 = Object(); // owned
Object o2 = o1;      // move; o1 invalid afterward
// print(o1);        // error: moved value

int8 x = 42;
int8 y = x;          // copy (TC); x still valid
print(x);           // OK
```

### Example: Clone (Takeaway: explicit duplication for Owned)

```firescript
string s1 = "fire";
string s2 = s1.clone(); // independent
print(s1);
print(s2);
```

### Example: Borrowed Parameter (Owned only)

```firescript
int length(&string s) {
    return s.length;
}

string name = "firescript";
int8 n = length(name); // borrow; name still valid
```

### Example: Invalid Borrow of TC (Compile Error)

```firescript
int8 id = 10;
printId(&id);   // ERROR: cannot borrow TC type 'int'; remove '&'

// Correct version:
void printId(int8 v) {
    print(v);
}
printId(id);    // copies 'id'
print(id);      // still valid
```

### Example: Owned Parameter Consumed

```firescript
void addUser(owned string username);

string u = "alice";
addUser(u);   // move; u invalid afterward
```

### Example: Returning Borrow (Owned Only, Non-Escaping)

```firescript
&string head(string[] xs) {
    return xs[0];   // OK: element owned by caller's array
}
```

### Example: Consuming Method

```firescript
Account activate(owned this) {
    // mutate state
    return this;
}

acct = acct.activate(); // rebind with returned owned value
```

---

## Summary of Borrowing Availability

| Kind | TC Types | Owned Types |
|------|----------|-------------|
| Borrow (`&T`) | Not allowed (error) | Allowed (read-only, non-owning) |
| Move | Degenerate (copy) | Transfers ownership; source invalid |
| Clone | Not needed | Explicit, creates new owner |
| Drop | Not applicable | Invokes destructor deterministically |

Borrowing is intentionally restricted to Owned types to:
1. Preserve simplicity (no redundant alias form for scalars).
2. Keep ownership-focused diagnostics clear.
3. Avoid needless syntactic noise for trivially cheap copies.

If a future revision broadens TC to include large POD aggregates, this restriction may be reconsidered; until then it is normative.
