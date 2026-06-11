module generators_basic

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

generator range(end: int32) -> generator<int32> {
  block_0:
    %0 = IntLiteral(0, int32)
    DeclareLocal("i", int32, %0)
    Jump(block_1)

  block_1:
    %1 = LoadVar("i") -> int32
    %2 = LoadVar("end") -> int32
    %3 = BinaryOp("<", %1, %2)
    Branch(%3, block_2, block_3)

  block_2:
    %4 = LoadVar("i") -> int32
    Yield(%4)
    %5 = LoadVar("i") -> int32
    %6 = IntLiteral(1, int32)
    %7 = BinaryOp("+", %5, %6)
    StoreVar("i", %7)
    Jump(block_1)

  block_3:
    Return()
}

generator rangeFrom(start: int32, end: int32) -> generator<int32> {
  block_0:
    %0 = LoadVar("start") -> int32
    DeclareLocal("i", int32, %0)
    Jump(block_1)

  block_1:
    %1 = LoadVar("i") -> int32
    %2 = LoadVar("end") -> int32
    %3 = BinaryOp("<", %1, %2)
    Branch(%3, block_2, block_3)

  block_2:
    %4 = LoadVar("i") -> int32
    Yield(%4)
    %5 = LoadVar("i") -> int32
    %6 = IntLiteral(1, int32)
    %7 = BinaryOp("+", %5, %6)
    StoreVar("i", %7)
    Jump(block_1)

  block_3:
    Return()
}

generator rangeStep(start: int32, end: int32, step: int32) -> generator<int32> {
  block_0:
    %0 = LoadVar("start") -> int32
    DeclareLocal("i", int32, %0)
    Jump(block_1)

  block_1:
    %1 = LoadVar("i") -> int32
    %2 = LoadVar("end") -> int32
    %3 = BinaryOp("<", %1, %2)
    Branch(%3, block_2, block_3)

  block_2:
    %4 = LoadVar("i") -> int32
    Yield(%4)
    %5 = LoadVar("i") -> int32
    %6 = LoadVar("step") -> int32
    %7 = BinaryOp("+", %5, %6)
    StoreVar("i", %7)
    Jump(block_1)

  block_3:
    Return()
}

generator countdown(n: int32) -> generator<int32> {
  block_0:
    %0 = LoadVar("n") -> int32
    DeclareLocal("i", int32, %0)
    Jump(block_1)

  block_1:
    %1 = LoadVar("i") -> int32
    %2 = IntLiteral(0, int32)
    %3 = BinaryOp(">", %1, %2)
    Branch(%3, block_2, block_3)

  block_2:
    %4 = LoadVar("i") -> int32
    Yield(%4)
    %5 = LoadVar("i") -> int32
    %6 = IntLiteral(1, int32)
    %7 = BinaryOp("-", %5, %6)
    StoreVar("i", %7)
    Jump(block_1)

  block_3:
    Return()
}

function main() -> void {
  block_0:
    %0 = IntLiteral(5, int32)
    %1 = GenNew(range, [%0]) -> generator<int32>
    DeclareLocal("__gen_i", generator<int32>, %1)
    Jump(block_1)

  block_1:
    %2 = LoadVar("__gen_i") -> generator<int32>
    %3 = GenNext(%2) -> bool
    Branch(%3, block_2, block_3)

  block_2:
    %4 = LoadVar("__gen_i") -> generator<int32>
    %5 = GenValue(%4) -> int32
    DeclareLocal("i", int32, %5)
    %6 = LoadVar("i") -> int32
    Call(println, [%6], ["borrow"])
    Jump(block_1)

  block_3:
    %7 = IntLiteral(2, int32)
    %8 = IntLiteral(6, int32)
    %9 = GenNew(rangeFrom, [%7, %8]) -> generator<int32>
    DeclareLocal("__gen_i", generator<int32>, %9)
    Jump(block_4)

  block_4:
    %10 = LoadVar("__gen_i") -> generator<int32>
    %11 = GenNext(%10) -> bool
    Branch(%11, block_5, block_6)

  block_5:
    %12 = LoadVar("__gen_i") -> generator<int32>
    %13 = GenValue(%12) -> int32
    DeclareLocal("i", int32, %13)
    %14 = LoadVar("i") -> int32
    Call(println, [%14], ["borrow"])
    Jump(block_4)

  block_6:
    %15 = IntLiteral(0, int32)
    %16 = IntLiteral(10, int32)
    %17 = IntLiteral(3, int32)
    %18 = GenNew(rangeStep, [%15, %16, %17]) -> generator<int32>
    DeclareLocal("__gen_i", generator<int32>, %18)
    Jump(block_7)

  block_7:
    %19 = LoadVar("__gen_i") -> generator<int32>
    %20 = GenNext(%19) -> bool
    Branch(%20, block_8, block_9)

  block_8:
    %21 = LoadVar("__gen_i") -> generator<int32>
    %22 = GenValue(%21) -> int32
    DeclareLocal("i", int32, %22)
    %23 = LoadVar("i") -> int32
    Call(println, [%23], ["borrow"])
    Jump(block_7)

  block_9:
    %24 = IntLiteral(3, int32)
    %25 = GenNew(countdown, [%24]) -> generator<int32>
    DeclareLocal("__gen_v", generator<int32>, %25)
    Jump(block_10)

  block_10:
    %26 = LoadVar("__gen_v") -> generator<int32>
    %27 = GenNext(%26) -> bool
    Branch(%27, block_11, block_12)

  block_11:
    %28 = LoadVar("__gen_v") -> generator<int32>
    %29 = GenValue(%28) -> int32
    DeclareLocal("v", int32, %29)
    %30 = LoadVar("v") -> int32
    Call(println, [%30], ["borrow"])
    Jump(block_10)

  block_12:
    Return()
}
