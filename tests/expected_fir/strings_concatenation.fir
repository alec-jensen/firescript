module strings_concatenation

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
    %0 = StringLiteral("Hello", string)
    DeclareLocal("s1", string, %0)
    %1 = StringLiteral("World", string)
    DeclareLocal("s2", string, %1)
    %2 = LoadVar("s1") -> string
    %3 = StringLiteral(", ", string)
    %4 = BinaryOp("+", %2, %3)
    %5 = LoadVar("s2") -> string
    %6 = BinaryOp("+", %4, %5)
    %7 = StringLiteral("!", string)
    %8 = BinaryOp("+", %6, %7)
    DeclareLocal("greeting", string, %8)
    %9 = LoadVar("s1") -> string
    Drop(%9)
    %10 = LoadVar("s2") -> string
    Drop(%10)
    %11 = LoadVar("greeting") -> string
    Call(println, [%11], ["borrow"])
    %12 = LoadVar("greeting") -> string
    Drop(%12)
    %13 = StringLiteral("Line 1", string)
    %14 = StringLiteral(" ", string)
    %15 = BinaryOp("+", %13, %14)
    %16 = StringLiteral("Line 2", string)
    %17 = BinaryOp("+", %15, %16)
    %18 = StringLiteral(" ", string)
    %19 = BinaryOp("+", %17, %18)
    %20 = StringLiteral("Line 3", string)
    %21 = BinaryOp("+", %19, %20)
    DeclareLocal("multi", string, %21)
    %22 = LoadVar("multi") -> string
    Call(println, [%22], ["borrow"])
    %23 = LoadVar("multi") -> string
    Drop(%23)
    %24 = IntLiteral(5, int32)
    DeclareLocal("count", int32, %24)
    %25 = StringLiteral("Count: ", string)
    %26 = LoadVar("count") -> int32
    %27 = Cast(%26, string)
    %28 = BinaryOp("+", %25, %27)
    DeclareLocal("result", string, %28)
    %29 = LoadVar("result") -> string
    Call(println, [%29], ["borrow"])
    %30 = LoadVar("result") -> string
    Drop(%30)
    %31 = StringLiteral("Alice", string)
    DeclareLocal("name", string, %31)
    %32 = StringLiteral("30", string)
    DeclareLocal("age_str", string, %32)
    %33 = StringLiteral("Name: ", string)
    %34 = LoadVar("name") -> string
    %35 = BinaryOp("+", %33, %34)
    %36 = StringLiteral(", Age: ", string)
    %37 = BinaryOp("+", %35, %36)
    %38 = LoadVar("age_str") -> string
    %39 = BinaryOp("+", %37, %38)
    DeclareLocal("info", string, %39)
    %40 = LoadVar("name") -> string
    Drop(%40)
    %41 = LoadVar("age_str") -> string
    Drop(%41)
    %42 = LoadVar("info") -> string
    Call(println, [%42], ["borrow"])
    %43 = LoadVar("info") -> string
    Drop(%43)
    %44 = StringLiteral("", string)
    DeclareLocal("build", string, %44)
    %45 = LoadVar("build") -> string
    %46 = StringLiteral("a", string)
    %47 = BinaryOp("+", %45, %46)
    %48 = LoadVar("build") -> string
    Drop(%48)
    StoreVar("build", %47)
    %49 = LoadVar("build") -> string
    %50 = StringLiteral("b", string)
    %51 = BinaryOp("+", %49, %50)
    %52 = LoadVar("build") -> string
    Drop(%52)
    StoreVar("build", %51)
    %53 = LoadVar("build") -> string
    %54 = StringLiteral("c", string)
    %55 = BinaryOp("+", %53, %54)
    %56 = LoadVar("build") -> string
    Drop(%56)
    StoreVar("build", %55)
    %57 = LoadVar("build") -> string
    Call(println, [%57], ["borrow"])
    %58 = LoadVar("build") -> string
    Drop(%58)
    Return()
}
