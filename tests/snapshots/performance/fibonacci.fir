module fibonacci

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

function fib(n: int64) -> int64 {
  block_0:
    %0 = LoadVar("n") -> int64
    %1 = IntLiteral(1, int64)
    %2 = BinaryOp("<=", %0, %1)
    Branch(%2, block_2, block_1)

  block_1:
    %3 = LoadVar("n") -> int64
    %4 = IntLiteral(1, int64)
    %5 = BinaryOp("-", %3, %4)
    %6 = Call(fib, [%5], ["own"]) -> int64
    %7 = LoadVar("n") -> int64
    %8 = IntLiteral(2, int64)
    %9 = BinaryOp("-", %7, %8)
    %10 = Call(fib, [%9], ["own"]) -> int64
    %11 = BinaryOp("+", %6, %10)
    Return(%11)

  block_2:
    %12 = LoadVar("n") -> int64
    Return(%12)
}

function main() -> void {
  block_0:
    %0 = IntLiteral(20, int64)
    %1 = Call(fib, [%0], ["own"]) -> int64
    Call(println, [%1], ["borrow"])
    Return()
}
