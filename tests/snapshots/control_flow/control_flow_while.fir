module control_flow_while

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
    %0 = IntLiteral(0, int32)
    DeclareLocal("count", int32, %0)
    Jump(block_1)

  block_1:
    %1 = LoadVar("count") -> int32
    %2 = IntLiteral(5, int32)
    %3 = BinaryOp("<", %1, %2)
    Branch(%3, block_2, block_3)

  block_2:
    %4 = LoadVar("count") -> int32
    Call(println, [%4], ["borrow"])
    %5 = LoadVar("count") -> int32
    %6 = IntLiteral(1, int32)
    %7 = BinaryOp("+", %5, %6)
    StoreVar("count", %7)
    Jump(block_1)

  block_3:
    %8 = IntLiteral(0, int32)
    DeclareLocal("i", int32, %8)
    Jump(block_4)

  block_4:
    %9 = LoadVar("i") -> int32
    %10 = IntLiteral(10, int32)
    %11 = BinaryOp("<", %9, %10)
    Branch(%11, block_5, block_6)

  block_5:
    %12 = LoadVar("i") -> int32
    %13 = IntLiteral(5, int32)
    %14 = BinaryOp("==", %12, %13)
    Branch(%14, block_8, block_7)

  block_6:
    %15 = IntLiteral(0, int32)
    DeclareLocal("j", int32, %15)
    Jump(block_9)

  block_7:
    %16 = LoadVar("i") -> int32
    Call(println, [%16], ["borrow"])
    %17 = LoadVar("i") -> int32
    %18 = IntLiteral(1, int32)
    %19 = BinaryOp("+", %17, %18)
    StoreVar("i", %19)
    Jump(block_4)

  block_8:
    Jump(block_6)

  block_9:
    %20 = LoadVar("j") -> int32
    %21 = IntLiteral(5, int32)
    %22 = BinaryOp("<", %20, %21)
    Branch(%22, block_10, block_11)

  block_10:
    %23 = LoadVar("j") -> int32
    %24 = IntLiteral(1, int32)
    %25 = BinaryOp("+", %23, %24)
    StoreVar("j", %25)
    %26 = LoadVar("j") -> int32
    %27 = IntLiteral(3, int32)
    %28 = BinaryOp("==", %26, %27)
    Branch(%28, block_13, block_12)

  block_11:
    %29 = IntLiteral(0, int32)
    DeclareLocal("outer", int32, %29)
    Jump(block_14)

  block_12:
    %30 = LoadVar("j") -> int32
    Call(println, [%30], ["borrow"])
    Jump(block_9)

  block_13:
    Jump(block_9)

  block_14:
    %31 = LoadVar("outer") -> int32
    %32 = IntLiteral(3, int32)
    %33 = BinaryOp("<", %31, %32)
    Branch(%33, block_15, block_16)

  block_15:
    %34 = IntLiteral(0, int32)
    DeclareLocal("inner", int32, %34)
    Jump(block_17)

  block_16:
    Return()

  block_17:
    %35 = LoadVar("inner") -> int32
    %36 = IntLiteral(2, int32)
    %37 = BinaryOp("<", %35, %36)
    Branch(%37, block_18, block_19)

  block_18:
    %38 = LoadVar("outer") -> int32
    %39 = IntLiteral(10, int32)
    %40 = BinaryOp("*", %38, %39)
    %41 = LoadVar("inner") -> int32
    %42 = BinaryOp("+", %40, %41)
    Call(println, [%42], ["borrow"])
    %43 = LoadVar("inner") -> int32
    %44 = IntLiteral(1, int32)
    %45 = BinaryOp("+", %43, %44)
    StoreVar("inner", %45)
    Jump(block_17)

  block_19:
    %46 = LoadVar("outer") -> int32
    %47 = IntLiteral(1, int32)
    %48 = BinaryOp("+", %46, %47)
    StoreVar("outer", %48)
    Jump(block_14)
}
