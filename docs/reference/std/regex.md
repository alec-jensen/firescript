# std.regex

`@firescript/std.regex` provides a pure firescript regular-expression module: matching, position-aware matching, capture groups, search helpers, and replacement.

> Status: everything below marked `[IMPLEMENTED]` is complete and covered by tests under `tests/sources/std/regex/`. Items marked `[PLANNED]` do not work yet.

## Quick Start

```firescript
import @firescript/std.io.println;
import @firescript/std.regex.is_match;
import @firescript/std.regex.find_at;
import @firescript/std.regex.find_first;
import @firescript/std.regex.replace;
import @firescript/std.regex.last_error;
import @firescript/std.regex.pattern.Match;

println(is_match("(ab)+c", "ababc"));            // true
println(is_match("\\d{3}-\\d{4}", "555-1234"));  // true
println(find_at("script", "firescript", 4));     // 6
println(last_error("[ab"));                      // unmatched '[' in pattern

m: Match = find_first("(\\w+)@(\\w+)", "mail me@host now", 0);
println(m.group(1));                             // me
println(m.group(2));                             // host
println(replace("(\\w+)@(\\w+)", "me@host", "$2:$1"));  // host:me
```

## API

### `fn is_match(pattern: string, text: string) -> bool` [IMPLEMENTED]

Returns `true` when the pattern matches the input text. Without anchors, the pattern must match the entire input; `^` and `$` control anchoring explicitly. Matching backtracks fully, so any way of matching the whole text is found. An invalid pattern never matches.

### `fn find_match(pattern: string, text: string) -> bool` [IMPLEMENTED]

Alias of `is_match`. Named `match` prior to 0.6.0; renamed because `match` is now a reserved keyword.

### `fn find_at(pattern: string, text: string, start_pos: int32) -> int32` [IMPLEMENTED]

Position-aware matching: returns the length of the match starting exactly at `start_pos`, or `-1` if there is no match at that position (or `start_pos` is out of range, or the pattern is invalid). With a leading `^` the match can only start at position 0; with a trailing `$` it must end at the end of the text.

### `fn last_error(pattern: string) -> string` [IMPLEMENTED]

Validates a pattern and returns an empty string when the pattern is usable. If validation fails, it returns a short error message (see [Errors](#errors)).

### `fn find_first(pattern: string, text: string, start_pos: int32) -> Match` [IMPLEMENTED]

Finds the leftmost match starting at or after `start_pos` (a negative `start_pos` is treated as 0). The result is always a `Match`; check `found()` to see whether anything matched. An invalid pattern never matches.

### `fn find_all(pattern: string, text: string) -> ArrayList<Match>` [IMPLEMENTED]

Returns every non-overlapping match, left to right. An empty match advances the scan by one character, so the scan always terminates (`find_all("x*", "abc")` yields four empty matches, at 0, 1, 2 and 3). An invalid pattern yields an empty list.

`ArrayList<Match>` holds an Owned element type, so read it with `removeLast()` rather than `get()` (see [Collections](collections.md)). `removeLast()` returns the *last* match first:

```firescript
all: ArrayList<Match> = find_all("\\d+", "a1b22c333");
while (all.size() > 0) {
    m: Match = all.removeLast();
    println(m.group(0));   // 333, then 22, then 1
}
```

### `fn replace(pattern: string, text: string, replacement: string) -> string` [IMPLEMENTED]

Replaces every non-overlapping match with `replacement` and returns the result. In the replacement:

- `$0` .. `$9` insert that capture group (`$0` is the whole match). A group number past the last group, or a group that did not take part in the match, inserts nothing.
- `$$` is a literal `$`.
- Any other `$` is a literal `$`.

Empty matches are replaced too (`replace("x*", "abc", "-")` is `-a-b-c-`). An invalid pattern returns the text unchanged.

### `Match` [IMPLEMENTED]

`@firescript/std.regex.pattern.Match`, returned by `find_first` and held in the list from `find_all`. Group 0 is the whole match; groups are numbered by their opening `(`, left to right.

- `fn found(&this) -> bool` — `false` when nothing matched. On a no-match `Match`, `start()`/`end()`/`group_start()`/`group_end()` return `-1`, `group_count()` returns `0` and `group(i)` returns `""`.
- `fn start(&this) -> int32` / `fn end(&this) -> int32` — offsets of the match in the searched text (`end` is exclusive).
- `fn group(&this, i: int32) -> string` — the text matched by group `i`. Returns `""` for a group that did not take part in the match (for example the unused side of an alternation, or a group quantified to zero repetitions), and for an out-of-range `i`. Use `group_start(i) >= 0` to tell "did not participate" apart from "matched the empty string".
- `fn group_start(&this, i: int32) -> int32` / `fn group_end(&this, i: int32) -> int32` — offsets of group `i` in the searched text, or `-1` if the group did not take part or `i` is out of range.
- `fn group_count(&this) -> int32` — number of capture groups in the pattern, not counting group 0.

A group inside a repeated group (`(ab)+`, `(a|b){2,3}`) reports its **last** repetition.

### `RegexPattern` [IMPLEMENTED]

The `RegexPattern` class (`@firescript/std.regex.pattern.RegexPattern`) compiles a pattern once and lets you search repeatedly:

```firescript
import @firescript/std.regex.pattern.RegexPattern;
import @firescript/std.regex.pattern.Match;
import @firescript/std.io.println;

p: RegexPattern = RegexPattern("[a-z]+");
println(p.is_match("firescript"));
println(p.find_at("firescript", 4));
m: Match = p.find_first("123 abc", 0);
println(m.group(0));   // abc
```

Methods:

- `fn is_match(&this, &text: string) -> bool`
- `fn matches(&this, &text: string) -> bool` — alias of `is_match`
- `fn find_at(&this, &text: string, start_pos: int32) -> int32`
- `fn find_first(&this, &text: string, start_pos: int32) -> Match`
- `fn find_all(&this, &text: string) -> ArrayList<Match>`
- `fn replace(&this, &text: string, &replacement: string) -> string`
- `fn group_count(&this) -> int32` — number of capture groups (`0` for an invalid pattern)
- `fn last_error(&this) -> string` — pattern validation error, or empty string

The free functions each build a `RegexPattern` per call; construct one yourself to reuse it.

## Supported Syntax

All of the following is [IMPLEMENTED]:

- Literals like `abc`
- Escapes `\n`, `\t`, `\r`, and escaped metacharacters (`\.`, `\(`, `\\`, `\{`, ...). An escape of any other character stands for that character.
- Wildcard `.` (any single byte, including newline)
- Anchors: a leading `^` (start of text) and a trailing `$` (end of text). A trailing `\$` is a literal dollar. A `^` or `$` anywhere else is an ordinary literal character, and a pattern with nothing between its anchors (`^`, `$`, `^$`) is reported as empty.
- Capturing groups `( ... )` and non-capturing groups `(?: ... )`, which can be nested and quantified
- Alternation with `|`; the leftmost alternative that leads to an overall match wins, and an alternative may be empty (`a|`)
- Quantifiers `*`, `+`, `?` (greedy)
- Counted quantifiers `{n}`, `{n,}`, `{n,m}` on any atom or group (`n` and `m` up to 1000). `{n,m}` requires `n <= m`.
- Character classes `[abc]`, `[^abc]`, ranges `[a-z]` (over any byte values), and shorthand classes inside a class (`[\d_]`, `[^\s]`). A `-` just before the closing `]` (or first in the class) is a literal.
- Shorthand classes, inside or outside `[...]`:

| Escape | Matches |
|---|---|
| `\d` / `\D` | an ASCII digit / anything else |
| `\w` / `\W` | `[A-Za-z0-9_]` / anything else |
| `\s` / `\S` | space, `\t`, `\n`, `\v`, `\f`, `\r` / anything else |

Matching works on bytes, so non-ASCII text is matched byte by byte.

### Matching semantics

Matching is a backtracking search: leftmost, with greedy quantifiers that give characters back when the rest of the pattern needs them. Alternation tries alternatives left to right. A repetition of something that can match the empty string (`(a*)*`) stops as soon as an iteration consumes nothing, so it always terminates.

Because it is a backtracking matcher, a pattern with nested unbounded quantifiers can take exponential time on adversarial input, and a repeat whose body is a group uses native stack per iteration: a single greedy repeat over several thousand characters can overflow the 1 MiB stack. A counted quantifier is expanded into copies of its atom, so `(a{1000}){1000}` is rejected as `pattern too large`.

## Errors

Pattern errors are reported at runtime via `last_error`; there is no compile-time pattern validation yet. Searches with an invalid pattern never match. The messages are:

| Message | Cause |
|---|---|
| `pattern is empty` | empty pattern, or nothing between the anchors |
| `dangling escape at end of pattern` | a trailing `\` |
| `unmatched '[' in pattern` | a class with no closing `]` |
| `empty character class` | `[]` |
| `invalid range in character class` | a reversed range (`[z-a]`) or a shorthand as a range end (`[a-\d]`) |
| `unmatched '(' in pattern` / `unmatched ')' in pattern` | unbalanced parentheses |
| `unsupported group syntax` | `(?` followed by anything but `:` (lookarounds, named groups, flags) |
| `quantifier without target` | a `*`, `+`, `?` or `{` with nothing to repeat (`*a`, `(+)`, `a|*`) |
| `nested or non-greedy quantifiers are not supported` | `a**`, `a+?`, `a{2}{3}` |
| `unterminated '{' in pattern` | `{` with no closing `}` |
| `invalid counted quantifier` | malformed count (`a{}`, `a{,3}`, `a{x}`) |
| `counted quantifier minimum exceeds maximum` | `a{3,1}` |
| `counted quantifier too large` | a count above 1000 |
| `pattern too large` | the compiled pattern would exceed the size limit |

## Not Supported Yet

- Lookahead and lookbehind (`(?=...)`, `(?!...)`, `(?<=...)`) [PLANNED]
- Non-greedy quantifiers (`*?`, `+?`, `??`, `{n,m}?`) [PLANNED]
- Backreferences (`\1`) [PLANNED]
- Named groups (`(?<name>...)`) and inline flags (`(?i)`) [PLANNED]
- Word-boundary and other anchors inside a pattern (`\b`, `\A`, `\z`, `^`/`$` in the middle) [PLANNED]
- Unicode-aware classes and case-insensitive matching [PLANNED]
- Compile-time pattern validation [PLANNED]

## Future Sections [PLANNED]

- Linear-time matching (NFA/DFA simulation) for patterns that backtrack badly
- Named capture groups and iteration over matches
