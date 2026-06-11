module nullable_advanced

type Config owned {
  host: string
  port: string
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

function Config.Config(host: string, port: string) -> Config {
  block_0:
    %0 = Allocate(Config, [])
    DeclareLocal("this", Config, %0)
    %1 = LoadVar("host") -> string
    %2 = LoadVar("this") -> Config
    StoreField(%2, "host", %1)
    %3 = LoadVar("port") -> string
    %4 = LoadVar("this") -> Config
    StoreField(%4, "port", %3)
    %5 = LoadVar("this") -> Config
    Return(%5)
}

function Config.address(this: &Config) -> string {
  block_0:
    %0 = LoadVar("this") -> Config
    %1 = LoadField(%0, "port")
    %2 = NullLiteral(string?)
    %3 = BinaryOp("!=", %1, %2)
    Branch(%3, block_2, block_1)

  block_1:
    %4 = LoadVar("this") -> Config
    %5 = LoadField(%4, "host")
    Return(%5)

  block_2:
    %6 = LoadVar("this") -> Config
    %7 = LoadField(%6, "host")
    %8 = StringLiteral(":", string)
    %9 = BinaryOp("+", %7, %8)
    %10 = LoadVar("this") -> Config
    %11 = LoadField(%10, "port")
    %12 = BinaryOp("+", %9, %11)
    Return(%12)
}

function main() -> void {
  block_0:
    %0 = StringLiteral("localhost", string)
    %1 = StringLiteral("8080", string)
    %2 = Call(Config.Config, [%0, %1], ["own", "own"]) -> Config
    DeclareLocal("c1", Config, %2)
    %3 = StringLiteral("example.com", string)
    %4 = StringLiteral("1111", string)
    %5 = Call(Config.Config, [%3, %4], ["own", "own"]) -> Config
    DeclareLocal("c2", Config, %5)
    %6 = LoadVar("c1") -> Config
    %7 = MethodCall(%6, "address", [], []) -> string
    Call(println, [%7], ["borrow"])
    %8 = LoadVar("c1") -> Config
    Drop(%8)
    %9 = LoadVar("c2") -> Config
    %10 = MethodCall(%9, "address", [], []) -> string
    Call(println, [%10], ["borrow"])
    %11 = LoadVar("c2") -> Config
    Drop(%11)
    %12 = StringLiteral("first", string)
    DeclareLocal("a", string?, %12)
    %13 = NullLiteral(string?)
    DeclareLocal("b", string?, %13)
    %14 = StringLiteral("third", string)
    DeclareLocal("c", string?, %14)
    %15 = IntLiteral(0, int32)
    DeclareLocal("count", int32, %15)
    %16 = LoadVar("a") -> string
    %17 = NullLiteral(string?)
    %18 = BinaryOp("!=", %16, %17)
    Branch(%18, block_2, block_1)

  block_1:
    %19 = LoadVar("a") -> string
    Drop(%19)
    %20 = LoadVar("b") -> string
    %21 = NullLiteral(string?)
    %22 = BinaryOp("!=", %20, %21)
    Branch(%22, block_4, block_3)

  block_2:
    %23 = LoadVar("count") -> int32
    %24 = IntLiteral(1, int32)
    %25 = BinaryOp("+", %23, %24)
    StoreVar("count", %25)
    Jump(block_1)

  block_3:
    %26 = LoadVar("b") -> string
    Drop(%26)
    %27 = LoadVar("c") -> string
    %28 = NullLiteral(string?)
    %29 = BinaryOp("!=", %27, %28)
    Branch(%29, block_6, block_5)

  block_4:
    %30 = LoadVar("count") -> int32
    %31 = IntLiteral(1, int32)
    %32 = BinaryOp("+", %30, %31)
    StoreVar("count", %32)
    Jump(block_3)

  block_5:
    %33 = LoadVar("c") -> string
    Drop(%33)
    %34 = LoadVar("count") -> int32
    Call(println, [%34], ["borrow"])
    %35 = NullLiteral(string?)
    DeclareLocal("val", string?, %35)
    %36 = LoadVar("val") -> string
    %37 = NullLiteral(string?)
    %38 = BinaryOp("==", %36, %37)
    Call(println, [%38], ["borrow"])
    %39 = LoadVar("val") -> string
    Drop(%39)
    %40 = StringLiteral("assigned", string)
    StoreVar("val", %40)
    %41 = LoadVar("val") -> string
    %42 = NullLiteral(string?)
    %43 = BinaryOp("!=", %41, %42)
    Call(println, [%43], ["borrow"])
    %44 = LoadVar("val") -> string
    Drop(%44)
    Return()

  block_6:
    %45 = LoadVar("count") -> int32
    %46 = IntLiteral(1, int32)
    %47 = BinaryOp("+", %45, %46)
    StoreVar("count", %47)
    Jump(block_5)
}
