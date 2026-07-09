module move_semantics_test

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

function take_ownership(s: string) -> void {
  block_0:
    %0 = LoadVar("s") -> string
    Call(println, [%0], ["borrow"])
    Return()
}

function borrow_only(s: &string) -> void {
  block_0:
    %0 = LoadVar("s") -> string
    Call(println, [%0], ["borrow"])
    Return()
}

function main() -> void {
  block_0:
    %0 = StringLiteral("hello", string)
    DeclareLocal("s1", string, %0)
    %1 = LoadVar("s1") -> string
    Call(take_ownership, [%1], ["own"])
    %2 = StringLiteral("world", string)
    DeclareLocal("s2", string, %2)
    %3 = LoadVar("s2") -> string
    Call(borrow_only, [%3], ["borrow"])
    %4 = LoadVar("s2") -> string
    Call(println, [%4], ["borrow"])
    %5 = LoadVar("s2") -> string
    Drop(%5)
    %6 = StringLiteral("test", string)
    DeclareLocal("s3", string, %6)
    %7 = LoadVar("s3") -> string
    DeclareLocal("s4", string, %7)
    %8 = LoadVar("s4") -> string
    Call(println, [%8], ["borrow"])
    %9 = LoadVar("s4") -> string
    Drop(%9)
    Return()
}
