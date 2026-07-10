module receiver_mut

type Counter owned {
  count: int32
}

type Pair owned {
  first: string
  second: string
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

function Counter.Counter(start: int32) -> Counter {
  block_0:
    %0 = Allocate(Counter, [])
    DeclareLocal("this", Counter, %0)
    %1 = LoadVar("start") -> int32
    %2 = LoadVar("this") -> Counter
    StoreField(%2, "count", %1)
    %3 = LoadVar("this") -> Counter
    Return(%3)
}

function Counter.increment(this: &mut Counter) -> void {
  block_0:
    %0 = LoadVar("this") -> Counter
    %1 = LoadField(%0, "count")
    %2 = IntLiteral(1, int32)
    %3 = BinaryOp("+", %1, %2)
    %4 = LoadVar("this") -> Counter
    StoreField(%4, "count", %3)
    Return()
}

function Counter.add(this: &mut Counter, n: int32) -> void {
  block_0:
    %0 = LoadVar("this") -> Counter
    %1 = LoadField(%0, "count")
    %2 = LoadVar("n") -> int32
    %3 = BinaryOp("+", %1, %2)
    %4 = LoadVar("this") -> Counter
    StoreField(%4, "count", %3)
    Return()
}

function Counter.value(this: &Counter) -> int32 {
  block_0:
    %0 = LoadVar("this") -> Counter
    %1 = LoadField(%0, "count")
    Return(%1)
}

function Pair.Pair(a: string, b: string) -> Pair {
  block_0:
    %0 = Allocate(Pair, [])
    DeclareLocal("this", Pair, %0)
    %1 = LoadVar("a") -> string
    %2 = LoadVar("this") -> Pair
    StoreField(%2, "first", %1)
    %3 = LoadVar("b") -> string
    %4 = LoadVar("this") -> Pair
    StoreField(%4, "second", %3)
    %5 = LoadVar("this") -> Pair
    Return(%5)
}

function Pair.swap(this: &mut Pair) -> void {
  block_0:
    %0 = LoadVar("this") -> Pair
    %1 = LoadField(%0, "first")
    DeclareLocal("tmp", string, %1)
    %2 = LoadVar("this") -> Pair
    %3 = LoadField(%2, "second")
    %4 = LoadVar("this") -> Pair
    StoreField(%4, "first", %3)
    %5 = LoadVar("tmp") -> string
    %6 = LoadVar("this") -> Pair
    StoreField(%6, "second", %5)
    Return()
}

function Pair.describe(this: &Pair) -> string {
  block_0:
    %0 = LoadVar("this") -> Pair
    %1 = LoadField(%0, "first")
    %2 = StringLiteral(",", string)
    %3 = BinaryOp("+", %1, %2)
    %4 = LoadVar("this") -> Pair
    %5 = LoadField(%4, "second")
    %6 = BinaryOp("+", %3, %5)
    Return(%6)
}

function main() -> void {
  block_0:
    %0 = IntLiteral(0, int32)
    %1 = Call(Counter.Counter, [%0], ["own"]) -> Counter
    DeclareLocal("c", Counter, %1)
    %2 = LoadVar("c") -> Counter
    MethodCall(%2, "increment", [], [])
    %3 = LoadVar("c") -> Counter
    MethodCall(%3, "increment", [], [])
    %4 = LoadVar("c") -> Counter
    MethodCall(%4, "increment", [], [])
    %5 = LoadVar("c") -> Counter
    %6 = MethodCall(%5, "value", [], []) -> int32
    Call(println, [%6], ["borrow"])
    %7 = LoadVar("c") -> Counter
    %8 = IntLiteral(10, int32)
    MethodCall(%7, "add", [%8], ["own"])
    %9 = LoadVar("c") -> Counter
    %10 = MethodCall(%9, "value", [], []) -> int32
    Call(println, [%10], ["borrow"])
    %11 = LoadVar("c") -> Counter
    Drop(%11)
    %12 = StringLiteral("hello", string)
    %13 = StringLiteral("world", string)
    %14 = Call(Pair.Pair, [%12, %13], ["own", "own"]) -> Pair
    DeclareLocal("p", Pair, %14)
    %15 = LoadVar("p") -> Pair
    %16 = MethodCall(%15, "describe", [], []) -> string
    Call(println, [%16], ["borrow"])
    %17 = LoadVar("p") -> Pair
    MethodCall(%17, "swap", [], [])
    %18 = LoadVar("p") -> Pair
    %19 = MethodCall(%18, "describe", [], []) -> string
    Call(println, [%19], ["borrow"])
    %20 = LoadVar("p") -> Pair
    Drop(%20)
    Return()
}
