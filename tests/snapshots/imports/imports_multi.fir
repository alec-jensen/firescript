module imports_multi

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

function square(x: int32) -> int32 {
  block_0:
    %0 = LoadVar("x") -> int32
    %1 = LoadVar("x") -> int32
    %2 = BinaryOp("*", %0, %1)
    Return(%2)
}

function double_val(x: int32) -> int32 {
  block_0:
    %0 = LoadVar("x") -> int32
    %1 = LoadVar("x") -> int32
    %2 = BinaryOp("+", %0, %1)
    Return(%2)
}

function wrap(s: string) -> string {
  block_0:
    %0 = StringLiteral("[", string)
    %1 = LoadVar("s") -> string
    %2 = BinaryOp("+", %0, %1)
    %3 = StringLiteral("]", string)
    %4 = BinaryOp("+", %2, %3)
    %5 = LoadVar("s") -> string
    Drop(%5)
    Return(%4)
}

function main() -> void {
  block_0:
    %0 = IntLiteral(100, int32)
    DeclareLocal("MAX", int32, %0)
    %1 = StringLiteral("-- Math Operations --", string)
    Call(println, [%1], ["borrow"])
    %2 = IntLiteral(5, int32)
    %3 = Call(square, [%2], ["own"]) -> int32
    Call(println, [%3], ["borrow"])
    %4 = IntLiteral(10, int32)
    %5 = Call(square, [%4], ["own"]) -> int32
    Call(println, [%5], ["borrow"])
    %6 = LoadVar("MAX") -> int32
    Call(println, [%6], ["borrow"])
    %7 = StringLiteral("-- String Operations --", string)
    Call(println, [%7], ["borrow"])
    %8 = StringLiteral("hello", string)
    %9 = Call(wrap, [%8], ["own"]) -> string
    Call(println, [%9], ["borrow"])
    %10 = StringLiteral("imports work", string)
    %11 = Call(wrap, [%10], ["own"]) -> string
    Call(println, [%11], ["borrow"])
    Return()
}
