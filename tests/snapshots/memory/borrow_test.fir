module borrow_test

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
    %2 = LoadVar("p") -> Point
    Drop(%2)
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
