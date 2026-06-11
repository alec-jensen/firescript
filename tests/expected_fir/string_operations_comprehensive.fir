module string_operations_comprehensive

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
    %0 = StringLiteral("=== String Operation Tests ===", string)
    Call(println, [%0], ["borrow"])
    %1 = StringLiteral("--- String Basics ---", string)
    Call(println, [%1], ["borrow"])
    %2 = StringLiteral("Hello", string)
    DeclareLocal("s1", string, %2)
    %3 = StringLiteral("World", string)
    DeclareLocal("s2", string, %3)
    %4 = StringLiteral("", string)
    DeclareLocal("empty", string, %4)
    %5 = LoadVar("s1") -> string
    Call(println, [%5], ["borrow"])
    %6 = LoadVar("s2") -> string
    Call(println, [%6], ["borrow"])
    %7 = LoadVar("empty") -> string
    Call(println, [%7], ["borrow"])
    %8 = LoadVar("empty") -> string
    Drop(%8)
    %9 = StringLiteral("--- String Concatenation ---", string)
    Call(println, [%9], ["borrow"])
    %10 = LoadVar("s1") -> string
    %11 = StringLiteral(", ", string)
    %12 = BinaryOp("+", %10, %11)
    %13 = LoadVar("s2") -> string
    %14 = BinaryOp("+", %12, %13)
    %15 = StringLiteral("!", string)
    %16 = BinaryOp("+", %14, %15)
    DeclareLocal("greeting", string, %16)
    %17 = LoadVar("s1") -> string
    Drop(%17)
    %18 = LoadVar("s2") -> string
    Drop(%18)
    %19 = LoadVar("greeting") -> string
    Call(println, [%19], ["borrow"])
    %20 = LoadVar("greeting") -> string
    Drop(%20)
    %21 = StringLiteral("Line 1", string)
    %22 = StringLiteral(" ", string)
    %23 = BinaryOp("+", %21, %22)
    %24 = StringLiteral("Line 2", string)
    %25 = BinaryOp("+", %23, %24)
    %26 = StringLiteral(" ", string)
    %27 = BinaryOp("+", %25, %26)
    %28 = StringLiteral("Line 3", string)
    %29 = BinaryOp("+", %27, %28)
    DeclareLocal("multi", string, %29)
    %30 = LoadVar("multi") -> string
    Call(println, [%30], ["borrow"])
    %31 = LoadVar("multi") -> string
    Drop(%31)
    %32 = StringLiteral("--- Special Characters ---", string)
    Call(println, [%32], ["borrow"])
    %33 = StringLiteral("Line1\nLine2", string)
    DeclareLocal("newline", string, %33)
    %34 = LoadVar("newline") -> string
    Call(println, [%34], ["borrow"])
    %35 = LoadVar("newline") -> string
    Drop(%35)
    %36 = StringLiteral("Col1\tCol2\tCol3", string)
    DeclareLocal("tab", string, %36)
    %37 = LoadVar("tab") -> string
    Call(println, [%37], ["borrow"])
    %38 = LoadVar("tab") -> string
    Drop(%38)
    %39 = StringLiteral("She said \"Hello\"", string)
    DeclareLocal("quote", string, %39)
    %40 = LoadVar("quote") -> string
    Call(println, [%40], ["borrow"])
    %41 = LoadVar("quote") -> string
    Drop(%41)
    %42 = StringLiteral("Path\\to\\file", string)
    DeclareLocal("backslash", string, %42)
    %43 = LoadVar("backslash") -> string
    Call(println, [%43], ["borrow"])
    %44 = LoadVar("backslash") -> string
    Drop(%44)
    %45 = StringLiteral("--- String Comparison ---", string)
    Call(println, [%45], ["borrow"])
    %46 = StringLiteral("apple", string)
    DeclareLocal("a", string, %46)
    %47 = StringLiteral("apple", string)
    DeclareLocal("b", string, %47)
    %48 = StringLiteral("banana", string)
    DeclareLocal("c", string, %48)
    %49 = LoadVar("a") -> string
    %50 = LoadVar("b") -> string
    %51 = BinaryOp("==", %49, %50)
    Call(println, [%51], ["borrow"])
    %52 = LoadVar("b") -> string
    Drop(%52)
    %53 = LoadVar("a") -> string
    %54 = LoadVar("c") -> string
    %55 = BinaryOp("==", %53, %54)
    Call(println, [%55], ["borrow"])
    %56 = LoadVar("a") -> string
    %57 = LoadVar("c") -> string
    %58 = BinaryOp("!=", %56, %57)
    Call(println, [%58], ["borrow"])
    %59 = LoadVar("a") -> string
    Drop(%59)
    %60 = LoadVar("c") -> string
    Drop(%60)
    %61 = StringLiteral("--- String with Numbers ---", string)
    Call(println, [%61], ["borrow"])
    %62 = StringLiteral("12345", string)
    DeclareLocal("num_str", string, %62)
    %63 = LoadVar("num_str") -> string
    Call(println, [%63], ["borrow"])
    %64 = LoadVar("num_str") -> string
    Drop(%64)
    %65 = StringLiteral("--- Unicode Characters ---", string)
    Call(println, [%65], ["borrow"])
    %66 = StringLiteral("ðŸ”¥", string)
    DeclareLocal("emoji", string, %66)
    %67 = LoadVar("emoji") -> string
    Call(println, [%67], ["borrow"])
    %68 = LoadVar("emoji") -> string
    Drop(%68)
    %69 = StringLiteral("cafÃ©", string)
    DeclareLocal("accents", string, %69)
    %70 = LoadVar("accents") -> string
    Call(println, [%70], ["borrow"])
    %71 = LoadVar("accents") -> string
    Drop(%71)
    %72 = StringLiteral("--- String in Expressions ---", string)
    Call(println, [%72], ["borrow"])
    %73 = IntLiteral(5, int32)
    DeclareLocal("count", int32, %73)
    %74 = StringLiteral("Count: ", string)
    %75 = LoadVar("count") -> int32
    %76 = Cast(%75, string)
    %77 = BinaryOp("+", %74, %76)
    DeclareLocal("result", string, %77)
    %78 = LoadVar("result") -> string
    Call(println, [%78], ["borrow"])
    %79 = LoadVar("result") -> string
    Drop(%79)
    %80 = StringLiteral("--- String Methods ---", string)
    Call(println, [%80], ["borrow"])
    %81 = StringLiteral("hello", string)
    DeclareLocal("upper_test", string, %81)
    %82 = StringLiteral("WORLD", string)
    DeclareLocal("lower_test", string, %82)
    %83 = StringLiteral("--- Long Strings ---", string)
    Call(println, [%83], ["borrow"])
    %84 = StringLiteral("This is a very long string that contains many words and characters to test how the compiler and runtime handle longer string values.", string)
    DeclareLocal("long_str", string, %84)
    %85 = LoadVar("long_str") -> string
    Call(println, [%85], ["borrow"])
    %86 = LoadVar("long_str") -> string
    Drop(%86)
    %87 = StringLiteral("--- String Variables ---", string)
    Call(println, [%87], ["borrow"])
    %88 = StringLiteral("Alice", string)
    DeclareLocal("name", string, %88)
    %89 = StringLiteral("30", string)
    DeclareLocal("age_str", string, %89)
    %90 = StringLiteral("Name: ", string)
    %91 = LoadVar("name") -> string
    %92 = BinaryOp("+", %90, %91)
    %93 = StringLiteral(", Age: ", string)
    %94 = BinaryOp("+", %92, %93)
    %95 = LoadVar("age_str") -> string
    %96 = BinaryOp("+", %94, %95)
    DeclareLocal("info", string, %96)
    %97 = LoadVar("name") -> string
    Drop(%97)
    %98 = LoadVar("age_str") -> string
    Drop(%98)
    %99 = LoadVar("info") -> string
    Call(println, [%99], ["borrow"])
    %100 = LoadVar("info") -> string
    Drop(%100)
    %101 = StringLiteral("--- Repeated Concatenation ---", string)
    Call(println, [%101], ["borrow"])
    %102 = StringLiteral("", string)
    DeclareLocal("build", string, %102)
    %103 = LoadVar("build") -> string
    %104 = StringLiteral("a", string)
    %105 = BinaryOp("+", %103, %104)
    %106 = LoadVar("build") -> string
    Drop(%106)
    StoreVar("build", %105)
    %107 = LoadVar("build") -> string
    %108 = StringLiteral("b", string)
    %109 = BinaryOp("+", %107, %108)
    %110 = LoadVar("build") -> string
    Drop(%110)
    StoreVar("build", %109)
    %111 = LoadVar("build") -> string
    %112 = StringLiteral("c", string)
    %113 = BinaryOp("+", %111, %112)
    %114 = LoadVar("build") -> string
    Drop(%114)
    StoreVar("build", %113)
    %115 = LoadVar("build") -> string
    Call(println, [%115], ["borrow"])
    %116 = LoadVar("build") -> string
    Drop(%116)
    %117 = StringLiteral("=== All string operation tests passed ===", string)
    Call(println, [%117], ["borrow"])
    %118 = LoadVar("upper_test") -> string
    Drop(%118)
    %119 = LoadVar("lower_test") -> string
    Drop(%119)
    Return()
}
