# Match

`match` selects an arm based on which variant of an [enum](enums.md) a value holds, and binds that variant's payload fields. `match` is a reserved keyword.

```firescript
match <expr> {
    <pattern> -> <body>,
    ...
}
```

## Statement Form [IMPLEMENTED]

In statement position, each arm body is a `{ }` block. Arms need no separator.

```firescript
import @firescript/std.io.println;

enum Message {
    Quit,
    Move(x: int32, y: int32),
    Say(text: string)
}

fn handle(m: Message) -> void {
    match m {
        Message.Quit -> { println("quit"); }
        Message.Move(x, y) -> { println("move " + (x as string) + "," + (y as string)); }
        Message.Say(text) -> { println("say " + text); }
    }
}

handle(Message.Quit);
handle(Message.Move(1, 2));
handle(Message.Say("hi"));
```

Output:

```
quit
move 1,2
say hi
```

## Patterns [IMPLEMENTED]

- `EnumName.Variant` matches a tag-only variant, or a payload variant when no fields are needed.
- `EnumName.Variant(a, b)` binds payload fields by their **declared field name**, not by position. Fields may be left out (`Shape.Rectangle(width)`).
- `EnumName.Variant(field: local)` renames a binding: `Shape.Circle(radius: r) -> ...`.
- `_` is a wildcard that matches any remaining variant.

Bindings are read-only borrows scoped to their arm.

## Expression Form [IMPLEMENTED]

When every arm body is a plain expression, `match` produces a value and can be used in a `return` or a variable initializer. All arms must produce the same type.

```firescript
import @firescript/std.io.println;

enum Level { Low, High }

fn score(l: Level) -> int32 {
    return match l {
        Level.Low -> 1,
        Level.High -> 10
    };
}

x: int32 = match Level.Low { Level.Low -> 5, _ -> 6 };
println(score(Level.High) as string);
println(x as string);
```

Output:

```
10
5
```

## Exhaustiveness [IMPLEMENTED]

Every variant must be covered by an arm, or a trailing `_` arm must be present. A statement `match` with arms that all return counts as returning for the "missing return" check.

```firescript
fn name(l: Level) -> string {
    match l {
        Level.Low -> { return "low"; }
        _ -> { return "other"; }
    }
}
```

## Compile Errors

| Situation | Code |
|---|---|
| Non-exhaustive match (no arm for a variant and no `_`) | `FS-SEM-0001` |
| Duplicate arm for the same variant | `FS-SEM-0001` |
| Arms after a `_` arm | `FS-SEM-0001` |
| Pattern names a field the variant does not declare, or binds a field twice | `FS-SEM-0001` |
| Unknown variant, or a pattern from a different enum | `FS-SEM-0001` |
| Scrutinee is not an enum | `FS-SEM-0010` |
| Expression arms with different types | `FS-SEM-0010` |
| Malformed pattern (e.g. a literal as a binding) | `FS-PARSE-0010` |

## Related

- [Enums](enums.md)
- [Control Flow](control_flow.md)
