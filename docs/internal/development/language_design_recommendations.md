# Firescript Language Design Recommendations

This document provides detailed recommendations for language improvements that should be made **early in development**, ideally before or alongside FIR implementation, to establish strong foundations.

## Executive Summary

The following changes are recommended to improve language clarity, safety, and long-term maintainability:

1. **Explicit Value Categories** - Make `owned`/`copyable` explicit in declarations
2. **Explicit Ownership Operations** - Add `move()` and `borrow()` at call sites
3. **Ownership-Aware Generics** - Constraints that distinguish Owned vs Copyable
4. **Improved Error Messages** - Leverage FIR for better diagnostics
5. **Array Dynamism in Stdlib** - Move dynamic arrays to standard library
6. **Null Safety Clarification** - Explicit Option types or nullable syntax
7. **Trait System** (Phase 2) - For zero-cost abstraction and polymorphism

---

## Recommendation 1: Explicit Value Categories

### Current State

Value categories (owned/copyable) are inferred entirely during semantic analysis. Users don't see or declare them explicitly.

```firescript
class Point {
    int32 x;
    int32 y;
}  // Implicitly Owned - nothing indicates this

copyable class Vec2 {
    float32 x;
    float32 y;
}  // Only copyable is explicit
```

### Proposed Change

Make value category explicit and consistent in all declarations:

```firescript
// Option A: Explicit 'owned' keyword (recommended)
owned class Point {
    int32 x;
    int32 y;
}

copyable class Vec2 {
    float32 x;
    float32 y;
}

// Option B: Default owned, explicit for copyable (current)
class Point { ... }           // defaults to owned
copyable class Vec2 { ... }   // explicit copyable
```

**Option B (current) is acceptable if we document that "class" defaults to owned.**

### Benefits

| Aspect | Benefit |
|---|---|
| **Clarity** | Language users immediately see whether a class is copyable |
| **Teachability** | Explicit is easier to learn than "class defaults to owned" |
| **Safety** | Reduces chance of accidentally using Owned semantics when Copyable intended |
| **FIR Generation** | Parser already has value category; simpler to preserve through pipeline |
| **Type Diagnostics** | Tools can show value category in hover tooltips |

### Implementation Notes

- **Parser Change**: Minimal - already supports `copyable` keyword
- **Documentation**: Update getting started guide and memory management docs
- **Migration**: No breaking change if `owned` keyword is optional (default)
- **Testing**: Existing tests work unchanged

### Example: Before and After

**Before** (implicit):
```firescript
class File {
    string path;
    int32 handle;
}
// Is this owned or copyable? User must read docs or infer from usage
```

**After** (explicit):
```firescript
owned class File {
    string path;
    int32 handle;
}
// Clear that File is Owned (heap-allocated, unique ownership)
```

---

## Recommendation 2: Explicit Ownership Operations at Call Sites

### Current State

Ownership transfer (move vs. borrow) is implicit, determined by function signature:

```firescript
void addUser(string username);  // signature says 'move'

string u = "alice";
addUser(u);  // u moved implicitly; not obvious from call site
```

### Proposed Change

Make ownership operations explicit at call sites using `move()` and `borrow()`:

```firescript
void addUser(string username);        // Takes ownership
int32 length(&string s);              // Borrows

string u = "alice";
addUser(move(u));                     // Explicit move - clear intent
int32 len = length(borrow(u));        // Explicit borrow
println(u);                           // OK - u still valid after borrow

// For copyable types, move/borrow not needed (implicit copy):
int32 x = 42;
int32 y = x;                          // Copy - no annotation needed
```

### Benefits

| Aspect | Benefit |
|---|---|
| **Explicitness** | Follows firescript principle: explicit is better |
| **Readability** | Ownership intent obvious from call site, not just signature |
| **Safety** | Accidental moves easier to spot in code review |
| **Education** | New users see ownership operations explicitly |
| **Debugging** | Stack traces show which function moved value |
| **Linting** | Can warn on unexpected moves/borrows |

### Implementation Notes

- **Parser Change**: Add `move(expr)` and `borrow(expr)` as expression forms
- **Semantic Analysis**: Validate that `move(expr)` and `borrow(expr)` match parameter expectations
- **Code Generation**: Remove move/borrow markers from C output (already handled)
- **Migration**: Could support both implicit and explicit initially; deprecate implicit over time

### Example Transformation

**Before**:
```firescript
class Database {
    string connectionString;
}

void initDB(Database db) {  // Takes ownership
    // ...
}

Database d = Database("localhost");
initDB(d);  // Implicit move - not obvious
// d is now invalid but not marked at call site
```

**After**:
```firescript
void initDB(Database db) {  // Takes ownership

}

Database d = Database("localhost");
initDB(move(d));  // Explicit move - clear at call site
// Reader immediately sees d is moved here
```

### Discussion

This recommendation has implications:
- **Verbosity**: Adds `move()` and `borrow()` calls throughout code
- **Learning Curve**: Users must learn move() and borrow() notation
- **Consistency**: Applies to all ownership transfers, which is thorough

**Recommendation**: Implement as opt-in initially (warn if missing), then make required in future version.

---

## Recommendation 3: Ownership-Aware Generics

### Current State

Generic type parameters don't distinguish between Owned and Copyable:

```firescript
func<T> clone(T value) -> T {
    return value.clone();  // ERROR if T is Copyable (no .clone() method)
}
```

Generic constraints are basic:

```firescript
func<T: int32 | float64 | float128> absolute(T value) -> T {
    // Only numeric types
}
```

### Proposed Change

Add built-in constraint types that distinguish value categories:

```firescript
// Constraint: Only Copyable types
func<T: Copyable> process(T value) -> T {
    return value;  // Simple copy, no ownership involved
}

// Constraint: Only Owned types
func<T: Owned> clone(T value) -> T {
    return value.clone();
}

// Constraint: Numeric types (already exists)
func<T: int32 | float64> absolute(T value) -> T {
    // ...
}

// Multiple constraints (intersection):
func<T: Owned + HasLength> getLen(T value) -> int32 {
    return value.len();
}
```

### Benefits

| Aspect | Benefit |
|---|---|
| **Clarity** | Generic constraints explicitly state whether Owned or Copyable |
| **Correctness** | Compiler prevents incorrect generic usage |
| **Performance** | Allows different code paths for Owned vs Copyable |
| **Library Design** | Enables building sophisticated generic abstractions |
| **Documentation** | Constraints document assumptions about types |

### Implementation Notes

- **Semantic Analysis**: Extend constraint evaluation to recognize `Copyable`, `Owned` as built-in constraints
- **Code Generation**: Already handles monomorphization; no changes needed
- **Migration**: Backward compatible; existing generics continue to work
- **Documentation**: Add section on generic constraints

### Example: Generic Clone Function

**Before** (doesn't work well):
```firescript
func<T> clone(T value) -> T {
    // What if T is int32? Copyable types don't have .clone()
    return value.clone();  // Compiler error for Copyable T
}

// Workaround: separate functions
int32 cloneInt(int32 value) { return value; }
string cloneString(string value) { return value.clone(); }
```

**After** (clear intent):
```firescript
func<T: Owned> clone(T value) -> T {
    return value.clone();  // Only called with Owned types
}

// For copyables, users just use assignment:
int32 x = 42;
int32 y = x;  // Copy (no function call needed)
```

---

## Recommendation 4: Improved Error Messages via FIR

### Current State

Semantic analyzer produces good error messages, but they're tied to AST locations:

```
ownership_test.fire:7:5: error: use after move
    println(p1.x)
    ^
note: ownership of 'p1' was moved here (5:0)
    Point p2 = p1;
    ^
```

### Proposed Enhancement

With FIR in place, errors can be richer:

```
ownership_test.fire:7:5: error: use after move
    println(p1.x)
    ^
note: 'p1: Point(owned)' ownership transferred here (5:0)
    Point p2 = p1;
    ^^^^^^
hint: To borrow 'p1' instead, use: getX(borrow(p1))
hint: To clone 'p1', use: Point p2 = p1.clone();
```

### Benefits

- **Context-Aware**: Suggestions based on FIR information
- **Learning-Friendly**: Hints teach best practices
- **Efficiency**: Users fix errors faster
- **Tooling**: LSP can provide rich hover information

### Implementation Notes

- **FIR Integration**: Error reporting can examine FIR ownership map
- **Hint System**: Develop heuristics for common error patterns
- **Testing**: Add error message regression tests

---

## Recommendation 5: Dynamic Arrays in Standard Library

### Current State

Arrays are fixed-size and largely immutable in user code:

```firescript
int32[10] numbers;  // Fixed-size, must know size at compile time
// No .push(), .pop(), etc. available
```

### Proposed Change

Provide a standard library `Vec<T>` type:

```firescript
import @firescript/std.collections.Vec;

Vec<int32> numbers = Vec.new();
numbers.push(10);
numbers.push(20);
numbers.pop();

for (int32 n in numbers) {
    println(n);
}

int32 len = numbers.length();
```

### Benefits

| Aspect | Benefit |
|---|---|
| **Usability** | Natural dynamic array operations |
| **Simplicity** | Keeps core language simple (no dynamic syntax) |
| **Library Composition** | Users can build on Vec (stacks, queues, etc.) |
| **Performance** | Can optimize Vec implementation independently |
| **Consistency** | Aligns with how Option, Result are provided |

### Implementation Notes

- **Standard Library**: Implement `Vec<T>` in `std/collections.fire` (or C)
- **Generic Support**: Leverages existing generic mechanisms
- **Ownership**: Vec<T> is Owned type (moves on assignment)
- **Performance**: Can use optimized C arrays under the hood
- **Future**: Can add optimized specializations for `Vec<int32>`, `Vec<string>`, etc.

### Example: Collections Module

**std/collections.fire**:
```firescript
class Vec<T> {
    T[] data;
    int32 capacity;
    int32 len;
    
    static Vec<T> new() {
        return Vec<T>([], 0, 0);
    }
    
    void push(&mut this, T value) {
        // Grow if needed
        // ...
    }
    
    T? pop(&mut this) -> Option<T> {
        if this.len == 0 {
            return None();
        }
        // ...
    }
    
    int32 length(&this) {
        return this.len;
    }
    
    T[]& asSlice(&this) {
        return this.data;
    }
}
```

---

## Recommendation 6: Null Safety & Optional Values

### Current State

Null safety is mentioned but not fully enforced or standardized:

```firescript
// Current: How to represent "maybe a value"?
// Option: Use Option<T> from stdlib (works)
Option<int32> maybeNum = Some(42);

// But nullable syntax would be clearer:
int32? maybeNum = 42;
```

### Proposed Change (Phase 1)

**Clarify and document** use of `Option<T>` for optional values:

```firescript
import @firescript/std.types.Option, Some, None;

Option<string> maybeUser = Some("alice");
if (maybeUser is Some) {
    println(maybeUser.get());
}
```

### Proposed Change (Phase 2)

**Add nullable syntax** for convenience:

```firescript
// Syntax sugar for Option<T>
int32? maybeNum = 42;
string? name = None();

// Use with pattern matching or is-checks:
if (maybeNum is Some) {
    println(maybeNum!);  // unwrap operator
}
```

### Benefits

| Aspect | Benefit |
|---|---|
| **Clarity** | Null handling explicit in types |
| **Safety** | Compiler prevents unwrapping None values |
| **Familiarity** | Similar to Kotlin, Swift, TypeScript nullable syntax |
| **Composition** | Forces thinking about None case upfront |

### Implementation Notes

- **Phase 1**: Document Option<T> usage pattern
- **Phase 2**: Add syntax sugar for nullable (`T?`), unwrap operator (`!`), pattern matching
- **Future**: Could add Result<T, E> for error handling

---

## Recommendation 7: Trait System (Phase 2)

### Current State

Polymorphism limited; code reuse requires inheritance chains:

```firescript
class Shape { virtual void draw(); }
class Circle: Shape { void draw() { ... } }
class Rectangle: Shape { void draw() { ... } }

// But limited: only single inheritance, virtual methods
```

### Proposed Change (Phase 2 - post-FIR)

Add trait system for composition-based polymorphism:

```firescript
trait Drawable {
    void draw(&this);
}

trait Serializable {
    string serialize(&this);
}

class Circle: Drawable + Serializable {
    void draw(&this) { println("drawing circle"); }
    string serialize(&this) { return "circle"; }
}

class Rectangle: Drawable + Serializable {
    void draw(&this) { println("drawing rect"); }
    string serialize(&this) { return "rectangle"; }
}

void renderAll(&Drawable[] shapes) {
    for (&Drawable s in shapes) {
        s.draw();
    }
}
```

### Benefits

| Aspect | Benefit |
|---|---|
| **Composability** | Types can implement multiple traits |
| **Flexibility** | Traits can be added to types after creation |
| **Reuse** | Generic functions work on trait bounds |
| **Performance** | Monomorphization generates specialized code (no vtables) |
| **Idiomaticity** | Aligns with Rust, Go, TypeScript interfaces |

### Implementation Notes

- **Complexity**: Significant design work; defer to Phase 2
- **FIR Foundation**: FIR makes this feasible by decoupling from C backend
- **Monomorphization**: Leverage existing generic monomorphization mechanism
- **Dynamic Dispatch** (optional): Could support vtable-based dynamic dispatch if desired

---

## Recommendation 8: Pattern Matching (Phase 2)

### Current State

Limited ability to inspect and destructure values:

```firescript
// Current: Manual checks
if (result is Some) {
    int32 value = result.get();  // Awkward
    println(value);
}
```

### Proposed Change (Phase 2)

Add pattern matching for ergonomics:

```firescript
// Pattern matching
match (maybeValue) {
    Some(v) => println(v),
    None() => println("no value"),
}

// Destructuring
if (point is Point(x, y)) {
    println(x);
    println(y);
}
```

### Benefits

| Aspect | Benefit |
|---|---|
| **Readability** | Patterns more concise than manual checks |
| **Safety** | Forces handling all cases |
| **Ergonomics** | Natural expression of control flow |
| **Composition** | Works naturally with ADTs (algebraic data types) |

### Implementation Notes

- **Complexity**: Moderate; requires AST, semantic analysis, codegen changes
- **FIR Integration**: Pattern matching compiles to FIR branches naturally
- **Future Work**: Phase 2+

---

## Recommendation 9: Async/Await (Phase 3)

### Current State

Not supported; no asynchronous programming model.

### Proposed Direction (Phase 3+)

Add async/await for concurrent programming:

```firescript
async int32 fetchData(string url) {
    result = await httpGet(url);
    return result.length;
}

// Spawn task
task t = spawn fetchData("https://...");
await t;
```

### Implementation Notes

- **Complexity**: Very significant; coordinate with FIR
- **Backends**: Different strategies for C (threads) vs. JS/WASM (Promise)
- **Timeline**: Phase 3+ (after FIR and traits)

---

## Summary: Prioritization

| Recommendation | Priority | Effort | Impl. Phase | Impact |
|---|---|---|---|---|
| Explicit Value Categories | Medium | Low | 1 (Concurrent) | High (clarity) |
| Explicit Ownership Ops | High | Medium | 1 (Concurrent) | High (safety) |
| Ownership-Aware Generics | Medium | Medium | 1 (FIR) | Medium |
| Improved Errors | Medium | Low | 2 (FIR) | Medium |
| Dynamic Arrays | Low | Medium | 1 (Stdlib) | Low (convenience) |
| Null Safety Clarification | Low | Low | 1 (Docs) | Low |
| Trait System | Low | High | 2+ (After FIR) | High (future) |
| Pattern Matching | Low | High | 2+ (After FIR) | Medium |
| Async/Await | Very Low | Very High | 3+ (Long-term) | High (distant future) |

---

## Recommendation: Next Steps

1. **Immediate** (Concurrent with FIR):
   - Document that "class defaults to owned" explicitly
   - Consider adding `move()` and `borrow()` markers at call sites
   - Improve error messages with FIR context

2. **Phase 1** (After FIR MVP):
   - Implement Ownership-Aware Generics
   - Add Vec<T> to standard library
   - Clarify null safety with Option<T>

3. **Phase 2** (Post-FIR Stabilization):
   - Trait System
   - Pattern Matching
   - Enhanced error messages

4. **Phase 3+** (Long-term):
   - Async/Await
   - Advanced generic features
   - Macro system (if desired)

---

## Conclusion

These recommendations chart a course for firescript to mature into a powerful, ergonomic language while maintaining its core principles of safety, performance, and explicitness. With FIR providing a solid foundation, firescript can support increasingly sophisticated features without sacrificing simplicity or correctness.
