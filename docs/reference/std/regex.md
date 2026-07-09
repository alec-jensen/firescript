# std.regex

`@firescript/std.regex` provides a small, pure firescript regular-expression helper module.

This page covers the current API and syntax that the module supports today, and leaves room for future sections on captures, search helpers, replacements, and richer pattern syntax.

## Quick Start

```firescript
import @firescript/std.io.println;
import @firescript/std.regex.is_match;
import @firescript/std.regex.find_at;
import @firescript/std.regex.last_error;

println(is_match("(ab)+c", "ababc"));
println(is_match("[a-z]+", "firescript"));
println(is_match("^fire", "firescript"));
println(find_at("script", "firescript", 4));
println(last_error("[ab"));
```

## API

### `bool is_match(string pattern, string text)`

Returns `true` when the pattern matches the input text. Without anchors, the pattern must match the entire input; `^` and `$` control anchoring explicitly.

### `bool match(string pattern, string text)`

Alias of `is_match`.

### `int32 find_at(string pattern, string text, int32 start_pos)`

Position-aware matching: returns the length of the match starting at `start_pos`, or `-1` if there is no match at that position.

### `string last_error(string pattern)`

Validates a pattern and returns an empty string when the pattern is usable. If validation fails, it returns a short error message.

### `RegexPattern`

The `RegexPattern` class (`@firescript/std.regex.pattern.RegexPattern`) lets you construct a pattern once and match it repeatedly:

```firescript
import @firescript/std.regex.pattern.RegexPattern;
import @firescript/std.io.println;

RegexPattern p = RegexPattern("[a-z]+");
println(p.is_match("firescript"));
println(p.find_at("firescript", 4));
```

Methods:

- `bool is_match(&this, string &text)` — match against the text
- `bool matches(&this, string &text)` — alias of `is_match`
- `int32 find_at(&this, string &text, int32 start_pos)` — position-aware matching
- `string last_error(&this)` — pattern validation error, or empty string

## Supported Syntax

The current matcher supports:

- Literals like `abc`
- Escapes like `\n`, `\t`, `\r`, and escaped metacharacters
- Wildcard `.`
- Anchors `^` (start) and `$` (end)
- Grouping with `( ... )`
- Alternation with `|`
- Quantifiers `*`, `+`, and `?`
- Character classes like `[abc]`, `[^abc]`, and simple ranges like `[a-z]`

## Notes

- Pattern errors are reported at runtime via `last_error`; there is no compile-time pattern validation yet.
- Counted quantifiers (`{n,m}`), lookarounds, non-greedy quantifiers, captures, and backreferences are not supported yet.
- Character-class range ordering is intentionally simple and currently best suited to ASCII alphanumeric ranges.

## Future Sections [PLANNED]

These are good follow-up topics for later expansion:

- Capturing groups and submatch extraction
- Search helpers like `find_first` and `find_all`
- Replacement helpers
- More complete character classes and escaping rules
