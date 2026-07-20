# Generic Types (`std.types`)

The `std.types` module provides generic container and utility types.

> Status: `Tuple`, `CopyableTuple`, `Option`, `CopyableOption`, `Result`, and `CopyableResult` are all [IMPLEMENTED] and tested.

## `Tuple<T, U>`

A pair of values of potentially different types.

```firescript
class Tuple<T, U> {
    first: T;
    second: U;

    fn Tuple(first: T, second: U);
}
```

**Example:**

```firescript
import @firescript/std.types.Tuple;
import @firescript/std.io.println;

pair: Tuple<int32, string> = Tuple<int32, string>(42, "answer");
println(pair.first);   // 42
println(pair.second);  // answer
```

**Note:** `Tuple` is an Owned type; values are moved, not copied.

## `CopyableTuple<T, U>`

A copyable variant of `Tuple` for use with copyable types only.

```firescript
copyable class CopyableTuple<T, U> {
    first: T;
    second: U;

    fn CopyableTuple(first: T, second: U);
}
```

**Example:**

```firescript
import @firescript/std.types.CopyableTuple;

coord: CopyableTuple<float64, float64> = CopyableTuple<float64, float64>(3.14, 2.71);
copy: CopyableTuple<float64, float64> = coord;  // copies
```

## `Option<T>` [IMPLEMENTED]

An optional value of type `T`. Use this to represent potentially missing values without explicit nullability.

```firescript
class Option<T?> {
    value: T?;

    fn Option(value: T?);

    fn isSome() -> bool;
    fn isNone() -> bool;
}
```

**Methods:**

- `isSome()`: Returns `true` if a value is present
- `isNone()`: Returns `true` if no value is present

**Example:**

Intended usage (see the known issue above):

```firescript
import @firescript/std.types.Option;
import @firescript/std.io.println;

maybe_name: Option<string> = Option<string>("Alice");
present: bool = maybe_name.isSome();
if (present) {
    println(maybe_name.value);
}
```

**Note:** `Option` is an Owned type; construct carefully with move semantics in mind.

## `CopyableOption<T>` [IMPLEMENTED]

A copyable variant of `Option` for copyable types.

```firescript
copyable class CopyableOption<T?> {
    value: T?;

    fn CopyableOption(value: T?);

    fn isSome() -> bool;
    fn isNone() -> bool;
}
```

**Example:**

Intended usage (see the known issue above):

```firescript
import @firescript/std.types.CopyableOption;
import @firescript/std.io.println;

maybe_count: CopyableOption<int32> = CopyableOption<int32>(5);
present: bool = maybe_count.isSome();
if (present) {
    println(maybe_count.value);
}
```

## `Result<T,E>` [IMPLEMENTED]

A value that is either a success (`T`) or a failure (`E`). Use this to represent operations that can fail without relying on exceptions or sentinel values.

```firescript
class Result<T?, E?> {
    value: T?;
    error: E?;

    fn Result(value: T?, error: E?);

    fn isOk() -> bool;
    fn isErr() -> bool;
}
```

**Methods:**

- `isOk()`: Returns `true` if the result holds a success value
- `isErr()`: Returns `true` if the result holds an error value

**Note:** There are no `Result.Ok(value)` / `Result.Err(error)` static factory methods — static methods on generic classes are not yet supported by the compiler (calling one either fails to parse, with explicit type arguments, or crashes the compiler, with inferred type arguments). Construct a `Result` directly instead, passing `null` for the unused side:

```firescript
import @firescript/std.types.Result;
import @firescript/std.io.println;

fn tryDivide(a: int32, b: int32) -> Result<int32, string> {
    if (b == 0) {
        return Result<int32, string>(null, "division by zero");
    }
    return Result<int32, string>(a / b, null);
}

outcome: Result<int32, string> = tryDivide(10, 0);
if (outcome.isErr()) {
    println(outcome.error);
}
```

**Note:** `Result` is an Owned type; construct carefully with move semantics in mind.

## `CopyableResult<T,E>` [IMPLEMENTED]

A copyable variant of `Result` for copyable types.

```firescript
copyable class CopyableResult<T?, E?> {
    value: T?;
    error: E?;

    fn CopyableResult(value: T?, error: E?);

    fn isOk() -> bool;
    fn isErr() -> bool;
}
```

**Example:**

```firescript
import @firescript/std.types.CopyableResult;
import @firescript/std.io.println;

parsed: CopyableResult<int32, bool> = CopyableResult<int32, bool>(42, null);
if (parsed.isOk()) {
    println(parsed.value);
}
```

## Usage Notes

- **Prefer `CopyableTuple`, `CopyableOption`, and `CopyableResult`** for numeric/scalar types to avoid unnecessary moves.
- **Use owned variants** for containers or strings that you want to pass around differently.
- Both variants support generic type parameters; compile-time monomorphization produces efficient code.

## Example

```firescript
import @firescript/std.types.Tuple;
import @firescript/std.io.println;

// Tuple usage
user: Tuple<int32, string> = Tuple<int32, string>(1, "alice");
println("User ID: " + (user.first as string));
println(user.second);
```
