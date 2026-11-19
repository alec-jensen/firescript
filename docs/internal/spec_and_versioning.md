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

### The beta period (before fls 1.0.0)

- During 0.N, a **preliminary fls 1.0.0** is defined and maintained as a draft: the target the
  project works toward. While it is a draft it carries a pre-release version (working name
  `1.0.0-draft.N`, a semantic-versioning pre-release identifier) and may change freely; the
  semantic-versioning guarantees above start when fls 1.0.0 is released.
- **fsc 0.N is not guaranteed to be a full implementation** of the draft. Each fsc 0.N release
  states which draft revision it tracks and which parts of it are implemented. The existing status
  markers (`[IMPLEMENTED]` / `[IN DEVELOPMENT]` / `[PLANNED]`) keep exactly this meaning: they are
  the implementation status of fsc relative to the draft, and are best generated from the feature
  registry as an implementation-status table.
- **fls 1.0.0 is released together with fsc 1.0.0**, the first release that implements the whole
  specification and passes the full conformance suite (the self-hosted release). A specification
  with no passing implementation is only a draft.
- From then on the versions are independent, as described above.
- The draft's **scope** is the feature set the roadmap builds (memory and value model, object model,
  errors and exceptions, safety rules). Anything the roadmap defers past 1.0 is explicitly out of
  the draft (for example generic enums, async, macros). Platform targets (Windows, Linux),
  directives, and the runtime internals are properties of fsc, not of the language, and are not part
  of the fls.

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

**Decided:** the fls contains the **core library contract** above (the types the language itself
depends on). The rest of the standard library is versioned separately from the fls (it may follow
its own version or be pinned by kiln), as Java separates the language specification from the
platform API.

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

## Decisions

- The specification lives in `docs/spec/`, built up from the existing `docs/reference` pages.
- Only the core library contract is part of the fls; the rest of the standard library is
  versioned separately.
- Writing the specification itself is **deferred**: not started until the owner says so. The
  design decisions it depends on (safety package, exceptions, object model) settle first.
- The terminology (fls, fsc) is added to `CLAUDE.md` and used across the docs once the project
  starts changing the terminology everywhere, not before.

## Open questions

- How an fsc that implements several fls major versions (a compatibility mode) is expressed, if
  that is ever wanted.
- How the target version interacts with the versions of the separately versioned standard library
  that kiln pulls.
- How the existing `docs/reference` pages are split into normative specification text and the
  implementation-status table.
