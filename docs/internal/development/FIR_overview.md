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
Lexer (lexer.py) → Token Stream
    ↓
Parser (parser/*.py, recursive descent) → AST
    ↓
Import Resolution (imports.py, frontend_pipeline.py) → Merged AST
    ↓
Preprocessing (preprocessor.py, drop insertion) → Annotated AST
    ↓
Semantic Analysis (semantic_analyzer.py) → Type-checked, Ownership-validated AST
    ↓
Code Generation (codegen/*.py) → C Source
    ↓
C Compiler (GCC/Clang) → Native Binary
```

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
