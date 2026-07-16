# Generic Types (`std.types`)

The `std.types` module provides generic container and utility types.

> Status: `Tuple`, `CopyableTuple`, `Option`, and `CopyableOption` are all [IMPLEMENTED] and tested.

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

## Usage Notes

- **Prefer `CopyableTuple` and `CopyableOption`** for numeric/scalar types to avoid unnecessary moves.
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
