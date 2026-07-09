module arrays_iteration_for_in

function<T> print(value: &T) -> void {
  block_0:
    %0 = LoadVar("value") -> T
    %1 = Cast(%0, string)
    Call(stdout, [%1], ["own"])
    Return()
}

function<T> println(value: &T) -> void {
  block_0:
    %0 = LoadVar("value") -> T
    %1 = Cast(%0, string)
    %2 = StringLiteral("\n", string)
    %3 = BinaryOp("+", %1, %2)
    Call(stdout, [%3], ["own"])
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
    %5 = LoadVar("nums") -> int32[4]
    DeclareLocal("__arr_n", int32[4], %5)
    %6 = IntLiteral(0, int32)
    DeclareLocal("__i_n", int32, %6)
    Jump(block_1)

  block_1:
    %7 = LoadVar("__i_n") -> int32
    %8 = IntLiteral(4, int32)
    %9 = BinaryOp("<", %7, %8)
    Branch(%9, block_2, block_3)

  block_2:
    %10 = LoadVar("__arr_n") -> int32[4]
    %11 = LoadVar("__i_n") -> int32
    %12 = IndexArray(%10, %11)
    DeclareLocal("n", int32, %12)
    %13 = LoadVar("n") -> int32
    Call(println, [%13], ["borrow"])
    Jump(block_4)

  block_3:
    %14 = LoadVar("nums") -> int32[4]
    Drop(%14)
    Return()

  block_4:
    %15 = LoadVar("__i_n") -> int32
    %16 = IntLiteral(1, int32)
    %17 = BinaryOp("+", %15, %16)
    StoreVar("__i_n", %17)
    Jump(block_1)
}
