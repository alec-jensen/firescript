module arrays_iteration_for_in

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

function main() -> void {
  block_0:
    %0 = IntLiteral(5, int32)
    %1 = IntLiteral(10, int32)
    %2 = IntLiteral(15, int32)
    %3 = IntLiteral(20, int32)
    %4 = ArrayLiteral([%0, %1, %2, %3], int32[4])
    DeclareLocal("nums", int32[4], %4)
    %5 = IntLiteral(0, int32)
    DeclareLocal("__i_n", int32, %5)
    Jump(block_1)

  block_1:
    %6 = LoadVar("__i_n") -> int32
    %7 = IntLiteral(4, int32)
    %8 = BinaryOp("<", %6, %7)
    Branch(%8, block_2, block_3)

  block_2:
    %9 = LoadVar("nums") -> int32[4]
    %10 = LoadVar("__i_n") -> int32
    %11 = IndexArray(%9, %10)
    DeclareLocal("n", int32, %11)
    %12 = LoadVar("n") -> int32
    Call(println, [%12], ["borrow"])
    Jump(block_4)

  block_3:
    %13 = LoadVar("nums") -> int32[4]
    Drop(%13)
    Return()

  block_4:
    %14 = LoadVar("__i_n") -> int32
    %15 = IntLiteral(1, int32)
    %16 = BinaryOp("+", %14, %15)
    StoreVar("__i_n", %16)
    Jump(block_1)
}
