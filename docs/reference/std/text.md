# Text (`std.text`)

The `std.text` module provides `StringBuilder` (efficient accumulation of many string
fragments) and `split` (dividing a string on a delimiter).

> Status: `StringBuilder` (`append`/`length`/`build`) and `split` are both [IMPLEMENTED]
> and tested.

## `StringBuilder`

```firescript
class StringBuilder {
    fn StringBuilder(initial: string);

    fn append(&mut this, s: string) -> void;
    fn length(&this) -> int32;
    fn build(&mut this) -> string;
}
```

**Example:**

```firescript
import @firescript/std.text.StringBuilder;
import @firescript/std.io.println;

sb: StringBuilder = StringBuilder("");
sb.append("Hello");
sb.append(", ");
sb.append("World");
sb.append("!");
println(sb.length());  // 13
println(sb.build());   // Hello, World!
println(sb.length());  // 0 -- build() drains the builder
```

**Methods:**

- `append(s)`: Adds `s` to the end of the accumulated content. Takes ownership of `s`
  (matching `Vec<T>.push()`).
- `length()`: Total character count of everything appended so far, tracked incrementally
  (not recomputed by summing fragments).
- `build()`: Joins every appended fragment into a single string and returns it, **draining
  the builder** -- `length()` reads `0` immediately afterward. Not safe to call more than
  once expecting cumulative content; append more first if you need to keep building.

**Note:** `StringBuilder` has no zero-argument constructor -- pass `""` to start empty
(`StringBuilder("")`). A bare `ClassName()` constructor call for a class imported from
another module isn't reliably resolved by the compiler yet; see
`tests/sources/known_issues/zero_arg_constructor_bare_call_error.fire`. `StringBuilder`'s
constructor takes a real argument instead, which sidesteps this.

### Implementation notes

`StringBuilder` is backed by a `Vec<string>` of fragments rather than a raw growable byte
buffer -- string primitives (`std/internal/strings.fire`) have no way to construct a
`Vec<T>` themselves (internal runtime files carry no import statements), so building on
the already-public `Vec<T>` was the straightforward option. `build()` drains fragments
with `Vec<T>.pop()` rather than `get()`/`enumerate()`, which aren't safe for an Owned
element type like `string` (see [Collections](collections.md)'s note on `get()`).

## `split`

```firescript
fn split(&s: string, &delim: string) -> Vec<string>;
```

Splits `s` on every occurrence of `delim`, including leading, trailing, and adjacent
empty fields. An empty `delim` returns a single-element `Vec` containing the whole string
unchanged. If `delim` never occurs, the result is a single-element `Vec` containing `s`.

**Example:**

```firescript
import @firescript/std.text.split;
import @firescript/std.collections.Vec;
import @firescript/std.io.println;

parts: Vec<string> = split("a,bb,ccc", ",");
println(parts.length());  // 3
println(parts.pop());     // ccc -- pop() drains in reverse order
println(parts.pop());     // bb
println(parts.pop());     // a
```

**Note:** `split` isn't a `.split()` dot-method on `string` like `.indexOf()`/
`.substring()`/etc. (see the [strings feature table entry](../../../CLAUDE.md) for the
full list) -- it needs to return `Vec<string>`, and the compiler's `@builtin_method`
dispatch (used for those other string methods) only supports backing functions defined in
`std/internal/`, which can't reference `Vec<T>` (a normal importable module, not an
internal runtime file). Called as a plain function instead: `split(s, delim)`.

## Usage Notes

- Draining a `Vec<string>` (via `StringBuilder.build()` internally, or directly from
  `split`'s result) should always go through `pop()`, never `get()`/`enumerate()` -- see
  [Collections](collections.md) for why.
