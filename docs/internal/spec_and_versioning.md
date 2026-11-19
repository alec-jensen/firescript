# language specification and compiler versioning

> Status: **[PLANNED]** — a governance and terminology design. Nothing here is implemented: the
> compiler does not yet read a target spec version, and there is no formal specification document
> yet (the reference pages under `docs/reference` are the closest thing, and mix specified behavior
> with implementation status). The release roadmap is [version_planning.md](version_planning.md).

## Terminology

- **firescript** is the language, and is defined by the **firescript Language Specification
  (fls)**. When the language is discussed in general, "firescript" means what the fls says.
- **fsc** is the **firescript Compiler**, an implementation of the fls.
- **kiln** is the build tool and package manager.
- The fls and fsc are versioned **independently**, both with semantic versioning.

All three names are lowercase, like the project name.

## The compatibility contract

- Every fsc release declares the fls version it implements, for example *fsc 2.4.3 implements
  fls 1.4.3*.
- A project declares the fls version it **targets** (in its kiln manifest), for example
  *fls = 1.2.5*.
- kiln resolves the **newest fsc** whose implemented fls version is compatible with the project's
  target. Under semantic versioning, "compatible" means the **same major version and an implemented
  version greater than or equal to the target**: fls 1.4.3 is a superset of fls 1.2.5, so fsc
  2.4.3 is chosen for a project targeting fls 1.2.5.
- A project targeting fls 1.2.5 must not silently depend on later features. fsc therefore has to
  **reject features introduced after the target version** (feature gating), including language
  syntax, semantics, diagnostics that change validity, and standard-library APIs.

### Current state

fsc does not gate features by spec version, and will not until after the self-hosting bootstrap:
the gating needs a significant architectural change (every syntactic form, semantic rule,
diagnostic, and library API must carry a "since" version and be checked against the target). Until
then fsc accepts everything it implements regardless of the target. The work below only prepares
for the later change; it adds no gating code.

## Versioning rules

### fls

- **MAJOR**: a change that alters the validity or meaning of a program that was valid under the
  previous version. That includes removing or renaming a feature, tightening a rule so that
  formerly accepted programs are rejected, and changing defined behavior.
- **MINOR**: backward-compatible additions: new features, new standard-library APIs, new
  behavior in previously unspecified territory.
- **PATCH**: clarifications, corrections of wording or examples, and non-normative changes; no
  change to which programs are valid or what they do.
- Before 1.0, per semantic versioning, any 0.x release may make breaking changes.

### fsc

fsc has its own semantic version, which covers the compiler and its tool contract (command line,
exit codes, diagnostics format, output layout). A new fsc major is warranted when a tool-contract
change breaks users or when support for an fls major version is dropped. Which fls version an fsc
release implements is recorded with every release.

### Before 1.0

Until the self-hosted 1.0 release, fls and fsc advance **together**, so the roadmap versions in
[version_planning.md](version_planning.md) keep one meaning (fsc 0.N implements fls 0.N). The two
numbers diverge after 1.0, when the independent versioning above takes effect.

## What the specification contains (proposed)

A normative document, using RFC 2119 wording (MUST, SHOULD, MAY), with each feature annotated
"since fls X.Y":

1. Lexical structure (tokens, literals, identifiers, comments, escape sequences)
2. A formal grammar (EBNF). Today the grammar is implicit in the hand-written parser.
3. Types (numeric, `char`, `string`, arrays, classes, interfaces, generics, nullable types)
4. Expressions, operators, conversions, and the overflow/trap rules
5. Statements and control flow
6. Declarations: functions, classes, interfaces, enums, constants, module-level variables,
   visibility
7. The value, copy, move, and borrow model, and const rules
8. Errors: traps and exceptions, `Result`
9. Modules, imports, and exports
10. Directives and the compilation model (what a conforming implementation must diagnose)
11. The **core library contract**: the types the language itself depends on (`Object`, the
    primitive bindings, `Exception`, `Result`/`Option`, the standard interfaces)

Open: whether the whole standard library is part of the fls or only the core library the language
depends on (Java separates the language specification from the platform API; the standard library
could carry its own version, or follow the fls version).

## Preparing now, without the architecture change

1. **Spec-first changes.** A language change is written into the specification (with its "since"
   version) before or with the compiler change, never only in the compiler.
2. **A machine-readable feature registry** derived from the spec: each syntactic form, semantic
   rule, diagnostic code, and library API with its "since" version. Gating can later be generated
   from it. Add the registry; do not add gating.
3. **The test suite becomes the conformance suite.** Each `.fire` test records the spec section it
   covers; the suite is then what any conforming implementation, including the self-hosted fsc,
   must pass.
4. **Split the changelog** into an fls changelog (language and core-library changes, by spec
   version) and an fsc changelog (compiler and tooling changes).
5. **Status markers keep their meaning.** `[IMPLEMENTED]` / `[IN DEVELOPMENT]` / `[PLANNED]` describe
   the state of fsc relative to the spec. Once a formal spec exists, the spec text carries no status
   markers; they live in an implementation-status table.
6. **Diagnostic codes are part of the contract.** The `FS-*` codes that identify rule violations
   should be allocated by the spec (a stable code per specified rule) and stay stable across fsc
   releases.

## Open questions

- Whether the whole standard library, or only the core library, is part of the fls.
- Where the specification lives in the repository (a top-level `spec/` directory, or
  `docs/spec/`), and how it relates to the existing `docs/reference` pages (which are the natural
  starting material).
- How an fsc that implements several fls major versions (a compatibility mode) is expressed, if
  that is ever wanted.
- How the target version interacts with standard-library versions pulled by kiln.
