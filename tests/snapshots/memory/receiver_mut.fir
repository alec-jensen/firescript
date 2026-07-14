fir module receiver_mut

type Counter owned {
  count: int32
}

type Pair owned {
  first: string
  second: string
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

function @Counter.Counter(start: int32) -> Counter {
  L0:
    %0 = alloc.Counter()
    local this: Counter = %0
    %1 = loadvar.int32 start
    %2 = loadvar.Counter this
    storefield %2, "count", %1
    %3 = loadvar.Counter this
    ret %3
}

function @Counter.increment(this: &mut Counter) -> void {
  L0:
    %0 = loadvar.Counter this
    %1 = loadfield.int32 %0, "count"
    %2 = const.int32 1
    %3 = binop "+", %1, %2
    %4 = loadvar.Counter this
    storefield %4, "count", %3
    ret
}

function @Counter.add(this: &mut Counter, n: int32) -> void {
  L0:
    %0 = loadvar.Counter this
    %1 = loadfield.int32 %0, "count"
    %2 = loadvar.int32 n
    %3 = binop "+", %1, %2
    %4 = loadvar.Counter this
    storefield %4, "count", %3
    ret
}

function @Counter.value(this: &Counter) -> int32 {
  L0:
    %0 = loadvar.Counter this
    %1 = loadfield.int32 %0, "count"
    ret %1
}

function @Pair.Pair(a: string, b: string) -> Pair {
  L0:
    %0 = alloc.Pair()
    local this: Pair = %0
    %1 = loadvar.string a
    %2 = loadvar.Pair this
    storefield %2, "first", %1
    %3 = loadvar.string b
    %4 = loadvar.Pair this
    storefield %4, "second", %3
    %5 = loadvar.Pair this
    ret %5
}

function @Pair.swap(this: &mut Pair) -> void {
  L0:
    %0 = loadvar.Pair this
    %1 = loadfield.string %0, "first"
    local tmp: string = %1
    %2 = loadvar.Pair this
    %3 = loadfield.string %2, "second"
    %4 = loadvar.Pair this
    storefield %4, "first", %3
    %5 = loadvar.string tmp
    %6 = loadvar.Pair this
    storefield %6, "second", %5
    ret
}

function @Pair.describe(this: &Pair) -> string {
  L0:
    %0 = loadvar.Pair this
    %1 = loadfield.string %0, "first"
    %2 = strconst ","
    %3 = binop "+", %1, %2
    %4 = loadvar.Pair this
    %5 = loadfield.string %4, "second"
    %6 = binop "+", %3, %5
    ret %6
}

function @main() -> void {
  L0:
    %0 = const.int32 0
    %1 = call.Counter @Counter.Counter(%0 own)
    local c: Counter = %1
    %2 = loadvar.Counter c
    mcall %2, "increment"()
    %3 = loadvar.Counter c
    mcall %3, "increment"()
    %4 = loadvar.Counter c
    mcall %4, "increment"()
    %5 = loadvar.Counter c
    %6 = mcall.int32 %5, "value"()
    call @println(%6 borrow)
    %7 = loadvar.Counter c
    %8 = const.int32 10
    mcall %7, "add"(%8 own)
    %9 = loadvar.Counter c
    %10 = mcall.int32 %9, "value"()
    call @println(%10 borrow)
    %11 = loadvar.Counter c
    drop %11
    %12 = strconst "hello"
    %13 = strconst "world"
    %14 = call.Pair @Pair.Pair(%12 own, %13 own)
    local p: Pair = %14
    %15 = loadvar.Pair p
    %16 = mcall.string %15, "describe"()
    call @println(%16 borrow)
    %17 = loadvar.Pair p
    mcall %17, "swap"()
    %18 = loadvar.Pair p
    %19 = mcall.string %18, "describe"()
    call @println(%19 borrow)
    %20 = loadvar.Pair p
    drop %20
    ret
}
