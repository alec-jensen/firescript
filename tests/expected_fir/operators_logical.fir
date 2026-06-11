module operators_logical

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
    %0 = StringLiteral("=== Logical Operators ===", string)
    Call(println, [%0], ["borrow"])
    %1 = StringLiteral("--- Boolean Basics ---", string)
    Call(println, [%1], ["borrow"])
    %2 = BoolLiteral(true, bool)
    DeclareLocal("t", bool, %2)
    %3 = BoolLiteral(false, bool)
    DeclareLocal("f", bool, %3)
    %4 = LoadVar("t") -> bool
    Call(println, [%4], ["borrow"])
    %5 = LoadVar("f") -> bool
    Call(println, [%5], ["borrow"])
    %6 = LoadVar("t") -> bool
    %7 = BoolLiteral(true, bool)
    %8 = BinaryOp("==", %6, %7)
    Call(println, [%8], ["borrow"])
    %9 = LoadVar("f") -> bool
    %10 = BoolLiteral(false, bool)
    %11 = BinaryOp("==", %9, %10)
    Call(println, [%11], ["borrow"])
    %12 = LoadVar("t") -> bool
    %13 = LoadVar("f") -> bool
    %14 = BinaryOp("==", %12, %13)
    Call(println, [%14], ["borrow"])
    %15 = StringLiteral("--- Logical Conditions ---", string)
    Call(println, [%15], ["borrow"])
    %16 = IntLiteral(10, int32)
    DeclareLocal("a", int32, %16)
    %17 = IntLiteral(5, int32)
    DeclareLocal("b", int32, %17)
    %18 = IntLiteral(15, int32)
    DeclareLocal("c", int32, %18)
    %19 = LoadVar("a") -> int32
    %20 = LoadVar("b") -> int32
    %21 = BinaryOp(">", %19, %20)
    DeclareLocal("__sc_2_32", bool, %21)
    %22 = LoadVar("__sc_2_32") -> bool
    Branch(%22, block_2, block_3)

  block_1:
    %23 = LoadVar("a") -> int32
    %24 = LoadVar("b") -> int32
    %25 = BinaryOp("<", %23, %24)
    DeclareLocal("__sc_6_0", bool, %25)
    %26 = LoadVar("__sc_6_0") -> bool
    Branch(%26, block_7, block_6)

  block_2:
    %27 = LoadVar("a") -> int32
    %28 = LoadVar("c") -> int32
    %29 = BinaryOp("<", %27, %28)
    StoreVar("__sc_2_32", %29)
    Jump(block_3)

  block_3:
    %30 = LoadVar("__sc_2_32") -> bool
    Branch(%30, block_4, block_1)

  block_4:
    %31 = StringLiteral("a is between b and c", string)
    Call(println, [%31], ["borrow"])
    Jump(block_1)

  block_5:
    %32 = LoadVar("a") -> int32
    %33 = LoadVar("b") -> int32
    %34 = BinaryOp("<", %32, %33)
    DeclareLocal("__sc_10_0", bool, %34)
    %35 = LoadVar("__sc_10_0") -> bool
    Branch(%35, block_11, block_10)

  block_6:
    %36 = LoadVar("a") -> int32
    %37 = IntLiteral(0, int32)
    %38 = BinaryOp(">", %36, %37)
    StoreVar("__sc_6_0", %38)
    Jump(block_7)

  block_7:
    %39 = LoadVar("__sc_6_0") -> bool
    Branch(%39, block_8, block_5)

  block_8:
    %40 = StringLiteral("a meets at least one condition", string)
    Call(println, [%40], ["borrow"])
    Jump(block_5)

  block_9:
    %41 = LoadVar("t") -> bool
    DeclareLocal("__sc_14_0", bool, %41)
    %42 = LoadVar("__sc_14_0") -> bool
    Branch(%42, block_14, block_15)

  block_10:
    %43 = LoadVar("t") -> bool
    %44 = UnaryOp("!", %43)
    StoreVar("__sc_10_0", %44)
    Jump(block_11)

  block_11:
    %45 = LoadVar("__sc_10_0") -> bool
    %46 = UnaryOp("!", %45)
    Branch(%46, block_12, block_9)

  block_12:
    %47 = StringLiteral("not/or combination works", string)
    Call(println, [%47], ["borrow"])
    Jump(block_9)

  block_13:
    %48 = StringLiteral("=== All logical operator tests passed ===", string)
    Call(println, [%48], ["borrow"])
    Return()

  block_14:
    %49 = LoadVar("f") -> bool
    %50 = UnaryOp("!", %49)
    StoreVar("__sc_14_0", %50)
    Jump(block_15)

  block_15:
    %51 = LoadVar("__sc_14_0") -> bool
    Branch(%51, block_16, block_13)

  block_16:
    %52 = StringLiteral("and/not combination works", string)
    Call(println, [%52], ["borrow"])
    Jump(block_13)
}
