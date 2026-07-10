module generics_class_basic

type Pair<T, U> copyable {
  first: T
  second: U
}

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

function<T, U> Pair.Pair(first: T, second: U) -> Pair {
  block_0:
    %0 = Allocate(Pair, [])
    DeclareLocal("this", Pair, %0)
    %1 = LoadVar("first") -> T
    %2 = LoadVar("this") -> Pair
    StoreField(%2, "first", %1)
    %3 = LoadVar("second") -> U
    %4 = LoadVar("this") -> Pair
    StoreField(%4, "second", %3)
    %5 = LoadVar("this") -> Pair
    Return(%5)
}

function main() -> void {
  block_0:
    %0 = IntLiteral(10, int32)
    %1 = IntLiteral(20, int32)
    %2 = Call(Pair.Pair, [%0, %1], ["own", "own"]) -> Pair<int32, int32>
    DeclareLocal("p1", Pair<int32, int32>, %2)
    %3 = IntLiteral(42, int32)
    %4 = StringLiteral("hello", string)
    %5 = Call(Pair.Pair, [%3, %4], ["own", "own"]) -> Pair<int32, string>
    DeclareLocal("p2", Pair<int32, string>, %5)
    %6 = LoadVar("p1") -> Pair<int32, int32>
    %7 = LoadField(%6, "first")
    Call(println, [%7], ["borrow"])
    %8 = LoadVar("p1") -> Pair<int32, int32>
    %9 = LoadField(%8, "second")
    Call(println, [%9], ["borrow"])
    %10 = LoadVar("p2") -> Pair<int32, string>
    %11 = LoadField(%10, "first")
    Call(println, [%11], ["borrow"])
    %12 = LoadVar("p2") -> Pair<int32, string>
    %13 = LoadField(%12, "second")
    Call(println, [%13], ["borrow"])
    Return()
}
