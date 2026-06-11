module generics_basic

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

function<T> max(a: T, b: T) -> T {
  block_0:
    %0 = LoadVar("a") -> T
    %1 = LoadVar("b") -> T
    %2 = BinaryOp(">", %0, %1)
    Branch(%2, block_2, block_1)

  block_1:
    %3 = LoadVar("b") -> T
    Return(%3)

  block_2:
    %4 = LoadVar("a") -> T
    Return(%4)
}

function<T> min(a: T, b: T) -> T {
  block_0:
    %0 = LoadVar("a") -> T
    %1 = LoadVar("b") -> T
    %2 = BinaryOp("<", %0, %1)
    Branch(%2, block_2, block_1)

  block_1:
    %3 = LoadVar("b") -> T
    Return(%3)

  block_2:
    %4 = LoadVar("a") -> T
    Return(%4)
}

function<T> abs(x: T, zero: T) -> T {
  block_0:
    %0 = LoadVar("x") -> T
    %1 = LoadVar("zero") -> T
    %2 = BinaryOp("<", %0, %1)
    Branch(%2, block_2, block_1)

  block_1:
    %3 = LoadVar("x") -> T
    Return(%3)

  block_2:
    %4 = LoadVar("x") -> T
    %5 = UnaryOp("-", %4)
    Return(%5)
}

function main() -> void {
  block_0:
    %0 = IntLiteral(10, int32)
    DeclareLocal("a", int32, %0)
    %1 = IntLiteral(20, int32)
    DeclareLocal("b", int32, %1)
    %2 = LoadVar("a") -> int32
    %3 = LoadVar("b") -> int32
    %4 = Call(max, [%2, %3], ["own", "own"]) -> T
    DeclareLocal("maxVal", int32, %4)
    %5 = LoadVar("maxVal") -> int32
    Call(println, [%5], ["borrow"])
    %6 = LoadVar("a") -> int32
    %7 = LoadVar("b") -> int32
    %8 = Call(min, [%6, %7], ["own", "own"]) -> T
    DeclareLocal("minVal", int32, %8)
    %9 = LoadVar("minVal") -> int32
    Call(println, [%9], ["borrow"])
    %10 = IntLiteral(100, int64)
    DeclareLocal("c", int64, %10)
    %11 = IntLiteral(50, int64)
    DeclareLocal("d", int64, %11)
    %12 = LoadVar("c") -> int64
    %13 = LoadVar("d") -> int64
    %14 = Call(max, [%12, %13], ["own", "own"]) -> T
    DeclareLocal("maxVal64", int64, %14)
    %15 = LoadVar("maxVal64") -> int64
    Call(println, [%15], ["borrow"])
    %16 = FloatLiteral(3.14, float32)
    DeclareLocal("e", float32, %16)
    %17 = FloatLiteral(2.71, float32)
    DeclareLocal("f", float32, %17)
    %18 = LoadVar("e") -> float32
    %19 = LoadVar("f") -> float32
    %20 = Call(max, [%18, %19], ["own", "own"]) -> T
    DeclareLocal("maxFloat", float32, %20)
    %21 = LoadVar("maxFloat") -> float32
    Call(println, [%21], ["borrow"])
    %22 = IntLiteral(42, int32)
    %23 = UnaryOp("-", %22)
    DeclareLocal("negInt", int32, %23)
    %24 = LoadVar("negInt") -> int32
    %25 = IntLiteral(0, int32)
    %26 = Call(abs, [%24, %25], ["own", "own"]) -> T
    DeclareLocal("absInt", int32, %26)
    %27 = LoadVar("absInt") -> int32
    Call(println, [%27], ["borrow"])
    %28 = IntLiteral(999, int64)
    %29 = UnaryOp("-", %28)
    DeclareLocal("negInt64", int64, %29)
    %30 = LoadVar("negInt64") -> int64
    %31 = IntLiteral(0, int64)
    %32 = Call(abs, [%30, %31], ["own", "own"]) -> T
    DeclareLocal("absInt64", int64, %32)
    %33 = LoadVar("absInt64") -> int64
    Call(println, [%33], ["borrow"])
    Return()
}
