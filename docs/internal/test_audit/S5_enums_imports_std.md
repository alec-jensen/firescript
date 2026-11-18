<!-- Audit shard report, 2026-11-18. Raw audit output; see README.md for the consolidated plan. Verdicts are recommendations, not applied changes. -->
# S5 audit: enums, match, imports, integration, std (excl. regex)

Method: all 58 standalone tests (helpers excluded) compiled and run under wine from private temp dirs (private root with build/temp and copies of the integration .txt files). ALL 58 PASS against their EXPECT blocks (runner: scratchpad/audit/run_all.py). I re-derived expected output by hand / with python for: hackathon8_mission1 (576 = signed sum, confirmed), hackathon8_mission2 (17 = mode of unsigned magnitudes, 59 vs runner-up 54, robust), run_length_encoding (python itertools.groupby == EXPECT), fcl lexer offsets, math/ranges/split/fs/cli semantics against docs and std sources. No EXPECT block was found to bless a compiler bug. Findings are mostly redundancy, weak assertions and stale header comments.

## DELETE-candidate
tests/sources/imports/imports_single.fire | REDUNDANT | `import utils.helper` + call is covered by imports_alias.fire (`import utils.helper;`), imports_deep_path.fire, export_visibility.fire; only unique bit is the missing trailing semicolon, which imports_symbols/imports_multi/imports_wildcard also use.
tests/sources/imports/export_visibility.fire | REDUNDANT, WEAK, misnamed | Named for visibility but only imports one exported fn (same as imports_single/deep_path). `hiddenValue` is never touched. Real visibility negative test is tests/sources/invalid/imports/export_visibility_private.fire. Helper visibility_provider.fire carries a stray empty `/* EXPECT */` block.
tests/sources/std/types/option_static_factories.fire | REDUNDANT | option_unwrap_or.fire uses Option.Some, Option<string>.None(), Option.Some(0), Option<int32>.None(), CopyableOption.Some, CopyableOption<int32>.None() and checks the produced values (stronger). Only unique: CopyableOption<bool>.None().isNone().
tests/sources/std/types/result_static_factories.fire | REDUNDANT, WEAK | result_unwrap_or.fire exercises Result<string,string>.Ok/.Err and CopyableResult<int32,bool>.Ok/.Err with value checks. This file only checks isOk/isErr booleans (never the value). Unique: Result<int32,string>.Ok(10)/Err("bad") (scalar T).
tests/sources/imports/imports_symbol_alias.fire | REDUNDANT (soft; it is a regression test) | imports_alias.fire also does `import @firescript/std.io.println as p;` and calls `p(...)` -- the exact bug (alias call site -> "call to unknown function") would fail there too. Keep only if the owner wants a dedicated minimal regression.
tests/sources/std/types/option_issome_isnone.fire | REDUNDANT (soft; regression) | option_null_vs_zero.fire calls isSome()/isNone() on imported Option<int32> and CopyableOption<bool>, so the cross-module `_find_method_def` generic-lookup bug in its header would also fail there. Unique: isNone() on Option and isSome() on CopyableOption<int32>.

## MERGE-candidate
tests/sources/std/cli/std_cli_args_parser.fire | WEAK, REDUNDANT-in-part | First two lines (argc()>=1, argv_at(0)!="") duplicate std_cli_args_basic.fire. Rest only checks default fallbacks with no argv (has_flag false, option_value fallback, positional(-1)). Fold into basic (or into with_argv) as one "no args" section.
tests/sources/std/fs/std_fs_helpers.fire | MERGE with std_fs_basic.fire | Both do writeAll/appendAll/read/missing-read; helpers unique = exists()/err_code(), basic unique = readBytes + status -2. One file would cover both.
tests/sources/std/text/stringbuilder_basic.fire | MERGE with stringbuilder_reuse_after_build.fire | Overlap: append/length/build/drain. basic unique: multi-append total 13, seeded "Count: "+append. reuse unique: empty append, build-twice, reuse after drain.
tests/sources/enums/enum_leading_comma.fire + enum_body_formatting.fire | optional MERGE | Two tiny parser-tolerance tests (leading comma / comments+trailing comma); distinct behaviors, both fine as one-behavior files.

## FIX-EXPECTATION / FIX-COMMENT (no failing expectation found; these are stale/misleading comments or too-weak assertions)
tests/sources/enums/enum_payload_construct.fire | INCORRECT (header), WEAK | Header says payload fields are "limited to copyable scalar types ... owned payload data requires destructor support planned for a later stage (0.6.0)". False now: enum_owned_payload_drop.fire / enum_field_in_class_drop.fire have string/class payloads and feature table says implemented. Body prints two constant strings; payload values are never read back, and the "reassignment across variants must not corrupt storage" claim is never checked (a, b are not matched after reassigning). Fix: update header; after reassignment `match a`/`match b` and println the fields; keep Labeled(int32,bool) (unique mixed-type payload).
tests/sources/enums/enum_tag_only.fire | WEAK | Prints two constant strings; never matches a/b/c/d, so wrong tag/reassignment would go unnoticed. The header claim "previously-held owned enum value must be dropped" is not observable (tag-only enum owns nothing). Fix: match after reassign and print variant names. (`export enum` with no importer is also untested here.)
tests/sources/enums/enum_field_in_class_drop.fire | WEAK/comment | Header says it checks the enum destructor runs; TEST_MANIFEST says it is a move-into-payload regression (owned arg moved, not also dropped at scope exit). Real assertion = no crash and data survives to match. Align header with manifest.
tests/sources/std/types/result_copyable.fire | WEAK | Header claims a copy is "independent (value-semantics copy, not shared)" but nothing mutates either copy after copying, so independence is never tested. Fix: mutate `copy.value`, assert `original.value` unchanged.
tests/sources/std/collections/arraylist_add_remove_last.fire | comment misleading | Header says "and growth beyond the initial capacity" but only 3 adds (capacity 4). Growth is in arraylist_growth.fire. Edit header.
tests/sources/std/collections/arraylist_growth.fire | WEAK (mild) | Spot-checks indices 0,12,24 only; a grow-and-copy bug dropping elements at 3/4, 7/8, 15/16 would pass. Check a sum/all elements.
tests/sources/std/collections/hashmap_growth.fire | WEAK (mild) | Checks size and keys 0,25,49 only; `size()` is a tracked counter, so a rehash that loses a key (e.g. 10) is not detected. Check every key (sum of get(i)).
tests/sources/std/fcl/std_fcl_lexer.fire | WEAK | Only 6 of the token paths: identifier, assign, string, comma, colon, int32, bool, eof. Not covered: lbrace/rbrace/lbracket/rbracket, negative ints, "-" alone, unterminated string, unknown char (status -84 "invalid"), whitespace/newlines. The test's own `status<0 -> break` branch is never taken. I ran such inputs (see detail) and the lexer behaves sanely, so adding them is safe.
tests/sources/std/syscalls/syscall_basic.fire | WEAK | Only open(w)/write/close/open(r)/read round trip printing the data. Status values from write/close are never asserted; open failure, "a" mode, remove/rename/move syscalls and short reads untested directly (fs tests cover remove/rename/move via std.fs wrappers). If open fails it silently prints nothing.
tests/sources/std/cli/std_cli_args_edge_with_argv.fire | WEAK (mild) | `has_flag_alias("debug","d")` is satisfied by `--debug` alone, so the grouped `-de` path is not isolated (with_argv's `-vg` does isolate it). Also pins that `--output` followed by `--debug` is "no value" then later `--output=final.bin` wins -- not in docs/cli_args.md.
tests/sources/std/cli/* (all) | gap | Short-option value forms (`-o value`, `-o=value`, `-ovalue`) and non-alias `option_value("x")` with separate value are never tested (only `--path src` via alias and `--output=...`).
tests/sources/enums/enum_body_formatting.fire | undocumented behavior pinned | Uses expression-bodied arms (`Status.Ok -> println("ok"),`) in *statement* position. changelog says statement arms use `{ }` blocks and only value-producing match uses plain expressions. Works, but pins an unspecified form; add a note or move to a documented form.
tests/sources/std/math/math_abs_min_max_clamp.fire | correct; docs stale | Test nests generic calls (`println(abs(-7, 0))`), which docs/reference/std/math.md says "currently fails to compile -- a known limitation". It compiles and passes, so the doc note is stale (not a test bug).

## KEEP
tests/sources/enums/enum_owned_payload_drop.fire | KEEP | Correct (10000, then four describe lines). Caveat: "leak/double-free sanity check" can only catch double free/crash at runtime; a leak is invisible (no runtime leak detector; leaks are caught statically by heap verifier). Header's "golden file" wording is stale.
tests/sources/enums/enum_owned_payload_no_destructor_needed.fire | KEEP | Distinct lowering branch (class payload w/o destructor), correct output.
tests/sources/match/match_expression_value.fire | KEEP | 3.14159*2*2=12.56636 -> 12.566360 correct; covers `return match` and initializer forms.
tests/sources/match/match_payload_destructure.fire | KEEP | Covers positional, rename (`radius: r`) and field omission per changelog.
tests/sources/match/match_statement_basic.fire | KEEP | Tag-only match statement (small but the only plain-block-arm tag-only match).
tests/sources/match/match_wildcard.fire | KEEP | Wildcard fallthrough with 3 distinct unmatched variants.
tests/sources/imports/imports_alias.fire | KEEP (note) | Relies on `fn main` being auto-run (top-level statements are ignored when main() exists, compiler warns). `import utils as U;` is only checked to parse (qualified access PLANNED per docs/reference/imports.md). Correct.
tests/sources/imports/imports_deep_path.fire | KEEP | Only nested-dir dotted-path import test.
tests/sources/imports/imports_entry_shadow.fire | KEEP | Entry def wins over import; output 2 / 42 correct. (Behavior not in docs/reference/imports.md -- undocumented but intentional per header.)
tests/sources/imports/imports_multi.fire | KEEP | Braced list + wildcard from two modules, plus fir/flir snapshot.
tests/sources/imports/imports_std_wildcard.fire | KEEP | Only std wildcard import test.
tests/sources/imports/imports_symbols.fire | KEEP | Braced symbol list incl. a constant.
tests/sources/imports/imports_wildcard.fire | KEEP | Wildcard of user module (func + const).
tests/sources/integration/hackathon8_mission1.fire | KEEP | Output 576 independently verified. Exercises File.read of a 3.5 KB pre-existing file, for-in over string, continue/break, `as int32`. Depends on cwd = repo root (harness guarantees). Contains an unreachable "shits broke" debug branch (unprofessional message; consider rewording).
tests/sources/integration/hackathon8_mission2.fire | KEEP | 17 independently verified (unsigned-magnitude mode). Uniquely exercises int16[1000] arrays, borrowed array param `&a: int16[]`, int8/uint8 index arithmetic. Algorithm quirks (last number never flushed, idx int8 would overflow past 127 distinct values) are the program's, not pinned incorrectly for this data.
tests/sources/integration/run_length_encoding.fire | KEEP | EXPECT verified with python groupby; 1000-char argv via `//@ arg:`.
tests/sources/std/cli/std_cli_args_basic.fire | KEEP | Out-of-range argv_at (-1, 9999) + fir/flir snapshots.
tests/sources/std/cli/std_cli_args_with_argv.fire | KEEP | Verified against args.fire: argc 10, grouped `-vg`, `--` terminator ignores later `-h`/`--output=ignored.exe`, positional vs positional_value.
tests/sources/std/collections/arraylist_enumerate.fire | KEEP | Only enumerate<T>/Pair test.
tests/sources/std/collections/arraylist_get_set.fire | KEEP | Only int32 set() test (strings set in arraylist_of_strings).
tests/sources/std/collections/arraylist_of_strings.fire | KEEP | Owned element ArrayList; same leak-claim caveat as enum_owned_payload_drop.
tests/sources/std/collections/hashmap_int_keys.fire | KEEP | set/get/has/remove/overwrite; correct.
tests/sources/std/collections/hashmap_of_owned_values.fire | KEEP | Owned V/K remove; same leak-claim caveat.
tests/sources/std/collections/hashmap_string_keys.fire | KEEP | String-key hashing, overwrite, remove.
tests/sources/std/fs/std_fs_basic.fire | KEEP (merge w/ helpers optional) | Correct vs fs.md (statuses 5,5,10,5,-2).
tests/sources/std/fs/std_fs_path_ops.fire | KEEP | rename/move/remove, correct given docs ("Updates the File path on success": after renameTo, fileA.path is b so fileA.exists() true). Does not verify the old path "a" is gone (no File object left for it) -- minor gap.
tests/sources/std/math/math_abs_min_max_clamp.fire | KEEP | All 22 values verified correct (ties, u8, i8, i64, f64).
tests/sources/std/ranges/ranges_empty_and_negative.fire | KEEP | Verified against firescript/std/ranges.fire; positive cases covered in generators/generators_basic.fire. step<=0 (infinite loop) intentionally untested.
tests/sources/std/text/split_basic.fire | KEEP | Matches text.md (5 fields for ",a,,b,").
tests/sources/std/text/split_edge_cases.fire | KEEP | Empty source -> [""], empty delim -> whole string, per text.md.
tests/sources/std/text/stringbuilder_reuse_after_build.fire | KEEP | Drain/reuse semantics per text.md.
tests/sources/std/types/option_null_vs_zero.fire | KEEP | Genuine regression for nullable scalars.
tests/sources/std/types/option_unwrap_or.fire | KEEP | Drain semantics (Owned) vs intact (Copyable) verified.
tests/sources/std/types/result_isok_iserr.fire | KEEP | Owned Result<string,string> construction.
tests/sources/std/types/result_null_vs_zero.fire | KEEP | Scalar T/E null-vs-zero on two fields.
tests/sources/std/types/result_unwrap_or.fire | KEEP | Strongest Result factory test.
tests/sources/std/types/std_types_test.fire | KEEP (WEAK on coverage) | Pair<int32,string> field access with snapshot. CopyablePair (documented "tested" in types.md) has NO direct test (only appears in a python lowering test and an FIR snapshot). Name is vague.
Helpers (not judged as tests): imports/{utils,math_utils,string_utils,visibility_provider}.fire, imports/nested/deep_provider.fire. visibility_provider.fire has a stray empty EXPECT block (harmless).

## Detailed evidence for WEAK / INCORRECT items
- enum_payload_construct (INCORRECT header): compare header text with tests/sources/enums/enum_owned_payload_drop.fire (string and class payloads compile, run, free correctly) and CLAUDE.md feature table (enums: tag-only and named-data-payload IMPLEMENTED). Suggested replacement: delete header paragraph; after `a = Shape.Rectangle(1.0, 1.0); b = Shape.Point;` add `match a { Shape.Rectangle(width, height) -> println(...) ...}` and `match c` printing code/active.
- enum_tag_only: suggested replacement: a helper `fn name(c: Color) -> string { return match c {...}; }` and println(name(a)) after `a = Color.Blue` (expect "Blue"), likewise d (expect "West").
- result_copyable: replace with e.g. `copy.value = 99;` (field assignable?) then println(original.value) expecting 10. If fields are not assignable, say so in the header and drop the independence claim.
- std_fcl_lexer: add a second source, e.g. `"{ } [ ] -5 - x_1 \"abc"` ; I ran this exact source: output was lbrace `{` 0..1, rbrace `}` 2..3, lbracket `[` 3..4, rbracket `]` 4..5, int32 `-5` 6..8, status -84 invalid `-` 9..10, identifier `x_1` 11..14, status -84 invalid `unterminated_string` 15..19, eof 19..19. Lexer behavior is consistent with init.fire, so these would be valid new expectations.
- hashmap_growth: replace the spot checks with `total += m.get(i)` over 0..49 (expect 12250) plus `has` for all keys.
- arraylist_growth: sum of v.get(i) for i in 0..24 = 600.
- syscall_basic: print `open_w.status >= 0`, write status (13), close status (0), plus open of nonexistent path with mode "r" status < 0.
- cli: add a case for `-o value`, `-o=value`, `-ovalue` and `--name value` through non-alias option_value.

## Compiler bugs discovered
None confirmed. Observations (not bugs): 
1. firescript/std/fcl/init.fire string-literal branch (lines ~136-144) returns without `drop(ch)` while every other branch drops it -- possible leak of `ch` (or the language auto-drops; I did not verify). Minimal: lex any source starting with `"`. Not observable at runtime.
2. docs/reference/std/math.md nested-generic-call note is stale (see above).
3. Enums/match have no reference doc page (only changelog); CopyablePair has no direct test despite docs saying all types are "tested".
