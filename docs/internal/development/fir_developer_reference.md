# FIR Development Quick Reference

This document provides practical guidance for developers implementing FIR and the FIR → C backend.

---

## Part 1: FIR Module Structure

### Directory Layout

```
firescript/
├── fir/                           # NEW: FIR system
│   ├── __init__.py               # Package initialization
│   ├── ir_types.py               # Type system (FIRType, SimpleType, etc.)
│   ├── ir_node.py                # IR nodes (Instruction, BasicBlock, etc.)
│   ├── ir_module.py              # Module structure (FIRModule, FIRFunction, etc.)
│   ├── ownership.py              # Ownership tracking (OwnershipState, OwnershipMap)
│   ├── ir_builder.py             # Helper class for building FIR
│   ├── textual.py                # Serialize FIR to human-readable form
│   └── __pycache__/
│
├── ast_to_fir.py                 # AST → FIR converter (NEW)
│
├── codegen/
│   ├── fir_to_c.py               # FIR → C backend (NEW; replaces generator.py)
│   ├── generator.py              # (Keep for reference; deprecated)
│   └── ... (other files)
│
└── ... (existing files)
```

### File Responsibilities

| File | Responsibility |
|---|---|
| `fir/ir_types.py` | Define `FIRType`, `SimpleType`, `ArrayType`, `FunctionType` classes |
| `fir/ir_node.py` | Define `Instruction`, `BasicBlock`, `FIRValue`, `Terminator` classes |
| `fir/ir_module.py` | Define `FIRModule`, `FIRFunction`, `TypeDef` classes |
| `fir/ownership.py` | Define `OwnershipState`, `OwnershipMap`, ownership tracking logic |
| `fir/ir_builder.py` | Provide `FIRBuilder` class for convenient FIR construction |
| `fir/textual.py` | Serialize FIR to debug text format (like `zig ast-check -t`) |
| `ast_to_fir.py` | Implement `ASTToFIRConverter` class |
| `codegen/fir_to_c.py` | Implement `FIRToCBackend` class |

---

## Part 2: Key Classes and Interfaces

### FIRType System

```python
# ir_types.py

class FIRType:
    """Base class for all FIR types."""
    pass

class SimpleType(FIRType):
    """Scalar type: int32, float64, bool, string, or custom class."""
    name: str              # "int32", "string", "Point", etc.
    category: str          # "copyable" or "owned"
    is_nullable: bool      # For future null safety
    metadata: Dict         # Additional info (for classes: fields)
    
    def __init__(self, name: str, category: str = "owned", metadata=None):
        self.name = name
        self.category = category
        self.is_nullable = False
        self.metadata = metadata or {}
    
    def is_owned(self) -> bool:
        return self.category == "owned"
    
    def is_copyable(self) -> bool:
        return self.category == "copyable"

class ArrayType(FIRType):
    """Array type: T[]."""
    element_type: FIRType
    size: Optional[int]    # None for dynamic/unknown
    
    def __init__(self, element_type: FIRType, size=None):
        self.element_type = element_type
        self.size = size
        # Arrays are always owned
        self.category = "owned"

class FunctionType(FIRType):
    """Function type: (T1, T2) -> ReturnType."""
    param_types: List[FIRType]
    param_borrowing: List[bool]  # True if param is borrowed
    return_type: Optional[FIRType]
    
    def __init__(self, params: List[FIRType], return_type=None, borrowing=None):
        self.param_types = params
        self.return_type = return_type
        self.param_borrowing = borrowing or [False] * len(params)
```

### Instructions & Values

```python
# ir_node.py

class FIRValue:
    """Represents a value produced by an instruction."""
    instruction: "Instruction"
    block: "BasicBlock"
    index: int            # Index of value in block
    
    def __init__(self, instruction, block, index):
        self.instruction = instruction
        self.block = block
        self.index = index

class Instruction:
    """Base class for all instructions."""
    opcode: str           # "IntLiteral", "BinaryOp", etc.
    operands: List[FIRValue]  # Input values
    result_type: FIRType  # Type of produced value
    metadata: Dict        # Line number, source location, etc.
    
    def __init__(self, opcode: str, operands=None, result_type=None):
        self.opcode = opcode
        self.operands = operands or []
        self.result_type = result_type
        self.metadata = {}
    
    def result(self) -> FIRValue:
        """Get the value produced by this instruction."""
        pass

class IntLiteralInst(Instruction):
    """IntLiteral(value, target_type) -> int_type."""
    value: int
    
    def __init__(self, value: int, target_type: FIRType):
        super().__init__("IntLiteral", result_type=target_type)
        self.value = value

class BinaryOpInst(Instruction):
    """BinaryOp(op, lhs, rhs) -> result_type."""
    op: str  # "+", "-", "*", "/", etc.
    
    def __init__(self, op: str, lhs: FIRValue, rhs: FIRValue, result_type: FIRType):
        super().__init__("BinaryOp", [lhs, rhs], result_type)
        self.op = op

class MoveInst(Instruction):
    """Move(value) -> value_type (marks source as MOVED)."""
    
    def __init__(self, value: FIRValue):
        super().__init__("Move", [value], value.instruction.result_type)

class BorrowInst(Instruction):
    """Borrow(value) -> reference_type (source remains VALID)."""
    
    def __init__(self, value: FIRValue):
        # Result type is same as operand (conceptually a reference)
        super().__init__("Borrow", [value], value.instruction.result_type)

class DropInst(Instruction):
    """Drop(value) -> void (destructs owned value)."""
    
    def __init__(self, value: FIRValue):
        super().__init__("Drop", [value])  # No result type

class CallInst(Instruction):
    """Call(function, args, modes) -> return_type."""
    function_ref: str     # Function name or reference
    arg_modes: List[str]  # ["own", "borrow", "own", ...]
    
    def __init__(self, function_ref: str, args: List[FIRValue], 
                 arg_modes: List[str], return_type: Optional[FIRType]):
        super().__init__("Call", args, return_type)
        self.function_ref = function_ref
        self.arg_modes = arg_modes

class Terminator(Instruction):
    """Base class for block-terminating instructions."""
    pass

class ReturnInst(Terminator):
    """Return(value?) -> (terminates)."""
    
    def __init__(self, value: Optional[FIRValue] = None):
        super().__init__("Return", [value] if value else [])

class BranchInst(Terminator):
    """Branch(cond, true_block, false_block) -> (terminates)."""
    true_block: str       # Block name
    false_block: str      # Block name
    
    def __init__(self, cond: FIRValue, true_block: str, false_block: str):
        super().__init__("Branch", [cond])
        self.true_block = true_block
        self.false_block = false_block

class BasicBlock:
    """Sequence of instructions with single entry/exit."""
    id: str               # "block_0", "block_1", etc.
    params: List[(str, FIRType)]  # Block parameters (for joins)
    instructions: List[Instruction]
    terminator: Terminator
    
    def __init__(self, block_id: str, params=None):
        self.id = block_id
        self.params = params or []
        self.instructions = []
        self.terminator = None
    
    def add_instruction(self, inst: Instruction) -> FIRValue:
        """Add instruction to block, return produced value."""
        self.instructions.append(inst)
        return FIRValue(inst, self, len(self.instructions) - 1)
    
    def set_terminator(self, term: Terminator):
        """Set block's terminating instruction."""
        self.terminator = term
```

### FIR Builder

```python
# ir_builder.py

class FIRBuilder:
    """Helper class for building FIR instructions."""
    
    current_block: BasicBlock
    function: "FIRFunction"
    
    def __init__(self, function: "FIRFunction", block: BasicBlock):
        self.function = function
        self.current_block = block
    
    # Instruction builders
    
    def int_literal(self, value: int, target_type: FIRType) -> FIRValue:
        """Build IntLiteral instruction."""
        inst = IntLiteralInst(value, target_type)
        return self.current_block.add_instruction(inst)
    
    def binary_op(self, op: str, lhs: FIRValue, rhs: FIRValue) -> FIRValue:
        """Build BinaryOp instruction."""
        # Infer result type from operands
        result_type = lhs.instruction.result_type
        inst = BinaryOpInst(op, lhs, rhs, result_type)
        return self.current_block.add_instruction(inst)
    
    def move(self, value: FIRValue) -> FIRValue:
        """Build Move instruction."""
        inst = MoveInst(value)
        return self.current_block.add_instruction(inst)
    
    def borrow(self, value: FIRValue) -> FIRValue:
        """Build Borrow instruction."""
        inst = BorrowInst(value)
        return self.current_block.add_instruction(inst)
    
    def call(self, func_name: str, args: List[FIRValue], 
             modes: List[str], return_type: Optional[FIRType]) -> FIRValue:
        """Build Call instruction."""
        inst = CallInst(func_name, args, modes, return_type)
        return self.current_block.add_instruction(inst)
    
    def drop(self, value: FIRValue):
        """Build Drop instruction (has no result)."""
        inst = DropInst(value)
        self.current_block.add_instruction(inst)
    
    def ret(self, value: Optional[FIRValue] = None):
        """Set block terminator to Return."""
        term = ReturnInst(value)
        self.current_block.set_terminator(term)
    
    def branch(self, cond: FIRValue, true_block: str, false_block: str):
        """Set block terminator to Branch."""
        term = BranchInst(cond, true_block, false_block)
        self.current_block.set_terminator(term)
```

### Ownership Tracking

```python
# ownership.py

class OwnershipState(Enum):
    """State of a binding in ownership tracking."""
    VALID = "valid"           # Binding can be used
    MOVED = "moved"           # Ownership transferred; invalid
    MAYBE_MOVED = "maybe_moved"  # Moved on some paths
    BORROWED = "borrowed"     # Currently borrowed

class OwnershipMap:
    """Tracks ownership state of values in a function."""
    
    binding_states: Dict[str, OwnershipState]  # var_name -> state
    move_invalidations: Dict[FIRValue, str]    # Move(x) -> var_name
    
    def __init__(self):
        self.binding_states = {}
        self.move_invalidations = {}
        self.borrow_lifetimes = {}
    
    def record_move(self, source_var: str, move_value: FIRValue):
        """Record that source_var was moved."""
        self.binding_states[source_var] = OwnershipState.MOVED
        self.move_invalidations[move_value] = source_var
    
    def record_borrow(self, source_var: str, borrow_start_block, borrow_end_block):
        """Record that source_var is borrowed in range."""
        self.binding_states[source_var] = OwnershipState.BORROWED
        self.borrow_lifetimes[source_var] = (borrow_start_block, borrow_end_block)
    
    def is_valid(self, var: str) -> bool:
        """Check if variable is in VALID state."""
        return self.binding_states.get(var) == OwnershipState.VALID
```

---

## Part 3: AST → FIR Conversion Template

```python
# ast_to_fir.py

class ASTToFIRConverter:
    """Convert semantic-analyzed AST to FIR."""
    
    def __init__(self, ast: ASTNode, parser_instance, source_code: str):
        self.ast = ast
        self.parser = parser_instance
        self.source_code = source_code
        self.fir_module = FIRModule()
        self.current_function: Optional[FIRFunction] = None
        self.current_block: Optional[BasicBlock] = None
        self.builder: Optional[FIRBuilder] = None
        self.value_map: Dict[ASTNode, FIRValue] = {}  # AST node -> FIR value
        self.block_counter = 0
    
    def convert(self) -> FIRModule:
        """Convert AST to FIR module."""
        for child in self.ast.children:
            if child.node_type == NodeTypes.FUNCTION_DEFINITION:
                self._convert_function(child)
            elif child.node_type == NodeTypes.CLASS_DEFINITION:
                self._convert_class(child)
        return self.fir_module
    
    def _convert_function(self, node: ASTNode) -> FIRFunction:
        """Convert function definition to FIR."""
        func_name = node.name
        
        # Extract parameters
        params = []
        param_borrowing = []
        for param in node.children:
            if param.node_type == NodeTypes.PARAMETER:
                param_name = param.name
                param_type = self._convert_type(param)
                is_borrowed = param.is_borrowed if hasattr(param, 'is_borrowed') else False
                params.append((param_name, param_type))
                param_borrowing.append(is_borrowed)
        
        # Return type
        return_type = self._convert_type(node) if node.var_type else None
        
        # Create FIR function
        fir_func = FIRFunction(func_name, params, return_type)
        self.current_function = fir_func
        
        # Create entry block
        entry_block = self._create_block()
        self.current_block = entry_block
        self.builder = FIRBuilder(fir_func, entry_block)
        
        # Convert function body
        for stmt in node.children:
            if stmt.node_type in [NodeTypes.STATEMENT, NodeTypes.BLOCK]:
                self._convert_statement(stmt)
        
        # Ensure block has terminator
        if self.current_block.terminator is None:
            self.builder.ret(None)
        
        fir_func.blocks.append(entry_block)
        self.fir_module.functions.append(fir_func)
        
        return fir_func
    
    def _convert_expression(self, node: ASTNode) -> FIRValue:
        """Convert expression to FIR value."""
        if node.node_type == NodeTypes.INTEGER_LITERAL:
            target_type = self._convert_type(node)
            return self.builder.int_literal(int(node.value), target_type)
        
        elif node.node_type == NodeTypes.BINARY_OPERATION:
            lhs = self._convert_expression(node.children[0])
            rhs = self._convert_expression(node.children[1])
            op = node.operator
            return self.builder.binary_op(op, lhs, rhs)
        
        elif node.node_type == NodeTypes.FUNCTION_CALL:
            func_name = node.name
            args = []
            modes = []  # "own", "borrow", etc.
            
            for arg in node.children:
                arg_value = self._convert_expression(arg)
                args.append(arg_value)
                # Determine if borrowed or owned based on function signature
                # For now, assume owned
                modes.append("own")
            
            return_type = self._convert_type(node)
            return self.builder.call(func_name, args, modes, return_type)
        
        elif node.node_type == NodeTypes.IDENTIFIER:
            # Look up variable in value_map or create reference
            if node in self.value_map:
                return self.value_map[node]
            else:
                # Create reference to parameter or local variable
                var_name = node.name
                var_type = self._convert_type(node)
                # Placeholder: should track value from parameter
                raise NotImplementedError(f"Variable lookup for {var_name}")
        
        else:
            raise NotImplementedError(f"Expression type {node.node_type}")
    
    def _convert_statement(self, node: ASTNode):
        """Convert statement to FIR instructions."""
        if node.node_type == NodeTypes.RETURN_STATEMENT:
            value = None
            if node.children:
                value = self._convert_expression(node.children[0])
            self.builder.ret(value)
        
        elif node.node_type == NodeTypes.IF_STATEMENT:
            cond = self._convert_expression(node.children[0])
            true_block = self._create_block()
            false_block = self._create_block()
            join_block = self._create_block()
            
            self.builder.branch(cond, true_block.id, false_block.id)
            
            # Convert true branch
            self.current_block = true_block
            self.builder = FIRBuilder(self.current_function, true_block)
            # ... convert body
            if true_block.terminator is None:
                true_block.set_terminator(JumpInst(join_block.id))
            
            # Convert false branch (if exists)
            # ...
            
            # Continue at join block
            self.current_block = join_block
            self.builder = FIRBuilder(self.current_function, join_block)
        
        else:
            raise NotImplementedError(f"Statement type {node.node_type}")
    
    def _convert_type(self, node: ASTNode) -> FIRType:
        """Convert AST type to FIR type."""
        type_name = node.var_type
        is_array = node.is_array if hasattr(node, 'is_array') else False
        
        if is_array:
            element_type = SimpleType(type_name, category="owned")
            return ArrayType(element_type)
        else:
            # Determine if owned or copyable
            category = "owned"  # Default
            if type_name in ["int32", "float64", "bool"]:
                category = "copyable"
            
            return SimpleType(type_name, category=category)
    
    def _create_block(self) -> BasicBlock:
        """Create a new basic block."""
        block_id = f"block_{self.block_counter}"
        self.block_counter += 1
        return BasicBlock(block_id)
```

---

## Part 4: FIR → C Backend Template

```python
# codegen/fir_to_c.py

class FIRToCBackend:
    """Convert FIR to C source code."""
    
    def __init__(self, fir_module: FIRModule):
        self.module = fir_module
        self.output = []
    
    def generate(self) -> str:
        """Generate complete C source."""
        self._emit_includes()
        self._emit_type_defs()
        self._emit_functions()
        return "\n".join(self.output)
    
    def _emit_includes(self):
        """Emit C includes."""
        self.output.append("#include <stdio.h>")
        self.output.append("#include <stdint.h>")
        self.output.append("#include <stdbool.h>")
        self.output.append("#include <string.h>")
        self.output.append('#include "firescript/runtime/runtime.h"')
        self.output.append("")
    
    def _emit_type_defs(self):
        """Emit C struct typedefs for classes."""
        for type_def in self.module.types:
            self._emit_type_def(type_def)
        self.output.append("")
    
    def _emit_type_def(self, type_def: TypeDef):
        """Emit single type definition."""
        # Generate C struct
        struct_name = f"_firescript_{type_def.name}"
        self.output.append(f"typedef struct {struct_name} {{")
        
        # Fields
        for field_name, field_type in type_def.fields:
            c_type = self._fir_type_to_c(field_type)
            self.output.append(f"    {c_type} {field_name};")
        
        self.output.append(f"}} {struct_name};")
    
    def _emit_functions(self):
        """Emit all FIR functions as C functions."""
        for fir_func in self.module.functions:
            self._emit_function(fir_func)
    
    def _emit_function(self, fir_func: FIRFunction):
        """Emit single FIR function as C function."""
        # Function signature
        return_type = self._fir_type_to_c(fir_func.return_type or SimpleType("void"))
        func_name = f"_firescript_{fir_func.name}"
        
        params_c = []
        for param_name, param_type in fir_func.parameters:
            c_type = self._fir_type_to_c(param_type)
            params_c.append(f"{c_type} {param_name}")
        
        params_str = ", ".join(params_c) if params_c else "void"
        self.output.append(f"{return_type} {func_name}({params_str}) {{")
        
        # Function body
        for block in fir_func.blocks:
            self._emit_block(block)
        
        self.output.append("}")
        self.output.append("")
    
    def _emit_block(self, block: BasicBlock):
        """Emit block label and instructions."""
        # Skip label for entry block (block_0)
        if block.id != "block_0":
            self.output.append(f"{block.id}:")
        
        for instr in block.instructions:
            self._emit_instruction(instr)
        
        if block.terminator:
            self._emit_terminator(block.terminator)
    
    def _emit_instruction(self, instr: Instruction):
        """Emit single instruction as C statement."""
        if instr.opcode == "IntLiteral":
            # %0 = IntLiteral(42, int32) → int32_t %0 = 42;
            var_name = self._value_name(instr)
            c_type = self._fir_type_to_c(instr.result_type)
            self.output.append(f"    {c_type} {var_name} = {instr.value};")
        
        elif instr.opcode == "BinaryOp":
            # %0 = BinaryOp("+", %1, %2) → int32_t %0 = (%1 + %2);
            var_name = self._value_name(instr)
            c_type = self._fir_type_to_c(instr.result_type)
            lhs = self._operand_name(instr.operands[0])
            rhs = self._operand_name(instr.operands[1])
            self.output.append(f"    {c_type} {var_name} = ({lhs} {instr.op} {rhs});")
        
        elif instr.opcode == "Drop":
            # Drop(x) → drop_X(x) or free(x)
            operand = self._operand_name(instr.operands[0])
            self.output.append(f"    free({operand});")
        
        elif instr.opcode == "Call":
            # Call(func, args, modes) → result = func(args);
            func_name = f"_firescript_{instr.function_ref}"
            args_c = [self._operand_name(arg) for arg in instr.operands]
            args_str = ", ".join(args_c)
            
            if instr.result_type:
                var_name = self._value_name(instr)
                c_type = self._fir_type_to_c(instr.result_type)
                self.output.append(f"    {c_type} {var_name} = {func_name}({args_str});")
            else:
                self.output.append(f"    {func_name}({args_str});")
        
        else:
            # Placeholder for other instructions
            pass
    
    def _emit_terminator(self, term: Terminator):
        """Emit terminating instruction."""
        if term.opcode == "Return":
            if term.operands:
                value = self._operand_name(term.operands[0])
                self.output.append(f"    return {value};")
            else:
                self.output.append("    return;")
        
        elif term.opcode == "Branch":
            cond = self._operand_name(term.operands[0])
            self.output.append(f"    if ({cond}) {{")
            self.output.append(f"        goto {term.true_block};")
            self.output.append("    } else {")
            self.output.append(f"        goto {term.false_block};")
            self.output.append("    }")
        
        elif term.opcode == "Jump":
            self.output.append(f"    goto {term.target_block};")
    
    def _fir_type_to_c(self, fir_type: FIRType) -> str:
        """Convert FIR type to C type string."""
        if isinstance(fir_type, SimpleType):
            type_map = {
                "int8": "int8_t",
                "int16": "int16_t",
                "int32": "int32_t",
                "int64": "int64_t",
                "float32": "float",
                "float64": "double",
                "bool": "bool",
                "string": "char*",
                "void": "void",
            }
            if fir_type.name in type_map:
                return type_map[fir_type.name]
            else:
                # Custom class (owned)
                if fir_type.is_owned():
                    return f"_firescript_{fir_type.name}*"
                else:
                    return f"_firescript_{fir_type.name}"
        
        elif isinstance(fir_type, ArrayType):
            element_c = self._fir_type_to_c(fir_type.element_type)
            return f"{element_c}*"
        
        else:
            return "void"
    
    def _value_name(self, instr: Instruction) -> str:
        """Generate C variable name for instruction result."""
        # Simple approach: use instruction address as unique ID
        return f"_v{id(instr)}"
    
    def _operand_name(self, operand: FIRValue) -> str:
        """Get C name for operand."""
        return self._value_name(operand.instruction)
```

---

## Part 5: Testing Strategy

### Test Structure

```python
# tests/fir_runner.py (NEW)

import subprocess
import os
from pathlib import Path

class FIRTestRunner:
    """Run tests using AST → FIR → C backend."""
    
    def run_test(self, source_file: str) -> bool:
        """
        Compile with FIR backend, compare output to expected.
        """
        # 1. Compile with FIR backend
        result = subprocess.run(
            ["python", "firescript/main.py", source_file, "--use-fir"],
            capture_output=True
        )
        
        if result.returncode != 0:
            print(f"Compilation failed: {result.stderr}")
            return False
        
        # 2. Run compiled binary
        binary_path = source_file.replace(".fire", "")
        output = subprocess.run([binary_path], capture_output=True).stdout.decode()
        
        # 3. Compare to expected output
        expected_path = f"tests/expected/{Path(source_file).stem}.out"
        with open(expected_path) as f:
            expected = f.read()
        
        if output == expected:
            return True
        else:
            print(f"Output mismatch in {source_file}")
            print(f"Expected:\n{expected}")
            print(f"Got:\n{output}")
            return False

# Run parallel tests
def run_all_tests():
    runner_old = OldCompilerTestRunner()  # Current backend
    runner_fir = FIRTestRunner()          # FIR backend
    
    for test_file in glob("tests/sources/*.fire"):
        old_result = runner_old.run_test(test_file)
        fir_result = runner_fir.run_test(test_file)
        
        if old_result and fir_result:
            print(f"✓ {test_file}")
        elif old_result and not fir_result:
            print(f"✗ {test_file} (FIR FAILED)")
        else:
            print(f"? {test_file} (Old also failed)")
```

### Comparison Matrix

| Test | Old Backend | FIR Backend | Status |
|---|---|---|---|
| `functions.fire` | ✓ | ✓ | Both pass |
| `ownership_demo.fire` | ✓ | (Testing) | Check ownership handling |
| `classes_smoke.fire` | ✓ | (Testing) | Check class codegen |
| `generics_basic.fire` | ✓ | (Testing) | Check monomorphization |

---

## Part 6: Debugging & Introspection

### Dumping FIR for Debugging

```python
# Enable FIR dump with flag

$ python firescript/main.py example.fire --dump-fir

# Output:
module firescript_example

type Point copyable {
  x: int32
  y: int32
}

function main() -> void {
  block_0:
    %0 = IntLiteral(10, int32)
    %1 = IntLiteral(20, int32)
    %2 = Allocate(Point, [%0, %1])
    %3 = Borrow(%2)
    %4 = Call(distance, [%3, %3], ["borrow", "borrow"]) -> int32
    Drop(%2)
    Return()
}
```

### Comparing Generated C

```python
# Side-by-side comparison of old vs. new generated C

$ python scripts/compare_codegen.py example.fire

# Output shows:
# - Differences in generated C
# - Functionality should be identical
# - Structure may differ (acceptable)
```

---

## Part 7: Common Pitfalls & Solutions

| Issue | Cause | Solution |
|---|---|---|
| "Variable not found in value_map" | Accessing parameter before creating FIRValue | Track all parameters in value_map during function setup |
| "Block has no terminator" | Forgot to add return/branch at block end | Always set terminator before moving to next block |
| "Type mismatch in BinaryOp" | Operand types differ | Enforce type checking; both must be same type |
| "Orphaned instruction" | Instruction not added to block | Use `builder.add_instruction()`, not direct construction |
| "Dangling reference after block merge" | Borrow lifetime escapes merge point | Track borrow lifetimes in OwnershipMap |

---

## Conclusion

This quick reference provides the foundational structures and patterns needed to implement FIR. Refer back to the main FIR_impl_plan.md for detailed specification and rationale.

Key takeaways:
1. **Modularize**: Separate FIR IR design, AST conversion, and code generation
2. **Test Early**: Compare outputs between old and new backends continuously
3. **Use Builders**: FIRBuilder makes instruction construction cleaner
4. **Track Ownership**: OwnershipMap is critical for correctness
5. **Debug Friendly**: Textual FIR serialization helps identify issues

Good luck with the implementation!
