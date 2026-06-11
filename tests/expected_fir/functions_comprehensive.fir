module functions_comprehensive

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

function greet() -> void {
  block_0:
    %0 = StringLiteral("Hello from function!", string)
    Call(println, [%0], ["borrow"])
    Return()
}

function getConstant() -> int32 {
  block_0:
    %0 = IntLiteral(42, int32)
    Return(%0)
}

function double(x: int32) -> int32 {
  block_0:
    %0 = LoadVar("x") -> int32
    %1 = IntLiteral(2, int32)
    %2 = BinaryOp("*", %0, %1)
    Return(%2)
}

function add(a: int32, b: int32) -> int32 {
  block_0:
    %0 = LoadVar("a") -> int32
    %1 = LoadVar("b") -> int32
    %2 = BinaryOp("+", %0, %1)
    Return(%2)
}

function multiply(x: int32, y: int32) -> int32 {
  block_0:
    %0 = LoadVar("x") -> int32
    %1 = LoadVar("y") -> int32
    %2 = BinaryOp("*", %0, %1)
    Return(%2)
}

function addThenDouble(a: int32, b: int32) -> int32 {
  block_0:
    %0 = LoadVar("a") -> int32
    %1 = LoadVar("b") -> int32
    %2 = Call(add, [%0, %1], ["own", "own"]) -> int32
    DeclareLocal("sum", int32, %2)
    %3 = LoadVar("sum") -> int32
    %4 = Call(double, [%3], ["own"]) -> int32
    Return(%4)
}

function factorial(n: int32) -> int32 {
  block_0:
    %0 = LoadVar("n") -> int32
    %1 = IntLiteral(1, int32)
    %2 = BinaryOp("<=", %0, %1)
    Branch(%2, block_2, block_1)

  block_1:
    %3 = LoadVar("n") -> int32
    %4 = LoadVar("n") -> int32
    %5 = IntLiteral(1, int32)
    %6 = BinaryOp("-", %4, %5)
    %7 = Call(factorial, [%6], ["own"]) -> int32
    %8 = BinaryOp("*", %3, %7)
    Return(%8)

  block_2:
    %9 = IntLiteral(1, int32)
    Return(%9)
}

function divide(a: float32, b: float32) -> float32 {
  block_0:
    %0 = LoadVar("a") -> float32
    %1 = LoadVar("b") -> float32
    %2 = BinaryOp("/", %0, %1)
    Return(%2)
}

function isEven(n: int32) -> bool {
  block_0:
    %0 = LoadVar("n") -> int32
    %1 = IntLiteral(2, int32)
    %2 = BinaryOp("%", %0, %1)
    %3 = IntLiteral(0, int32)
    %4 = BinaryOp("==", %2, %3)
    Return(%4)
}

function makeGreeting(name: string) -> string {
  block_0:
    %0 = StringLiteral("Hello, ", string)
    %1 = LoadVar("name") -> string
    %2 = BinaryOp("+", %0, %1)
    %3 = StringLiteral("!", string)
    %4 = BinaryOp("+", %2, %3)
    Return(%4)
}

function getFirst(arr: int32[]) -> int32 {
  block_0:
    %0 = LoadVar("arr") -> int32[]
    %1 = IntLiteral(0, int32)
    %2 = IndexArray(%0, %1)
    Return(%2)
}

function arraySum(values: int32[]) -> int32 {
  block_0:
    %0 = IntLiteral(0, int32)
    DeclareLocal("total", int32, %0)
    %1 = LoadVar("values") -> int32[]
    DeclareLocal("__arr_v", int32[], %1)
    %2 = IntLiteral(0, int32)
    DeclareLocal("__i_v", int32, %2)
    Jump(block_1)

  block_1:
    %3 = LoadVar("__i_v") -> int32
    %4 = LoadVar("__arr_v") -> int32[]
    %5 = Call(array_length, [%4], ["borrow"]) -> int32
    %6 = BinaryOp("<", %3, %5)
    Branch(%6, block_2, block_3)

  block_2:
    %7 = LoadVar("__arr_v") -> int32[]
    %8 = LoadVar("__i_v") -> int32
    %9 = IndexArray(%7, %8)
    DeclareLocal("v", int32, %9)
    %10 = LoadVar("total") -> int32
    %11 = LoadVar("v") -> int32
    %12 = BinaryOp("+", %10, %11)
    StoreVar("total", %12)
    Jump(block_4)

  block_3:
    %13 = LoadVar("total") -> int32
    Return(%13)

  block_4:
    %14 = LoadVar("__i_v") -> int32
    %15 = IntLiteral(1, int32)
    %16 = BinaryOp("+", %14, %15)
    StoreVar("__i_v", %16)
    Jump(block_1)
}

function findPositive(x: int32) -> int32 {
  block_0:
    %0 = LoadVar("x") -> int32
    %1 = IntLiteral(0, int32)
    %2 = BinaryOp(">", %0, %1)
    Branch(%2, block_2, block_1)

  block_1:
    %3 = IntLiteral(0, int32)
    Return(%3)

  block_2:
    %4 = LoadVar("x") -> int32
    Return(%4)
}

function classify(n: int32) -> string {
  block_0:
    %0 = LoadVar("n") -> int32
    %1 = IntLiteral(0, int32)
    %2 = BinaryOp("<", %0, %1)
    Branch(%2, block_2, block_3)

  block_1:
    Return()

  block_2:
    %3 = StringLiteral("negative", string)
    Return(%3)

  block_3:
    %4 = LoadVar("n") -> int32
    %5 = IntLiteral(0, int32)
    %6 = BinaryOp("==", %4, %5)
    Branch(%6, block_5, block_6)

  block_4:
    Jump(block_1)

  block_5:
    %7 = StringLiteral("zero", string)
    Return(%7)

  block_6:
    %8 = StringLiteral("positive", string)
    Return(%8)
}

function printTwice(msg: string) -> void {
  block_0:
    %0 = LoadVar("msg") -> string
    Call(println, [%0], ["borrow"])
    %1 = LoadVar("msg") -> string
    Call(println, [%1], ["borrow"])
    Return()
}

function complexCalc(a: int32, b: int32, c: int32) -> int32 {
  block_0:
    %0 = LoadVar("a") -> int32
    %1 = LoadVar("b") -> int32
    %2 = BinaryOp("+", %0, %1)
    DeclareLocal("temp", int32, %2)
    %3 = LoadVar("temp") -> int32
    %4 = LoadVar("c") -> int32
    %5 = BinaryOp("*", %3, %4)
    StoreVar("temp", %5)
    %6 = LoadVar("temp") -> int32
    %7 = IntLiteral(100, int32)
    %8 = BinaryOp(">", %6, %7)
    Branch(%8, block_2, block_1)

  block_1:
    %9 = LoadVar("temp") -> int32
    Return(%9)

  block_2:
    %10 = LoadVar("temp") -> int32
    %11 = IntLiteral(2, int32)
    %12 = BinaryOp("/", %10, %11)
    Return(%12)
}

function main() -> void {
  block_0:
    %0 = StringLiteral("=== Function Tests ===", string)
    Call(println, [%0], ["borrow"])
    %1 = StringLiteral("--- No Parameters ---", string)
    Call(println, [%1], ["borrow"])
    Call(greet, [], [])
    %2 = StringLiteral("--- Return Value, No Parameters ---", string)
    Call(println, [%2], ["borrow"])
    %3 = Call(getConstant, [], []) -> int32
    Call(println, [%3], ["borrow"])
    %4 = StringLiteral("--- Single Parameter ---", string)
    Call(println, [%4], ["borrow"])
    %5 = IntLiteral(5, int32)
    %6 = Call(double, [%5], ["own"]) -> int32
    Call(println, [%6], ["borrow"])
    %7 = IntLiteral(10, int32)
    %8 = Call(double, [%7], ["own"]) -> int32
    Call(println, [%8], ["borrow"])
    %9 = StringLiteral("--- Multiple Parameters ---", string)
    Call(println, [%9], ["borrow"])
    %10 = IntLiteral(3, int32)
    %11 = IntLiteral(7, int32)
    %12 = Call(add, [%10, %11], ["own", "own"]) -> int32
    Call(println, [%12], ["borrow"])
    %13 = IntLiteral(100, int32)
    %14 = IntLiteral(200, int32)
    %15 = Call(add, [%13, %14], ["own", "own"]) -> int32
    Call(println, [%15], ["borrow"])
    %16 = IntLiteral(4, int32)
    %17 = IntLiteral(5, int32)
    %18 = Call(multiply, [%16, %17], ["own", "own"]) -> int32
    Call(println, [%18], ["borrow"])
    %19 = StringLiteral("--- Function Calling Function ---", string)
    Call(println, [%19], ["borrow"])
    %20 = IntLiteral(2, int32)
    %21 = IntLiteral(3, int32)
    %22 = Call(addThenDouble, [%20, %21], ["own", "own"]) -> int32
    Call(println, [%22], ["borrow"])
    %23 = StringLiteral("--- Recursion ---", string)
    Call(println, [%23], ["borrow"])
    %24 = IntLiteral(5, int32)
    %25 = Call(factorial, [%24], ["own"]) -> int32
    Call(println, [%25], ["borrow"])
    %26 = IntLiteral(3, int32)
    %27 = Call(factorial, [%26], ["own"]) -> int32
    Call(println, [%27], ["borrow"])
    %28 = StringLiteral("--- Different Return Types ---", string)
    Call(println, [%28], ["borrow"])
    %29 = FloatLiteral(10.0, float32)
    %30 = FloatLiteral(4.0, float32)
    %31 = Call(divide, [%29, %30], ["own", "own"]) -> float32
    Call(println, [%31], ["borrow"])
    %32 = IntLiteral(4, int32)
    %33 = Call(isEven, [%32], ["own"]) -> bool
    Call(println, [%33], ["borrow"])
    %34 = IntLiteral(7, int32)
    %35 = Call(isEven, [%34], ["own"]) -> bool
    Call(println, [%35], ["borrow"])
    %36 = StringLiteral("Alice", string)
    %37 = Call(makeGreeting, [%36], ["own"]) -> string
    Call(println, [%37], ["borrow"])
    %38 = StringLiteral("--- Array Parameters ---", string)
    Call(println, [%38], ["borrow"])
    %39 = IntLiteral(99, int32)
    %40 = IntLiteral(88, int32)
    %41 = IntLiteral(77, int32)
    %42 = ArrayLiteral([%39, %40, %41], int32[3])
    DeclareLocal("nums", int32[3], %42)
    %43 = LoadVar("nums") -> int32[3]
    %44 = Call(getFirst, [%43], ["own"]) -> int32
    Call(println, [%44], ["borrow"])
    %45 = IntLiteral(1, int32)
    %46 = IntLiteral(2, int32)
    %47 = IntLiteral(3, int32)
    %48 = IntLiteral(4, int32)
    %49 = IntLiteral(5, int32)
    %50 = ArrayLiteral([%45, %46, %47, %48, %49], int32[5])
    DeclareLocal("to_sum", int32[5], %50)
    %51 = LoadVar("to_sum") -> int32[5]
    %52 = Call(arraySum, [%51], ["own"]) -> int32
    Call(println, [%52], ["borrow"])
    %53 = StringLiteral("--- Early Return ---", string)
    Call(println, [%53], ["borrow"])
    %54 = IntLiteral(42, int32)
    %55 = Call(findPositive, [%54], ["own"]) -> int32
    Call(println, [%55], ["borrow"])
    %56 = IntLiteral(5, int32)
    %57 = UnaryOp("-", %56)
    %58 = Call(findPositive, [%57], ["own"]) -> int32
    Call(println, [%58], ["borrow"])
    %59 = StringLiteral("--- Multiple Returns ---", string)
    Call(println, [%59], ["borrow"])
    %60 = IntLiteral(3, int32)
    %61 = UnaryOp("-", %60)
    %62 = Call(classify, [%61], ["own"]) -> string
    Call(println, [%62], ["borrow"])
    %63 = IntLiteral(0, int32)
    %64 = Call(classify, [%63], ["own"]) -> string
    Call(println, [%64], ["borrow"])
    %65 = IntLiteral(5, int32)
    %66 = Call(classify, [%65], ["own"]) -> string
    Call(println, [%66], ["borrow"])
    %67 = StringLiteral("--- Void Functions ---", string)
    Call(println, [%67], ["borrow"])
    %68 = StringLiteral("repeat", string)
    Call(printTwice, [%68], ["own"])
    %69 = StringLiteral("--- Complex Function ---", string)
    Call(println, [%69], ["borrow"])
    %70 = IntLiteral(10, int32)
    %71 = IntLiteral(20, int32)
    %72 = IntLiteral(5, int32)
    %73 = Call(complexCalc, [%70, %71, %72], ["own", "own", "own"]) -> int32
    Call(println, [%73], ["borrow"])
    %74 = IntLiteral(2, int32)
    %75 = IntLiteral(3, int32)
    %76 = IntLiteral(4, int32)
    %77 = Call(complexCalc, [%74, %75, %76], ["own", "own", "own"]) -> int32
    Call(println, [%77], ["borrow"])
    %78 = StringLiteral("=== All function tests passed ===", string)
    Call(println, [%78], ["borrow"])
    Return()
}
