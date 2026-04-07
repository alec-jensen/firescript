# firescript config language

firescript config language (fcl) is a typed, human-readable configuration DSL designed for firescript configs.

fcl is intended for the same use cases where teams often choose YAML or TOML, but with syntax and semantics aligned to firescript.

## Purpose

fcl is config-first. It exists to make project configuration and structured data easier to write, validate, and consume from firescript.

Files use the `.fcl` extension.

## Core Principle

fcl is a typed configuration DSL, not a general-purpose programming language.

To keep that boundary clear, fcl is deliberately non-general in three ways:

- It can only produce data (a single exported value or object graph).
- It does not allow user-defined behavior (no functions, methods, or loops). Type declarations are structural only.
- It only allows a small set of total, deterministic expressions so complexity cannot grow unchecked.

These constraints should be enforced at the parser and typechecker level.
With these guardrails, fcl can evolve with new configuration features without becoming a full programming language.

## Relationship to firescript

fcl is designed as a constrained subset of firescript concepts:

- You can define structured data using explicit types.
- You can define interface-compatible typed structures and typed variables in fcl files.
- fcl data is accessible from firescript.
- The language remains intentionally focused on configuration and predictable static structure.

This keeps fcl familiar to firescript users while preserving a clear config-oriented scope.

## Usage Modes

fcl is planned to support two major modes:

- Compile-time mode: fcl files are imported and consumed during compilation.
- Runtime mode (future): fcl files are read through an fcl interpreter.

For runtime usage, schema is defined as an interface in the firescript program. Runtime-loaded fcl data is validated against that interface so structure and types remain explicit.

## Data Model and Expression Layer

fcl follows a typed object graph model with a small expression layer.
Files are primarily declarative, while still allowing constrained expressions inside values.

## Example fcl Files

The examples below are illustrative and intended to show the design direction.

### Basic static configuration

```fcl
class AppConfig {
	string appName = "firescript-app"
	int32 port = 8080
	bool enableTelemetry = false
	[string] allowedHosts = ["localhost", "127.0.0.1"]
}
```

### Using deterministic expression helpers

```fcl
class BuildConfig {
	string mode = (optEnv("BUILD_MODE") ?? "debug")
	string outputDir = pathJoin("build", mode)
	int32 workerCount = parseInt((optEnv("WORKERS") ?? "4"))
}
```

### Conditional expression in a value

```fcl
class RuntimeConfig {
	string environment = (optEnv("ENV") ?? "dev")
	string logLevel = if (environment == "prod") { "warn" } else { "debug" } // Note: expression form of if/else is not currently implemented and may be different syntax when added.
}
```

### Interface-backed runtime loading (firescript)

When loading fcl at runtime, define the expected structure as an interface in firescript:

```firescript
interface RuntimeConfig {
	string environment;
	string logLevel;
	int32 port;
}

RuntimeConfig cfg = load_config<RuntimeConfig>("config.fcl");
```

### Allowed

- Literals (`"text"`, numeric literals, `true`, `false`, `null`)
- Object/class initializers for config structures
- Arrays and maps
- `if/else` expressions (expression form, not statement form)
- Null coalescing (`??`)
- Optional ternary expression (`?:`) if adopted
- A small set of built-in pure functions (for example `env()`, `optEnv()`, `pathJoin()`, `parseInt()`)
- Imports of types only, or config-class-only imports

### Not Allowed

- Defining functions
- Calling arbitrary methods
- Loops (`for`, `while`)
- Mutation or reassignment (config values are effectively `const`)
- General module-system behavior or arbitrary code execution

## Logic and Execution Roadmap

fcl is declarative first, but limited logic is planned over time:

- Basic logic support is planned for future versions.
- Runtime interpretation is planned after compile-time workflows.
- Longer term, this roadmap may enable JIT-style execution paths for fcl.

These capabilities are intended to evolve without changing fcl's core identity as a typed configuration format for firescript.

## Name and Extension

The official name is firescript config language.

- The short form is fcl.
- The file extension is `.fcl`.
- fcl remains focused on being a firescript-native alternative to YAML/TOML for configuration.
