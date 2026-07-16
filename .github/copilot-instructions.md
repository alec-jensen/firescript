The project name is "firescript", all lowercase. Do not capitalize it. Make sure you are not removing random code. When writing new code, keep a consistent style with the existing code. Do not add new features or change the functionality of the code unless explicitly instructed to do so. If you are unsure about something, ask for clarification. Do not make assumptions about the code or its purpose. Stuff exists the way it does for a reason.

When compiling a firescript source file, the command is 
python firescript/main.py <source-file>
Add the -d flag to view debug output during compilation.
python firescript/main.py <source-file> -d

Test sources live under tests/sources/<category>/ (e.g. tests/sources/arrays/, tests/sources/std/regex/), grouped by feature area; error tests live under the mirrored tests/sources/invalid/<category>/. There are no sidecar golden files (except FIR/FLIR IR snapshots under tests/snapshots/<category>/) — expectations live inside the .fire file itself as a trailing `/* EXPECT ... */` output block (for run tests) or `//~ ERROR <CODE>` annotations (for compile-fail tests). Whenever you add a file to examples/ or tests/sources/<category>/, run `python tests/run.py <path> --update` to generate/refresh that in-file block and review the diff before committing. Prefer one focused behavior per file over a large multi-assertion file — see tests/TEST_MANIFEST.md's "Splitting large test files" section.

Veryify the docs (/docs) for language syntax, features, and examples are accurate and up to date with the current implementation of firescript.

Compiler directives are only to be used in the standard library and should not be used in user source files except in specific scenarios (e.g., enabling syscalls). They are primarily for internal use by the compiler and standard library. Do not add directives to user source files without a clear justification. Do not add directives to tests unless necessary for testing specific compiler behavior.

Any changes to the compiler's handling of language features should be documented in the changelog under "Currently in Development". Only user-facing changes (e.g., new features, syntax changes, behavior changes) should be documented in the changelog. Internal refactorings or optimizations that do not affect user-facing behavior do not need to be documented in the changelog.

If a test fails, do not change the test case to make it pass. Instead, investigate the failure and fix the underlying issue in the compiler or standard library. Tests should only be modified if there is a change in expected behavior that is intentional and documented in the changelog.