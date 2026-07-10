module classes_static_methods

type Math owned {
}

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
    %2 = StringLiteral("\n", string)
    %3 = BinaryOp("+", %1, %2)
    DeclareLocal("text", string, %3)
    %4 = LoadVar("text") -> string
    Call(stdout, [%4], ["borrow"])
    %5 = LoadVar("text") -> string
    Drop(%5)
    Return()
}

function Math.max(a: int32, b: int32) -> int32 {
  block_0:
    %0 = LoadVar("a") -> int32
    %1 = LoadVar("b") -> int32
    %2 = BinaryOp(">", %0, %1)
    Branch(%2, block_2, block_1)

  block_1:
    %3 = LoadVar("b") -> int32
    Return(%3)

  block_2:
    %4 = LoadVar("a") -> int32
    Return(%4)
}

function Math.add(a: int32, b: int32) -> int32 {
  block_0:
    %0 = LoadVar("a") -> int32
    %1 = LoadVar("b") -> int32
    %2 = BinaryOp("+", %0, %1)
    Return(%2)
}

function Math.twice(this: Math, x: int32) -> int32 {
  block_0:
    %0 = LoadVar("this") -> Math
    Drop(%0)
    %1 = LoadVar("x") -> int32
    %2 = IntLiteral(2, int32)
    %3 = BinaryOp("*", %1, %2)
    Return(%3)
}

function main() -> void {
  block_0:
    %0 = IntLiteral(3, int32)
    %1 = IntLiteral(7, int32)
    %2 = Call(Math.max, [%0, %1], ["own", "own"]) -> int32
    Call(println, [%2], ["borrow"])
    %3 = IntLiteral(8, int32)
    %4 = IntLiteral(5, int32)
    %5 = Call(Math.add, [%3, %4], ["own", "own"]) -> int32
    Call(println, [%5], ["borrow"])
    %6 = Allocate(Math, [])
    DeclareLocal("m", Math, %6)
    %7 = LoadVar("m") -> Math
    %8 = IntLiteral(6, int32)
    %9 = MethodCall(%7, "twice", [%8], ["own"]) -> int32
    Call(println, [%9], ["borrow"])
    %10 = LoadVar("m") -> Math
    Drop(%10)
    Return()
}
