module array_negative_indexing

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

function last(values: int32[]) -> int32 {
  block_0:
    %0 = LoadVar("values") -> int32[]
    %1 = IntLiteral(1, int32)
    %2 = UnaryOp("-", %1)
    %3 = IndexArray(%0, %2)
    Return(%3)
}

function main() -> void {
  block_0:
    %0 = IntLiteral(10, int32)
    %1 = IntLiteral(20, int32)
    %2 = IntLiteral(30, int32)
    %3 = IntLiteral(40, int32)
    %4 = ArrayLiteral([%0, %1, %2, %3], int32[4])
    DeclareLocal("nums", int32[4], %4)
    %5 = LoadVar("nums") -> int32[4]
    %6 = IntLiteral(1, int32)
    %7 = UnaryOp("-", %6)
    %8 = IndexArray(%5, %7)
    Call(println, [%8], ["borrow"])
    %9 = LoadVar("nums") -> int32[4]
    %10 = IntLiteral(2, int32)
    %11 = UnaryOp("-", %10)
    %12 = IndexArray(%9, %11)
    Call(println, [%12], ["borrow"])
    %13 = IntLiteral(3, int32)
    %14 = UnaryOp("-", %13)
    DeclareLocal("idx", int32, %14)
    %15 = LoadVar("nums") -> int32[4]
    %16 = LoadVar("idx") -> int32
    %17 = IndexArray(%15, %16)
    Call(println, [%17], ["borrow"])
    %18 = IntLiteral(99, int32)
    %19 = LoadVar("nums") -> int32[4]
    %20 = IntLiteral(1, int32)
    %21 = UnaryOp("-", %20)
    StoreArray(%19, %21, %18)
    %22 = LoadVar("nums") -> int32[4]
    %23 = IntLiteral(3, int32)
    %24 = IndexArray(%22, %23)
    Call(println, [%24], ["borrow"])
    %25 = LoadVar("nums") -> int32[4]
    %26 = Call(last, [%25], ["own"]) -> int32
    Call(println, [%26], ["borrow"])
    Return()
}
