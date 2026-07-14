fir module classes_methods

type Point owned {
  x: int32
  y: int32
}

function<T> @print(value: &T) -> void {
  L0:
    %0 = loadvar.T value
    %1 = cast.string %0
    local text: string = %1
    %2 = loadvar.string text
    call @stdout(%2 borrow)
    %3 = loadvar.string text
    drop %3
    ret
}

function<T> @println(value: &T) -> void {
  L0:
    %0 = loadvar.T value
    %1 = cast.string %0
    local cast_text: string = %1
    %2 = loadvar.string cast_text
    %3 = strconst "\n"
    %4 = binop "+", %2, %3
    local text: string = %4
    %5 = loadvar.string cast_text
    drop %5
    %6 = loadvar.string text
    call @stdout(%6 borrow)
    %7 = loadvar.string text
    drop %7
    ret
}

function @Point.Point(x: int32, y: int32) -> Point {
  L0:
    %0 = alloc.Point()
    local this: Point = %0
    %1 = loadvar.int32 x
    %2 = loadvar.Point this
    storefield %2, "x", %1
    %3 = loadvar.int32 y
    %4 = loadvar.Point this
    storefield %4, "y", %3
    %5 = loadvar.Point this
    ret %5
}

function @Point.sum(this: &Point) -> int32 {
  L0:
    %0 = loadvar.Point this
    %1 = loadfield.int32 %0, "x"
    %2 = loadvar.Point this
    %3 = loadfield.int32 %2, "y"
    %4 = binop "+", %1, %3
    ret %4
}

function @main() -> void {
  L0:
    %0 = const.int32 2
    %1 = const.int32 3
    %2 = call.Point @Point.Point(%0 own, %1 own)
    local p: Point = %2
    %3 = loadvar.Point p
    %4 = mcall.int32 %3, "sum"()
    call @println(%4 borrow)
    %5 = loadvar.Point p
    drop %5
    ret
}
