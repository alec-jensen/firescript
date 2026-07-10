module types_int64

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

function main() -> void {
  block_0:
    %0 = IntLiteral(9223372036854775807, int64)
    DeclareLocal("i64_test", int64, %0)
    %1 = IntLiteral(9223372036854775808, int64)
    %2 = UnaryOp("-", %1)
    DeclareLocal("i64_negative", int64, %2)
    %3 = LoadVar("i64_test") -> int64
    Call(println, [%3], ["borrow"])
    %4 = LoadVar("i64_negative") -> int64
    Call(println, [%4], ["borrow"])
    %5 = LoadVar("i64_test") -> int64
    %6 = IntLiteral(1000, int64)
    %7 = BinaryOp("/", %5, %6)
    Call(println, [%7], ["borrow"])
    Return()
}
