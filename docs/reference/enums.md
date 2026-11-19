# Enums

An `enum` declares a type whose value is exactly one of a fixed set of named variants. A variant can carry named payload fields. Enums are consumed with [`match`](match.md).

## Declaring an Enum [IMPLEMENTED]

```firescript
enum Color {
    Red,
    Green,
    Blue
}
```

Variants are separated by commas. A trailing comma and comments between or after variants are allowed. An enum can be exported from a module with `export enum Name { ... }`.

## Variants with Payloads [IMPLEMENTED]

A variant may carry named fields. Each field is written `name: Type`, like a class field:

```firescript
enum Shape {
    Circle(radius: float64),
    Rectangle(width: float64, height: float64),
    Point
}
```

A single enum can mix tag-only variants (`Point`) and payload variants. Payload fields may be any type, including owned types such as `string`, classes, and other enums.

## Constructing Values [IMPLEMENTED]

Variants are constructed with `EnumName.Variant` (tag-only) or `EnumName.Variant(args...)` (with a payload). Arguments are positional, in declaration order, and must match the variant's field count and types.

```firescript
import @firescript/std.io.println;

enum Message {
    Quit,
    Move(x: int32, y: int32),
    Say(text: string)
}

a: Message = Message.Quit;
b: Message = Message.Move(1, 2);
c: Message = Message.Say("hi");
a = Message.Say("again");
```

Passing the wrong number of arguments (`Shape.Circle(3.0, 4.0)`, `Shape.Point(1)`) is a compile error (`FS-PARSE-0012`).

## Ownership [IMPLEMENTED]

Enums are owned types, like classes that are not marked `copyable`. Passing an enum value to a function or into another variant's payload moves it, and the value is dropped when its owner goes out of scope. Only the active variant's owned fields are dropped. Reassigning a variable drops its previous value first, even when the old and new variants have different payload shapes. Enums can be used as class fields.

## Reading Payloads

The only way to read a payload is a [`match`](match.md) arm, which binds the fields as read-only borrows.

## Generic Enums [PLANNED]

`enum Option<T> { ... }` is not supported yet. Declaring one is a compile error (`FS-PARSE-0012`). Use the standard library's `Option<T>` and `Result<T, E>` classes (see [Types](std/types.md)) instead.

## Related

- [Match](match.md)
- [Type System](type_system.md)
- [Memory Management](memory_management.md)
