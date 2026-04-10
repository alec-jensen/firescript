# Math (`std.math`)

The `std.math` module provides mathematical functions and mathematical constants across various floating-point precisions.

## Numeric Constraint

Most functions work with the `Numeric` constraint, which includes all integer and floating-point types:

```
Numeric = int8 | int16 | int32 | int64 | uint8 | uint16 | uint32 | uint64 | float32 | float64 | float128
```

## Functions

### `abs(T x, T zero)`

Return the absolute value of `x`.

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

### `sqrt(float64 x)`

Return the square root of `x` (Newton's method approximation).

```firescript
import @firescript/std.math.sqrt;

float64 two_root = sqrt(2.0);    // ≈ 1.414
```

### `pow(float64 base, int32 exp)`

Raise `base` to integer power `exp`.

```firescript
import @firescript/std.math.pow;

float64 squared = pow(3.0, 2);   // 9.0
```

### `sin(float64 x)`, `cos(float64 x)`, `tan(float64 x)`

Trigonometric functions (input in radians).

```firescript
import @firescript/std.math.sin;
import @firescript/std.math.cos;
import @firescript/std.math.PI64;

float64 s = sin(PI64 / 2.0);     // ≈ 1.0
float64 c = cos(0.0);             // 1.0
```

### `deg_to_rad(float64 degrees)`, `rad_to_deg(float64 radians)`

Convert between degrees and radians.

```firescript
import @firescript/std.math.deg_to_rad;

float64 rad = deg_to_rad(180.0);  // ≈ PI
```

## Mathematical Constants

The module exports precision-specific constants for pi, e, and other common values.

### Pi Constants

```firescript
import @firescript/std.math.PI32;
import @firescript/std.math.PI64;
import @firescript/std.math.PI128;
```

- `PI32`: float32 approximation
- `PI64`: float64 approximation
- `PI128`: float128 approximation
- `PI_2_32`, `PI_2_64`, `PI_2_128`: Pi/2
- `PI_4_32`, `PI_4_64`, `PI_4_128`: Pi/4

### Euler's Number (e)

```firescript
import @firescript/std.math.E32;
import @firescript/std.math.E64;
import @firescript/std.math.E128;
```

### Logarithm Constants

- `LN_2_32`, `LN_2_64`, `LN_2_128`: Natural log of 2
- `LN_10_32`, `LN_10_64`, `LN_10_128`: Natural log of 10
- `LOG2_E32`, `LOG2_E64`, `LOG2_E128`: Base-2 log of e
- `LOG10_E32`, `LOG10_E64`, `LOG10_E128`: Base-10 log of e

### Square Root Constants

- `SQRT_2_32`, `SQRT_2_64`, `SQRT_2_128`: sqrt(2)
- `SQRT_3_32`, `SQRT_3_64`, `SQRT_3_128`: sqrt(3)
- `SQRT_1_2_32`, `SQRT_1_2_64`, `SQRT_1_2_128`: sqrt(1/2)

### Special Constants

- `EULER_GAMMA32`, `EULER_GAMMA64`, `EULER_GAMMA128`: Euler–Mascheroni constant
- `PHI32`, `PHI64`, `PHI128`: Golden ratio
- `CATALAN32`, `CATALAN64`, `CATALAN128`: Catalan's constant

### Conversion Constants

- `DEG_TO_RAD32`, `DEG_TO_RAD64`, `DEG_TO_RAD128`: Degrees to radians multiplier
- `RAD_TO_DEG32`, `RAD_TO_DEG64`, `RAD_TO_DEG128`: Radians to degrees multiplier

## Example

```firescript
import @firescript/std.math.sqrt;
import @firescript/std.math.sin;
import @firescript/std.math.PI64;
import @firescript/std.io.println;

float64 distance = sqrt(3.0 * 3.0 + 4.0 * 4.0);  // 5.0
println(distance);

float64 angle_sin = sin(PI64 / 6.0);             // 0.5
println(angle_sin);
```
