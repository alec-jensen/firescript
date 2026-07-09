# Math (`std.math`)

The `std.math` module provides basic mathematical utilities.

> Status: `abs`, `min`, `max`, and `clamp` are exported and importable today. The module also contains trigonometry, `sqrt`, `pow`, angle-conversion helpers, and a large set of mathematical constants, but those are **not yet exported** and cannot be imported from user code — they are listed at the bottom of this page as [IN DEVELOPMENT].

## Numeric Constraint

The exported functions are generic over the `Numeric` constraint, a type union covering all integer and floating-point types:

```
Numeric = int8 | int16 | int32 | int64 | uint8 | uint16 | uint32 | uint64 | float32 | float64 | float128
```

Because the functions are generic, all arguments in a call must share the same type.

## Functions

### `abs(T x, T zero)`

Return the absolute value of `x`. The second argument supplies the zero value for the type (e.g., `0` for `int32`, `0.0` for `float64`).

```firescript
import @firescript/std.math.abs;

int32 v = abs(-42, 0);           // 42
float64 f = abs(-3.14, 0.0);     // 3.14
```

### `min(T a, T b)`

Return the smaller of two values.

```firescript
import @firescript/std.math.min;

int32 result = min(5, 3);        // 3
```

### `max(T a, T b)`

Return the larger of two values.

```firescript
import @firescript/std.math.max;

int32 result = max(5, 3);        // 5
```

### `clamp(T x, T lo, T hi)`

Constrain `x` to the range [lo, hi].

```firescript
import @firescript/std.math.clamp;

int32 result = clamp(10, 0, 5);  // 5
```

You can also import several symbols at once:

```firescript
import @firescript/std.math.{max, min, abs, clamp}
```

## Example

```firescript
import @firescript/std.math.{max, min, clamp};
import @firescript/std.io.println;

int32 biggest = max(3, 7);
float64 smallest = min(2.5, 1.5);
int32 bounded = clamp(15, 0, 10);

println(biggest);   // 7
println(smallest);  // 1.5
println(bounded);   // 10
```

> Note: assign the result of a generic call to a variable before passing it to another generic function (like `println`). Nesting generic calls directly (e.g., `println(max(3, 7))`) currently fails to compile — a known limitation.

## Not Yet Exported [IN DEVELOPMENT]

The following exist in the module sources but are private (not `export`ed), so they cannot be imported yet:

- **Functions** (`firescript/std/math/init.fire`): `sqrt`, `pow`, `pow_int`, `sin`, `cos`, `tan`, `lerp`, `deg_to_rad`, `rad_to_deg`
- **Constants** (`firescript/std/math/constants.fire`): precision-specific constants for pi (`PI32`/`PI64`/`PI128`, plus `PI_2_*`, `PI_4_*`, `INV_PI*`, `SQRT_PI*`, `LN_PI*`), Euler's number (`E*`, `LOG2_E*`, `LOG10_E*`), natural logs (`LN_2_*`, `LN_10_*`), square roots (`SQRT_2_*`, `SQRT_3_*`, `SQRT_1_2_*`), special constants (`EULER_GAMMA*`, `PHI*`, `CATALAN*`), and degree/radian conversion multipliers (`DEG_TO_RAD*`, `RAD_TO_DEG*`)

These will be documented here once they are exported and tested.
