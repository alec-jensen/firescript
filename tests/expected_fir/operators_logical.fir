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
    %22 = LoadVar("a") -> int32
    %23 = LoadVar("c") -> int32
    %24 = BinaryOp("<", %22, %23)
    %25 = BinaryOp("&&", %21, %24)
    Branch(%25, block_2, block_1)

  block_1:
    %26 = LoadVar("a") -> int32
    %27 = LoadVar("b") -> int32
    %28 = BinaryOp("<", %26, %27)
    %29 = LoadVar("a") -> int32
    %30 = IntLiteral(0, int32)
    %31 = BinaryOp(">", %29, %30)
    %32 = BinaryOp("||", %28, %31)
    Branch(%32, block_4, block_3)

  block_2:
    %33 = StringLiteral("a is between b and c", string)
    Call(println, [%33], ["borrow"])
    Jump(block_1)

  block_3:
    %34 = LoadVar("a") -> int32
    %35 = LoadVar("b") -> int32
    %36 = BinaryOp("<", %34, %35)
    %37 = LoadVar("t") -> bool
    %38 = UnaryOp("!", %37)
    %39 = BinaryOp("||", %36, %38)
    %40 = UnaryOp("!", %39)
    Branch(%40, block_6, block_5)

  block_4:
    %41 = StringLiteral("a meets at least one condition", string)
    Call(println, [%41], ["borrow"])
    Jump(block_3)

  block_5:
    %42 = LoadVar("t") -> bool
    %43 = LoadVar("f") -> bool
    %44 = UnaryOp("!", %43)
    %45 = BinaryOp("&&", %42, %44)
    Branch(%45, block_8, block_7)

  block_6:
    %46 = StringLiteral("not/or combination works", string)
    Call(println, [%46], ["borrow"])
    Jump(block_5)

  block_7:
    %47 = StringLiteral("=== All logical operator tests passed ===", string)
    Call(println, [%47], ["borrow"])
    Return()

  block_8:
    %48 = StringLiteral("and/not combination works", string)
    Call(println, [%48], ["borrow"])
    Jump(block_7)
}
