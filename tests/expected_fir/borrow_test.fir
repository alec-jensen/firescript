module borrow_test

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

function getX(p: &Point) -> int32 {
  block_0:
    %0 = LoadVar("p") -> Point
    %1 = LoadField(%0, "x")
    Return(%1)
}

function consumePoint(p: Point) -> void {
  block_0:
    %0 = LoadVar("p") -> Point
    %1 = LoadField(%0, "x")
    Call(println, [%1], ["borrow"])
    Return()
}

function main() -> void {
  block_0:
    %0 = IntLiteral(10, int32)
    %1 = IntLiteral(20, int32)
    %2 = Allocate(Point, [%0, %1])
    DeclareLocal("p1", Point, %2)
    %3 = LoadVar("p1") -> Point
    %4 = Call(getX, [%3], ["borrow"]) -> int32
    DeclareLocal("x", int32, %4)
    %5 = LoadVar("x") -> int32
    Call(println, [%5], ["borrow"])
    %6 = LoadVar("p1") -> Point
    %7 = LoadField(%6, "y")
    Call(println, [%7], ["borrow"])
    %8 = LoadVar("p1") -> Point
    Call(consumePoint, [%8], ["own"])
    Return()
}
