module classes_methods

type Point owned {
  x: int32
  y: int32
}

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
