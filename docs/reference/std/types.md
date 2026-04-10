# Generic Types (`std.types`)

The `std.types` module provides generic container and utility types.

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

Tuple<int32, string> pair = Tuple(42, "answer");
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

CopyableTuple<float64, float64> coord = CopyableTuple(3.14, 2.71);
CopyableTuple<float64, float64> copy = coord;  // copies
```

## `Option<T>`

An optional value of type `T`. Use this to represent potentially missing values without explicit nullability.

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

```firescript
import @firescript/std.types.Option;
import @firescript/std.io.println;

Option<string> maybe_name = Option("Alice");
if (maybe_name.isSome()) {
    println("Name: " + maybe_name.value);
}

Option<string> none_name = Option(null);
if (none_name.isNone()) {
    println("No name provided");
}
```

**Note:** `Option` is an Owned type; construct carefully with move semantics in mind.

## `CopyableOption<T>`

A copyable variant of `Option` for copyable types.

```firescript
copyable class CopyableOption<nullable T> {
    nullable T value;
    
    CopyableOption(nullable T value);
    
    bool isSome();
    bool isNone();
}
```

**Example:**

```firescript
import @firescript/std.types.CopyableOption;

CopyableOption<int32> maybe_count = CopyableOption(5);
if (maybe_count.isSome()) {
    println("Count: " + maybe_count.value);
}
```

## Usage Notes

- **Prefer `CopyableTuple` and `CopyableOption`** for numeric/scalar types to avoid unnecessary moves.
- **Use owned variants** for containers or strings that you want to pass around differently.
- Both variants support generic type parameters; compile-time monomorphization produces efficient code.

## Example

```firescript
import @firescript/std.types.Tuple;
import @firescript/std.types.Option;
import @firescript/std.io.println;

// Tuple usage
Tuple<int32, string> user = Tuple(1, "alice");
println("User ID: " + user.first);

// Option usage
Option<string> bio = Option("Software engineer");
if (bio.isSome()) {
    println("Bio: " + bio.value);
}
```
