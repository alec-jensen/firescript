# Memory Management

*Warning: Memory management in firescript is still being refined and none of this is implemented yet. This document may change.*

firescript provides automatic memory management without a garbage collector. The language uses ownership, move semantics, and compile-time last-use analysis to insert deterministic destruction ("drop") points. No runtime reference counting is required for ordinary values.

This document is normative.

## 1. Value Categories

- Trivially Copyable (TC): fixed-size scalars with no destructor (e.g., `int`, `float`, `double`, `bool`, `char`). Copy is bitwise; there is no drop.
- Owned (NON-TC): heap-backed or resource-managing values (e.g., `string`, arrays, user-defined objects, closures). Ownership is unique; assignment/pass/return moves ownership. Destruction runs at drop.

Cloning NON-TC values is explicit via `.clone()` or `clone(x)`.

## 2. Regions and Lifetimes

- Each lexical scope defines a region. An owned value lives in the region of its current owner.
- On scope exit, all owned values remaining in the region are dropped (in reverse creation order).
- The compiler performs last-use analysis and inserts drops at the final use site whenever earlier than scope end.

Moving a value transfers it to the destination region:
- Passing to a function that takes `owned T` moves into the callee’s region.
- Returning `T` moves into the caller’s region.
- Assigning to a variable moves into that variable’s region.

## 3. Function Parameters and Returns

Parameters may be:
- `owned T`: the callee receives ownership and may retain. The caller loses ownership unless it is returned.
- `&T` (borrowed, read-only): the callee may not retain nor return it; it cannot escape the call.

Returns:
- Returning `T` transfers ownership to the caller.
- Returning `&T` is only allowed if the reference points to a value owned by the caller (non-escaping borrow). The compiler enforces this; otherwise, the program is ill-formed.

Notes:
- In most cases, `&T` borrows are inferred at call sites and require no annotation in the call expression.

## 4. Borrowing Rules (No Runtime Cost)

- A borrowed `&T` is a non-owning, read-only view.
- A borrowed value cannot be stored in any owned location nor outlive the call/borrow expression.
- Mutability of NON-TC values is provided through methods on the owned value; borrowed views are read-only.

If a function needs to retain data beyond the call, it must take `owned T` or explicitly clone a borrowed value.

## 5. Closures and Coroutines

- Capturing by move transfers ownership into the closure’s region; the closure becomes the owner.
- Capturing by borrow is allowed only for non-escaping closures proven not to outlive the enclosing scope.
- Escaping closures must capture by move (or clone). The compiler rejects escaping borrowed captures.

## 6. Destruction and `Drop`

- NON-TC types may define a `drop(this)` destructor. The compiler calls `drop` at each inserted drop point.
- Drops occur deterministically:
  - At last use (if provable).
  - At scope exit (for remaining owned values).
  - Along all control-flow exits (return, break, exception).
- Drops are never duplicated. Moving a value disables its previous owner’s drop.

Resource safety:
```firescript
File f = File.open("log.txt");
f.write("hello");
// f dropped here even on early return/exception; File.drop closes the descriptor.
```

## 7. Control Flow and Last Use

The compiler uses non-lexical lifetimes:
- In conditional branches, drops are placed after the join point if both branches use the value; otherwise, after the last using branch.
- In loops, values used within the body are not dropped until the loop finishes; per-iteration owned temporaries are dropped at the end of each iteration.

## 8. Conversions and Sharing

- To create multiple long-lived aliases of a NON-TC value, use explicit `.clone()` (deep or copy-on-write as defined by the type).
- The standard library may offer sharing containers with explicit semantics:
  - `Rc<T>`: single-threaded shared ownership (runtime refcount).
  - `Arc<T>`: multi-threaded shared ownership (atomic refcount).
  - Arenas/pools for graph-like structures with bulk free.

These are opt-in; ordinary values incur no runtime reference counting.

## 9. Interop and Backends

- Native: destruction translates to direct calls; memory is reclaimed immediately.
- JavaScript: destruction calls run at the same program points; memory reclamation of underlying JS objects is delegated to the JS runtime, but resources (files, sockets) are still closed deterministically.

## 10. Diagnostics

- Use-after-move is a compile error with a primary note at the move site and a secondary note at the later use.
- Borrow escape violations point to the escaping store/return site.
- Destruction order is well-defined; tools may visualize last-use/drop points.

## 11. Examples

### Moves and clone

```firescript
string a = "hello";
string b = a;       // move: a is now invalid
print(b);
// print(a);        // error: use of moved value 'a'

string c = b.clone(); // explicit clone
print(b);
print(c);             // both valid, independent
```

### Borrowed parameter (inferred at call)

```firescript
// Signature says we only borrow; cannot retain
int length(&string s) {
    return s.length;
}

string name = "firescript";
int n = length(name); // ok; name is still valid afterwards
```

### Owned parameter (consumes)

```firescript
// Takes ownership and retains internally
void addUser(owned string username);

string u = "alice";
addUser(u);    // move: 'u' invalid after call
// print(u);   // error
```

### Returning references (non-escaping)

```firescript
&string head(&string[] xs) {
    return xs[0]; // ok: refers to caller-owned array element
}
```
