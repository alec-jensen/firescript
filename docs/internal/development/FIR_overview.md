# FIR Overview and Architecture

## Executive Summary

This document summarizes the FIR+FLIR design for the firescript compiler and describes the current compiler state and motivations for adding a two-level IR.

**Current State**: Compiler uses direct AST → C translation.
**Target State**: AST → FIR → [Optimization Passes] → FLIR → [C | Assembly | JS/WASM]

## Current Compiler Architecture Analysis

### Existing Pipeline

```
Source Text
    ↓
Lexer + Parser → AST
    ↓
Import Resolution → Merged AST
    ↓
Preprocessing → Annotated AST
    ↓
Semantic Analysis → Type-checked, Ownership-validated AST
    ↓
Code Generation → C Source
    ↓
C Compiler → Native Binary
```

### Proposed FIR+FLIR Pipeline

```
Source Text
    ↓
Lexer + Parser → AST
    ↓
Import Resolution → Merged AST
    ↓
Preprocessing → Annotated AST
    ↓
Semantic Analysis → Type-checked, ownership-validated AST
    ↓
AST → FIR Converter → FIR
    ↓
[FIR Optimization Passes]
    • Constant folding
    • Dead code elimination
    • Common subexpression elimination
    ↓
FIR → FLIR Lowering → FLIR
    ↓
[Backend Selection]
    ├─ FLIR → C
    ├─ FLIR → Assembly
    └─ FLIR → JS/WASM
```

### Proposed Pipeline Stages

- **AST stage**: parser output plus import and preprocessing passes, with source structure still intact.
- **Semantic stage**: validates types, ownership, borrows, and drops while the tree is still high-level.
- **FIR stage**: preserves classes, generics, and ownership so optimization passes can still use language semantics.
- **Optimization stage**: runs high-level IR passes before lowering removes useful type information.
- **FLIR stage**: erases high-level constructs into structs, pointers, primitive operations, and ABI-aware layouts.
- **Backend stage**: emits C, assembly, or other backend targets from the lowered IR.

The main rule is that FIR stays simple and semantic, while FLIR is the lowering boundary for backend-specific code generation.

### Type System Summary

- Copyable types: numeric, float, bool, user-defined copyable classes
- Owned types: strings, arrays, user-defined classes (default), generics

### Memory & Semantic Analysis

The `SemanticAnalyzer` tracks binding scope, ownership states (VALID/MOVED/MAYBE_MOVED/BORROWED), borrow validation and drop points. Currently this information is not preserved in a reusable IR and is lost once codegen begins.

### Strengths & Weaknesses

Strengths:
- Clear ownership semantics
- Readable AST and error reporting
- Working module and generic support

Weaknesses:
- No IR for multi-backend reuse
- Late monomorphization and tight coupling of semantic analysis to codegen
- No IR-level optimizations

---

For detailed FIR and FLIR specifications, see:
- FIR spec: `FIR_fir_spec.md`
- FLIR spec: `FIR_flir_spec.md`
- Roadmap and migration: `FIR_roadmap_and_migration.md`
