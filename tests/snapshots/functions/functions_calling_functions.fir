module functions_calling_functions

function<T> print(value: &T) -> void {
  block_0:
    %0 = LoadVar("value") -> T
    %1 = Cast(%0, string)
    DeclareLocal("text", string, %1)
    %2 = LoadVar("text") -> string
    Call(stdout, [%2], ["borrow"])
    %3 = LoadVar("text") -> string
    Drop(%3)
    Return()
}

function<T> println(value: &T) -> void {
  block_0:
    %0 = LoadVar("value") -> T
    %1 = Cast(%0, string)
    DeclareLocal("cast_text", string, %1)
    %2 = LoadVar("cast_text") -> string
    %3 = StringLiteral("\n", string)
    %4 = BinaryOp("+", %2, %3)
    DeclareLocal("text", string, %4)
    %5 = LoadVar("cast_text") -> string
    Drop(%5)
    %6 = LoadVar("text") -> string
    Call(stdout, [%6], ["borrow"])
    %7 = LoadVar("text") -> string
    Drop(%7)
    Return()
}

function add(a: int32, b: int32) -> int32 {
  block_0:
    %0 = LoadVar("a") -> int32
    %1 = LoadVar("b") -> int32
    %2 = BinaryOp("+", %0, %1)
    Return(%2)
}

function double(x: int32) -> int32 {
  block_0:
    %0 = LoadVar("x") -> int32
    %1 = IntLiteral(2, int32)
    %2 = BinaryOp("*", %0, %1)
    Return(%2)
}

function addThenDouble(a: int32, b: int32) -> int32 {
  block_0:
    %0 = LoadVar("a") -> int32
    %1 = LoadVar("b") -> int32
    %2 = Call(add, [%0, %1], ["own", "own"]) -> int32
    DeclareLocal("sum", int32, %2)
    %3 = LoadVar("sum") -> int32
    %4 = Call(double, [%3], ["own"]) -> int32
    Return(%4)
}

function complexCalc(a: int32, b: int32, c: int32) -> int32 {
  block_0:
    %0 = LoadVar("a") -> int32
    %1 = LoadVar("b") -> int32
    %2 = BinaryOp("+", %0, %1)
    DeclareLocal("temp", int32, %2)
    %3 = LoadVar("temp") -> int32
    %4 = LoadVar("c") -> int32
    %5 = BinaryOp("*", %3, %4)
    StoreVar("temp", %5)
    %6 = LoadVar("temp") -> int32
    %7 = IntLiteral(100, int32)
    %8 = BinaryOp(">", %6, %7)
    Branch(%8, block_2, block_1)

  block_1:
    %9 = LoadVar("temp") -> int32
    Return(%9)

  block_2:
    %10 = LoadVar("temp") -> int32
    %11 = IntLiteral(2, int32)
    %12 = BinaryOp("/", %10, %11)
    Return(%12)
}

function main() -> void {
  block_0:
    %0 = IntLiteral(2, int32)
    %1 = IntLiteral(3, int32)
    %2 = Call(addThenDouble, [%0, %1], ["own", "own"]) -> int32
    Call(println, [%2], ["borrow"])
    %3 = IntLiteral(10, int32)
    %4 = IntLiteral(20, int32)
    %5 = IntLiteral(5, int32)
    %6 = Call(complexCalc, [%3, %4, %5], ["own", "own", "own"]) -> int32
    Call(println, [%6], ["borrow"])
    %7 = IntLiteral(2, int32)
    %8 = IntLiteral(3, int32)
    %9 = IntLiteral(4, int32)
    %10 = Call(complexCalc, [%7, %8, %9], ["own", "own", "own"]) -> int32
    Call(println, [%10], ["borrow"])
    Return()
}
