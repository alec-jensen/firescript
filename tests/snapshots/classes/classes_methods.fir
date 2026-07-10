module classes_methods

type Point owned {
  x: int32
  y: int32
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

function Point.Point(x: int32, y: int32) -> Point {
  block_0:
    %0 = Allocate(Point, [])
    DeclareLocal("this", Point, %0)
    %1 = LoadVar("x") -> int32
    %2 = LoadVar("this") -> Point
    StoreField(%2, "x", %1)
    %3 = LoadVar("y") -> int32
    %4 = LoadVar("this") -> Point
    StoreField(%4, "y", %3)
    %5 = LoadVar("this") -> Point
    Return(%5)
}

function Point.sum(this: &Point) -> int32 {
  block_0:
    %0 = LoadVar("this") -> Point
    %1 = LoadField(%0, "x")
    %2 = LoadVar("this") -> Point
    %3 = LoadField(%2, "y")
    %4 = BinaryOp("+", %1, %3)
    Return(%4)
}

function main() -> void {
  block_0:
    %0 = IntLiteral(2, int32)
    %1 = IntLiteral(3, int32)
    %2 = Call(Point.Point, [%0, %1], ["own", "own"]) -> Point
    DeclareLocal("p", Point, %2)
    %3 = LoadVar("p") -> Point
    %4 = MethodCall(%3, "sum", [], []) -> int32
    Call(println, [%4], ["borrow"])
    %5 = LoadVar("p") -> Point
    Drop(%5)
    Return()
}
