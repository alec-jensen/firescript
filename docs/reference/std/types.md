# Generic Types (`std.types`)

The `std.types` module provides generic container and utility types.

> Status: `Tuple` and `CopyableTuple` are [IMPLEMENTED] and tested. `Option` and `CopyableOption` are [IN DEVELOPMENT]: they compile, but `isSome()`/`isNone()` currently return incorrect results (a known bug in generic-class methods that compare a nullable field to `null`), so they should not be relied on yet.

## `Tuple<T, U>`

A pair of values of potentially different types.

```firescript
class Tuple<T, U> {
    T first;
    U second;
    
    Tuple(T first, U second);
}
```

**Example:**

```firescript
import @firescript/std.types.Tuple;
import @firescript/std.io.println;

Tuple<int32, string> pair = Tuple<int32, string>(42, "answer");
println(pair.first);   // 42
println(pair.second);  // answer
```

**Note:** `Tuple` is an Owned type; values are moved, not copied.

## `CopyableTuple<T, U>`

A copyable variant of `Tuple` for use with copyable types only.

```firescript
copyable class CopyableTuple<T, U> {
    T first;
    U second;
    
    CopyableTuple(T first, U second);
}
```

**Example:**

```firescript
import @firescript/std.types.CopyableTuple;

CopyableTuple<float64, float64> coord = CopyableTuple<float64, float64>(3.14, 2.71);
CopyableTuple<float64, float64> copy = coord;  // copies
```

## `Option<T>` [IN DEVELOPMENT]

An optional value of type `T`. Use this to represent potentially missing values without explicit nullability. **Known issue:** `isSome()` and `isNone()` currently return incorrect results; prefer plain `nullable` variables until this is fixed.

```firescript
class Option<nullable T> {
    nullable T value;
    
    Option(nullable T value);
    
    bool isSome();
    bool isNone();
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

Option<string> maybe_name = Option<string>("Alice");
bool present = maybe_name.isSome();
if (present) {
    println(maybe_name.value);
}
```

**Note:** `Option` is an Owned type; construct carefully with move semantics in mind.

## `CopyableOption<T>` [IN DEVELOPMENT]

A copyable variant of `Option` for copyable types. Subject to the same known issue as `Option`.

```firescript
copyable class CopyableOption<nullable T> {
    nullable T value;
    
    CopyableOption(nullable T value);
    
    bool isSome();
    bool isNone();
}
```

**Example:**

Intended usage (see the known issue above):

```firescript
import @firescript/std.types.CopyableOption;
import @firescript/std.io.println;

CopyableOption<int32> maybe_count = CopyableOption<int32>(5);
bool present = maybe_count.isSome();
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
Tuple<int32, string> user = Tuple<int32, string>(1, "alice");
println("User ID: " + (user.first as string));
println(user.second);
```
