# Generic Types (`std.types`)

The `std.types` module provides generic container and utility types.

> Status: `Pair`, `CopyablePair`, `Option`, `CopyableOption`, `Result`, and `CopyableResult` are all [IMPLEMENTED] and tested.

## `Pair<T, U>`

A pair of values of potentially different types.

```firescript
class Pair<T, U> {
    first: T;
    second: U;

    fn Pair(&mut this, first: T, second: U);
}
```

**Example:**

```firescript
import @firescript/std.types.Pair;
import @firescript/std.io.println;

pair: Pair<int32, string> = Pair<int32, string>(42, "answer");
println(pair.first);   // 42
println(pair.second);  // answer
```

**Note:** `Pair` is an Owned type; values are moved, not copied.

## `CopyablePair<T, U>`

A copyable variant of `Pair` for use with copyable types only.

```firescript
copyable class CopyablePair<T, U> {
    first: T;
    second: U;

    fn CopyablePair(&mut this, first: T, second: U);
}
```

**Example:**

```firescript
import @firescript/std.types.CopyablePair;

coord: CopyablePair<float64, float64> = CopyablePair<float64, float64>(3.14, 2.71);
copy: CopyablePair<float64, float64> = coord;  // copies
```

## `Option<T>` [IMPLEMENTED]

An optional value of type `T`. Use this to represent potentially missing values without explicit nullability.

```firescript
class Option<T?> {
    value: T?;

    fn Option(&mut this, value: T?);

    fn isSome(&this) -> bool;
    fn isNone(&this) -> bool;

    static fn Some(value: T) -> Option<T>;
    static fn None() -> Option<T>;

    fn unwrapOr(&mut this, default: T) -> T;
}
```

**Methods:**

- `isSome()`: Returns `true` if a value is present
- `isNone()`: Returns `true` if no value is present
- `Some(value)`: Static factory for a present value. Infers `T` from `value`, so it works bare (`Option.Some(5)`).
- `None()`: Static factory for an absent value. Takes no argument to infer `T` from — use the explicit form, `Option<int32>.None()`.
- `unwrapOr(default)`: Returns the value if present, else `default`. **Drains the Option** — extracts the value by nulling out the field, so `isSome()` reads `false` immediately afterward. Safe for any `T`, including Owned types (the same aliasing hazard `ArrayList<T>.get()` has for an Owned element is avoided here the way `ArrayList<T>.removeLast()` avoids it — see [Collections](collections.md)).

**Example:**

```firescript
import @firescript/std.types.Option;
import @firescript/std.io.println;

maybe_name: Option<string> = Option.Some("Alice");
if (maybe_name.isSome()) {
    println(maybe_name.unwrapOr("unknown"));
}

nothing: Option<string> = Option<string>.None();
println(nothing.unwrapOr("fallback"));  // fallback
```

**Note:** `Option` is an Owned type; construct carefully with move semantics in mind.

## `CopyableOption<T>` [IMPLEMENTED]

A copyable variant of `Option` for copyable types.

```firescript
copyable class CopyableOption<T?> {
    value: T?;

    fn CopyableOption(&mut this, value: T?);

    fn isSome(&this) -> bool;
    fn isNone(&this) -> bool;

    static fn Some(value: T) -> CopyableOption<T>;
    static fn None() -> CopyableOption<T>;

    fn unwrapOr(&this, default: T) -> T;
}
```

`unwrapOr` here doesn't drain anything — Copyable values are just read, not extracted, so the option is left intact and can be read again.

**Example:**

```firescript
import @firescript/std.types.CopyableOption;
import @firescript/std.io.println;

maybe_count: CopyableOption<int32> = CopyableOption.Some(5);
println(maybe_count.unwrapOr(0));
```

## `Result<T,E>` [IMPLEMENTED]

A value that is either a success (`T`) or a failure (`E`). Use this to represent operations that can fail without relying on exceptions or sentinel values.

```firescript
class Result<T?, E?> {
    value: T?;
    error: E?;

    fn Result(&mut this, value: T?, error: E?);

    fn isOk(&this) -> bool;
    fn isErr(&this) -> bool;

    static fn Ok(value: T) -> Result<T, E>;
    static fn Err(error: E) -> Result<T, E>;

    fn unwrapOr(&mut this, default: T) -> T;
}
```

**Methods:**

- `isOk()`: Returns `true` if the result holds a success value
- `isErr()`: Returns `true` if the result holds an error value
- `Ok(value)` / `Err(error)`: Static factories. Neither infers *both* type parameters from its own argument (`Ok` never mentions `E`; `Err` never mentions `T`) — always use the explicit form, `Result<T,E>.Ok(x)` / `Result<T,E>.Err(e)`.
- `unwrapOr(default)`: Returns the success value if present, else `default`. Drains the `Result` the same way `Option<T>.unwrapOr()` does — see its note above.

```firescript
import @firescript/std.types.Result;
import @firescript/std.io.println;

fn tryDivide(a: int32, b: int32) -> Result<int32, string> {
    if (b == 0) {
        return Result<int32, string>.Err("division by zero");
    }
    return Result<int32, string>.Ok(a / b);
}

outcome: Result<int32, string> = tryDivide(10, 0);
println(outcome.unwrapOr(-1));  // -1
```

**Note:** `Result` is an Owned type; construct carefully with move semantics in mind.

## `CopyableResult<T,E>` [IMPLEMENTED]

A copyable variant of `Result` for copyable types.

```firescript
copyable class CopyableResult<T?, E?> {
    value: T?;
    error: E?;

    fn CopyableResult(&mut this, value: T?, error: E?);

    fn isOk(&this) -> bool;
    fn isErr(&this) -> bool;

    static fn Ok(value: T) -> CopyableResult<T, E>;
    static fn Err(error: E) -> CopyableResult<T, E>;

    fn unwrapOr(&this, default: T) -> T;
}
```

**Example:**

```firescript
import @firescript/std.types.CopyableResult;
import @firescript/std.io.println;

parsed: CopyableResult<int32, bool> = CopyableResult<int32, bool>.Ok(42);
println(parsed.unwrapOr(-1));
```

## Usage Notes

- **Prefer `CopyablePair`, `CopyableOption`, and `CopyableResult`** for numeric/scalar types to avoid unnecessary moves.
- **Use owned variants** for containers or strings that you want to pass around differently.
- Both variants support generic type parameters; compile-time monomorphization produces efficient code.

## Example

```firescript
import @firescript/std.types.Pair;
import @firescript/std.io.println;

// Pair usage
user: Pair<int32, string> = Pair<int32, string>(1, "alice");
println("User ID: " + (user.first as string));
println(user.second);
```
