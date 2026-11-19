# Collections (`std.collections`)

The `std.collections` module provides `ArrayList<T>` (a dynamically-growable array) and
`HashMap<K,V>` (a hash table).

> Status: `ArrayList<T>` `add`/`removeLast`/`get`/`set`/`size`/`enumerate` and `HashMap<K,V>`
> `set`/`get`/`has`/`remove`/`size` are all [IMPLEMENTED] and tested.

## `ArrayList<T>`

```firescript
class ArrayList<T> {
    fn ArrayList(&mut this);

    fn size(&this) -> int32;

    fn add(&mut this, value: T);
    fn removeLast(&mut this) -> T;

    fn get(&this, i: int32) -> T;
    fn set(&mut this, i: int32, value: T);
}
```

**Example:**

```firescript
import @firescript/std.collections.ArrayList;
import @firescript/std.io.println;

v: ArrayList<int32> = ArrayList<int32>();
v.add(10);
v.add(20);
v.add(30);
println(v.size());   // 3
println(v.get(1));     // 20

v.set(1, 99);
println(v.get(1));     // 99

last: int32 = v.removeLast();
println(last);          // 30
println(v.size());   // 2
```

**Methods:**

- `size()`: Number of elements currently stored.
- `add(value)`: Appends `value`, growing the backing buffer (capacity doubles, starting
  at 4) if needed.
- `removeLast()`: Removes and returns the last element; safe to call on an `ArrayList<T>`
  of any `T`, including an Owned type. Traps (`IndexOutOfBounds: index -1, length 0`) on an
  empty list.
- `get(i)` / `set(i, value)`: Read or overwrite the element at index `i`. `i` must be in
  `[-size(), size())` (a negative index counts from the end, as for core arrays); anything
  else, including an index inside the spare capacity, traps with
  `firescript runtime error: IndexOutOfBounds: index N, length L` [IMPLEMENTED].

### Owned vs. Copyable element types

`ArrayList<T>` itself is an Owned type. Its destructor always frees its own backing buffer,
and (via a compiler-internal `@owns_elements` mechanism) also drops each live element
first when `T` is itself an Owned type (a class or `string`) -- so `add`/`removeLast`/`set`
are safe for any `T`.

**`get()` (and therefore `enumerate<T>`, which calls `get()` internally) is only safe
for Copyable-ish `T`** (numeric types, `bool`, `char`). `get()` reads an element out by
value *without* removing it from the `ArrayList`, so for an Owned `T` the returned value and
the `ArrayList`'s own copy would alias the same heap allocation -- both the caller and the
`ArrayList`'s eventual destructor would try to free it, a double-free. firescript does not yet
have `Owned`/`Copyable` generic constraints to enforce this restriction at the type
level (planned for a future release; see `docs/internal/version_planning.md`'s 0.7.0
"Wyvern" milestone), so it isn't enforced by the compiler today -- calling `get()` on a
`ArrayList` of an Owned `T` will compile, but risks a runtime double-free.

**Example (Owned element type, `add`/`removeLast`/`set` only):**

```firescript
import @firescript/std.collections.ArrayList;
import @firescript/std.io.println;

names: ArrayList<string> = ArrayList<string>();
names.add("Alice");
names.add("Bob");
names.set(1, "Robert");
last: string = names.removeLast();
println(last);            // Robert
println(names.size());  // 1
```

## `enumerate<T>`

```firescript
fn enumerate<T>(&v: ArrayList<T>) -> generator<Pair<int32, T>>;
```

Yields `(index, value)` pairs as `Pair<int32, T>` while iterating an `ArrayList<T>`. Calls
`get()` internally, so it's subject to the same Copyable-`T` caveat above.

```firescript
import @firescript/std.collections.ArrayList;
import @firescript/std.collections.enumerate;
import @firescript/std.types.Pair;
import @firescript/std.io.println;

v: ArrayList<int32> = ArrayList<int32>();
v.add(10);
v.add(20);
v.add(30);

for (pair: Pair<int32, int32> in enumerate(v)) {
    println(pair.first);   // index
    println(pair.second);  // value
}
```

## `HashMap<K,V>`

```firescript
class HashMap<K, V> {
    fn HashMap(&mut this);

    fn size(&this) -> int32;

    fn set(&mut this, key: K, value: V);
    fn has(&this, key: K) -> bool;
    fn get(&mut this, key: K) -> V;
    fn remove(&mut this, key: K) -> V;
}
```

An open-addressing hash table with linear probing and tombstones, growing (capacity
doubles, starting at 8) when the load factor crosses 70%.

**Example:**

```firescript
import @firescript/std.collections.HashMap;
import @firescript/std.io.println;

ages: HashMap<string, int32> = HashMap<string, int32>();
ages.set("Alice", 30);
ages.set("Bob", 25);
println(ages.size());        // 2
println(ages.has("Alice"));    // true
println(ages.get("Alice"));    // 30

ages.set("Alice", 31);         // overwrite
println(ages.get("Alice"));    // 31

removed: int32 = ages.remove("Bob");
println(removed);              // 25
println(ages.has("Bob"));      // false
```

**Methods:**

- `size()`: Number of entries currently stored.
- `set(key, value)`: Inserts or overwrites the entry for `key`.
- `has(key)`: Returns whether `key` is present.
- `get(key)` / `remove(key)`: Only well-defined when `has(key)` is `true` first -- like
  core array indexing (and `ArrayList<T>.get()`), there's no presence check. Calling either for
  an absent key reads whatever currently occupies the slot probing would have chosen for
  an insert, which for a removed slot can be a stale, already-moved-out pointer for an
  Owned `V`. Always check `has()` first.
  - `remove(key)` moves the stored value out and marks the slot a tombstone in the same
    operation, so it's safe to call for any `V` (Owned or Copyable) -- matching
    `ArrayList<T>.removeLast()`'s equivalent safety argument.
  - `get(key)` reads the value out *without* removing it, so (like `ArrayList<T>.get()`) it's
    only safe for Copyable-ish `V` (numeric types, `bool`, `char`) -- for an Owned `V` the
    returned copy and the map's own copy would alias the same allocation.

### Key type restrictions

`HashMap<K,V>` is restricted to a fixed hashable key set: integer types (`int8`..`uint64`),
`bool`, `char`, and `string`. firescript has no `Hashable` trait to dispatch hashing
through generically yet (planned for a future release alongside `Owned`/`Copyable`
generic constraints; see `docs/internal/version_planning.md`'s 0.7.0 "Wyvern" milestone).
Instantiating `HashMap<K,V>` with any other `K` and then actually using it (`set`/`get`/
`has`/`remove`) is a compile-time error, not a silent miscompile.

### Why no `Option<V>` for "not found"?

`get()`/`remove()` return `V` directly rather than `Option<V>` -- use `has()` first (or, for
`remove()`, rely on it being safe to call unconditionally; see above). This is no longer a
representation-gap workaround: nullable *scalar* types now carry a real "has a value" tag
(see `docs/changelog.md`'s 0.6.0 entry), so `Option<V>(null)` vs. `Option<V>(value)` is
correctly distinguishable for any `V`, including primitives. Switching `get()`/`remove()` to
return `Option<V>` is a viable, purely additive follow-up (it doesn't need any further compiler
work) -- it just hasn't been done in this release, to keep this change scoped to the
compiler-level fix.

## Usage Notes

- `ArrayList<T>`/`HashMap<K,V>` are built on compiler intrinsics private to `std/collections/`:
  `fs_rt_array_new<T>`/`fs_rt_array_copy<T>` allocate/copy a `T[]` buffer of a
  runtime-determined element count (ordinary fixed-size arrays can only be sized by a
  compile-time literal), and `fs_rt_hash<K>` computes a key's hash, dispatched by concrete
  `K` at compile time. These are not user-facing API.
- `Stack<T>`, `Queue<T>`, and `Deque<T>` are planned follow-ups (see
  `docs/internal/version_planning.md`'s 0.6.0 "Griffin" milestone) -- not yet implemented.
