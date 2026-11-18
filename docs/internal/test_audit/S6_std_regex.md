<!-- Audit shard report, 2026-11-18. Raw audit output; see README.md for the consolidated plan. Verdicts are recommendations, not applied changes. -->
# S6 audit: tests/sources/std/regex/ (42 files, no `//@ helper` files, no directives)

Method: read every file; ran all 42 against the real compiler+wine in private dirs (all pass; only normalisation noise: trailing spaces per line, leading blank lines in validate_anchors). Reproduced every pattern/text case with Python `re` (scripts: scratchpad/audit/o.py, gen.py, probe.fire, p2.fire). RESULT: no INCORRECT expectation found; every expectation equals Python's result (with documented deviations: `.` matches newline, mid-pattern ^/$ literal, `[]` is an error).
Python equivalences used: is_match = fullmatch; find_at = pattern.match(text,pos) length; find_all/replace empty-match handling = Python>=3.7 finditer/sub (identical: `a*` on "baac" -> 0:0 1:3 3:3 4:4; sub -> `-b--c-`); `$1` = `\1`.

## DELETE-candidate
std_regex_anchor_simple.fire | REDUNDANT, TRIVIAL | `^abc`/`abc$`/`^abc$`/`abc` true cases are all in std_regex_anchors.fire; `abc` in basic; invalid `[ab` never matches in error_unterminated_class (`[abc`) + error_unbalanced_parens (is_match("(ab")).
std_regex_validate_anchors.fire | REDUNDANT, WEAK | strict subset of validate_anchors2.fire (same 4 last_error calls) plus last_error("^") already in error_misc; comments are stale ("Should be '' or error").
std_regex_find_at.fire | REDUNDANT | every case covered by std_regex_anchors.fire (abc/abc/0, abc/xabc/1, abc/xabc/0, too-short) and find_at_anchors.fire (`ab`/`cab`/1); only `ab` on `abc` (prefix match, also covered by `if|else|while` cases) and mid-text miss `a`/`xaxbx`/2 are not literally repeated -> fold into the merged find_at file below.

## MERGE-candidate
- find_at family -> one `std_regex_find_at.fire`: find_at.fire + find_at_anchors.fire + the three find_at blocks of anchors.fire (incl. lexer-style `if|else|while`) + counted_with_anchors.fire's find_at lines (`^a{2,3}` pos 1 duplicates `^abc` pos 1 behaviour, but counted-with-anchors may stay as its own file as the feature-interaction test). Keep regression_escaped_dollar separate (regression).
- std_regex_validate_anchors2.fire -> merge into std_regex_error_misc.fire (add `^abc`, `abc$`, `^abc$`, `abc` -> "" lines, drop the "Error N:" header noise).
- std_regex_counted_exact.fire + counted_open.fire + counted_range.fire -> one `counted_quantifiers` file (same mechanism: is_match true/false table of {n},{n,},{n,m}; `a{3,3}` in range == `a{3}` in exact; `a{2,}`/`a{0,}` etc). counted_group.fire (groups/nesting) and counted_with_anchors.fire keep as separate. Distinct behaviours lost: none.
- Invalid-pattern-never-matches: std_regex_find_first_invalid_pattern.fire + std_regex_replace_invalid_pattern.fire (+ the `bad.*` tail of regexpattern_search.fire, + is_match tails in error_unbalanced_parens / error_unterminated_class / error_bad_counted) are the same check per API. Merge find_first+replace invalid files into one `invalid_pattern` file and add the missing find_at / find_all / is_match invalid cases there (find_at invalid and find_all free-function invalid are currently untested; docs claim -1 / empty list).
- anchors.fire's is_match anchor block overlaps find_first_anchors / find_all_anchors / replace_basic anchor lines only loosely (different APIs) -> keep as the is_match anchor test, after extracting the find_at lines.

## FIX-EXPECTATION
(none: no INCORRECT expectations.)
Cosmetic: std_regex_shorthand_classes.fire comment "An unknown escape is still the literal character" is attached to `\.`, which is a metacharacter escape, not an unknown escape (no unknown-escape case such as `\q` or `\-`). std_regex_validate_anchors.fire comments are wrong. find_all_* files copy-paste the same show()/spans() helpers (4 copies) - not a correctness problem.

## KEEP (with notes)
std_regex_anchors.fire | KEEP (after find_at lines are moved out) | only test of is_match with `^`/`$` on non-matching text; lexer-style alternation find_at unique.
std_regex_basic.fire | KEEP, mild TRIVIAL parts | core is_match table (alt, *, +, ?, group, class); last_error x3 duplicates error_* files (`[ab`, `(ab`, `a\`).
std_regex_captures_alternation.fire | KEEP | non-participating groups, no stale-capture leak; matches Python (`(?:(a)x|(a)y)` on "ay" -> (None,'a')).
std_regex_captures_basic.fire | KEEP | group offsets; matches Python spans.
std_regex_captures_greedy_backtrack.fire | KEEP | equals Python groups for all 5 cases.
std_regex_captures_nested.fire | KEEP | numbering by open paren + out-of-range; equals Python.
std_regex_captures_noncapturing.fire | KEEP | note second case (`(?:a|b)(?:c|d)`) mostly overlaps counted_group `(?:ab|c){2}d` for syntax but asserts group_count==0, fine.
std_regex_captures_quantified_group.fire | KEEP | last-iteration capture; equals Python for `(ab)+`, `(\w)*`, `(a|b){2,3}`; zero-rep group -1. See bug note re `(a*)+`.
std_regex_counted_group.fire | KEEP | all 15 equal Python fullmatch.
std_regex_counted_with_anchors.fire | KEEP | equals Python match(text,pos).
std_regex_error_bad_counted.fire | KEEP | note `a{2,2}`/`a{0}` blank lines are valid-pattern assertions (harness trims trailing blanks; middle blanks are positional so OK). `a\{2\}` and `}` literals are extra but fine.
std_regex_error_dangling_quantifier.fire | KEEP | last `a*` valid -> empty line trimmed (WEAK-ish only in that the trailing empty is implicit; any regression yields a non-empty extra line so still detected).
std_regex_error_misc.fire | KEEP | 5 expected lines for 8 prints (trailing 3 blank = `a|`,`|a`,`()` valid); `^`/`$` empty dup with validate_anchors.
std_regex_error_unbalanced_parens.fire | KEEP | `(a)` valid and `(?=a)` unsupported are useful.
std_regex_error_unterminated_class.fire | KEEP | name misleading (`[]`, `[z-a]` are not unterminated) but cases distinct.
std_regex_find_all_anchors.fire | KEEP | unique. Python: findall('^a','aaa')==['a'], 'a$' on 'aaa' -> (2,3), '^a*$' -> (0,3): all equal.
std_regex_find_all_basic.fire | KEEP, small TRIVIAL | `show(find_all("x","abc"))` (blank line) and `.size()` 0 on the next line assert the same thing; `find_all("\\d","1 2 3").size()` near-duplicate of `\d+` case.
std_regex_find_all_empty_matches.fire | KEEP | equals Python>=3.7 spans.
std_regex_find_all_groups.fire | KEEP | equals Python findall tuples (`(a)(b)?` -> ('a','') shown as `a=`).
std_regex_find_first_anchors.fire | KEEP
std_regex_find_first_basic.fire | KEEP | no-match accessor degradation is documented behavior, not Python-comparable.
std_regex_find_first_empty.fire | KEEP | `x*$` on "ab" -> (2,2) equals Python.
std_regex_regexpattern_search.fire | KEEP, WEAK | only test of the RegexPattern class; does not exercise `matches()` (alias) nor `find_match` free function (nothing in tests/ does).
std_regex_regression_deep_text.fire | KEEP | narrow regression (stack depth, 500 reps).
std_regex_regression_escaped_dollar.fire | KEEP | equals Python (`a\$` on "a$ and more" -> 2; `a\\$` on "a\x" -> -1).
std_regex_regression_full_backtracking.fire | KEEP | all equal Python; `(a|ab)(c|bcd)` also in captures_greedy_backtrack (that one asserts groups; this asserts is_match) - acceptable.
std_regex_regression_generic_matcher.fire | KEEP | deliberately near-miss patterns; overlaps basic only superficially.
std_regex_replace_basic.fire | KEEP | equals Python re.sub (incl. `^a`->baa, `a$`->aab, `aa`/`aaaaa`->bba).
std_regex_replace_empty_matches.fire | KEEP | equals Python>=3.7 sub.
std_regex_replace_groups.fire | KEEP | `$n` semantics (Python `\n`); `$$`, `$x` etc. are firescript-specific (no oracle).
std_regex_shorthand_classes.fire | KEEP, WEAK | `\s` only exercised with space, \t, \n (doc also lists \r \v \f); no `\D`/`\W` on newline; no `\n \t \r` pattern escapes anywhere.
std_regex_shorthand_in_class.fire | KEEP | all equal Python (`[\D\s]+`, `[\w-]+`, ...).

## Detailed evidence: WEAK findings (no INCORRECT)
1. Missing is_match semantics pin: documented "without anchors the pattern must match the entire input; ^ and $ control anchoring". No test asserts `is_match("^abc","abcd")` (engine: false = Python fullmatch) or `is_match("abc$","xabc")` (engine: false). Only `abc$` vs `abcx` and `^abc` vs `xabc` are tested, which would also pass under "search" semantics for... (they'd fail under search too, so the gap is the prefix/suffix-with-extra-text direction). Suggested: add both lines to std_regex_anchors.fire (expect false, false).
2. Escapes `\n`, `\t`, `\r` in the pattern (doc "Supported Syntax") are never tested (grep over tests/ finds none). Probe: is_match("a\\tb","a\tb"), `\n`, `\r` all true. Suggest a 3-line test.
3. Mid-pattern `^`/`$` as literals (documented) untested. Probe: is_match("a^b","a^b") true, is_match("a$b","a$b") true. Python would treat them as anchors (never matches) - intentional deviation, should be pinned.
4. `.` matching newline (documented, differs from Python) untested. Probe is_match("a.c","a\nc") true.
5. find_at out-of-range / negative / invalid pattern (documented -1) untested: probe find_at("a","a",-1) = -1, find_at("a","a",5) = -1, find_at("(a","a",0) = -1, find_at("a*","a",1) = 0 (empty match at end).
6. `matches()` and `find_match()` aliases untested. Probe: find_match("a+","aaa") true.
7. `$10` in replacement (documented: only `$0..$9`): probe replace("(a)","a","$10") -> "a0". Untested.
8. `\s` with \r \v \f: `\v`/`\f` cannot be written as firescript string escapes (probe: "a\vb" does not match `a\sb`, so the literal is not a VT), so only `\r` is testable by literal; `\r` probe is true. Not verified for \v \f.
9. find_all free-function with invalid pattern (doc: empty list) only covered through RegexPattern.find_all in regexpattern_search.

## Compiler/engine differences vs Python re (all low severity; none are test failures)
- Capture of an empty final iteration: `(a*)+` on "aab": Python group1 = '' (last iteration empty), engine group1 = "aa" (0:2). Same for `(a*)*b` on "aab" (Python '', engine "aa"). `(a*)*` on "b": Python group1 = '' at (0,0), engine reports group 1 as non-participating (-1). Matches docs ("stops as soon as an iteration consumes nothing") so arguably design, but Python/PCRE differ. Repro: find_first("(a*)+","aab",0).group(1). Not pinned by any test (captures_quantified_group does not cover empty last iteration).
- `(a?){3}a` on "aa": engine group1 = 1:"" ; Python group1 = '' too (consistent).
- All other ~45 extra probes (alternation, nested/optional groups, `[a-]`, `[-a]`, `[a-c-e]`, `[\]]`, `[\\]`, `(\d+)(?:\.(\d+))?`, `(a|b)*`, `((a)|b)+` stale-group semantics) matched Python.
Documented-intentional deviations (not bugs): `.` matches `\n`; `[]` errors; `^`/`$` mid-pattern literal; `(?...)`, non-greedy, backrefs unsupported.
