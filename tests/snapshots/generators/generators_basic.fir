module generators_basic

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
    %7 = LoadVar("__gen_i") -> generator<int32>
    Drop(%7)
    %8 = IntLiteral(2, int32)
    %9 = IntLiteral(6, int32)
    %10 = GenNew(rangeFrom, [%8, %9]) -> generator<int32>
    DeclareLocal("__gen_i__2", generator<int32>, %10)
    Jump(block_4)

  block_4:
    %11 = LoadVar("__gen_i__2") -> generator<int32>
    %12 = GenNext(%11) -> bool
    Branch(%12, block_5, block_6)

  block_5:
    %13 = LoadVar("__gen_i__2") -> generator<int32>
    %14 = GenValue(%13) -> int32
    DeclareLocal("i__2", int32, %14)
    %15 = LoadVar("i__2") -> int32
    Call(println, [%15], ["borrow"])
    Jump(block_4)

  block_6:
    %16 = LoadVar("__gen_i__2") -> generator<int32>
    Drop(%16)
    %17 = IntLiteral(0, int32)
    %18 = IntLiteral(10, int32)
    %19 = IntLiteral(3, int32)
    %20 = GenNew(rangeStep, [%17, %18, %19]) -> generator<int32>
    DeclareLocal("__gen_i__3", generator<int32>, %20)
    Jump(block_7)

  block_7:
    %21 = LoadVar("__gen_i__3") -> generator<int32>
    %22 = GenNext(%21) -> bool
    Branch(%22, block_8, block_9)

  block_8:
    %23 = LoadVar("__gen_i__3") -> generator<int32>
    %24 = GenValue(%23) -> int32
    DeclareLocal("i__3", int32, %24)
    %25 = LoadVar("i__3") -> int32
    Call(println, [%25], ["borrow"])
    Jump(block_7)

  block_9:
    %26 = LoadVar("__gen_i__3") -> generator<int32>
    Drop(%26)
    %27 = IntLiteral(3, int32)
    %28 = GenNew(countdown, [%27]) -> generator<int32>
    DeclareLocal("__gen_v", generator<int32>, %28)
    Jump(block_10)

  block_10:
    %29 = LoadVar("__gen_v") -> generator<int32>
    %30 = GenNext(%29) -> bool
    Branch(%30, block_11, block_12)

  block_11:
    %31 = LoadVar("__gen_v") -> generator<int32>
    %32 = GenValue(%31) -> int32
    DeclareLocal("v", int32, %32)
    %33 = LoadVar("v") -> int32
    Call(println, [%33], ["borrow"])
    Jump(block_10)

  block_12:
    %34 = LoadVar("__gen_v") -> generator<int32>
    Drop(%34)
    Return()
}
