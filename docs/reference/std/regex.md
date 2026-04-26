# std.regex

`@firescript/std.regex` provides a small, pure firescript regular-expression helper module.

This page is intentionally basic for now. It covers the current API and syntax that the module supports today, and it leaves room for future sections on captures, search helpers, replacements, and richer pattern syntax.

## Quick Start

```firescript
import @firescript/std.io.println;
import @firescript/std.regex.is_match;
import @firescript/std.regex.last_error;

println(is_match("(ab)+c", "ababc"));
println(is_match("[a-z]+", "firescript"));
println(last_error("[ab"));
```

## API

### `bool is_match(string pattern, string text)`

Returns `true` when the pattern matches the entire input text.

### `bool match(string pattern, string text)`

Alias of `is_match`.

### `string last_error(string pattern)`

Validates a pattern and returns an empty string when the pattern is usable. If validation fails, it returns a short error message.

## Supported Syntax

The current matcher supports:

- Literals like `abc`
- Escapes like `\n`, `\t`, `\r`, and escaped metacharacters
- Wildcard `.`
- Grouping with `( ... )`
- Alternation with `|`
- Quantifiers `*`, `+`, and `?`
- Character classes like `[abc]`, `[^abc]`, and simple ranges like `[a-z]`

## Notes

- Matching is full-string only.
- Counted quantifiers, lookarounds, non-greedy quantifiers, captures, and backreferences are not part of this first version.
- Character-class range ordering is intentionally simple and currently best suited to ASCII alphanumeric ranges.

## Future Sections

These are good follow-up topics for later expansion:

- Capturing groups and submatch extraction
- Search helpers like `find_first` and `find_all`
- Replacement helpers
- More complete character classes and escaping rules
- Anchors like `^` and `$`
