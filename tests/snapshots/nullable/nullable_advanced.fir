fir module nullable_advanced

type Config owned {
  host: string
  port: string
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

function @Config.Config(host: string, port: string) -> Config {
  L0:
    %0 = alloc.Config()
    local this: Config = %0
    %1 = loadvar.string host
    %2 = loadvar.Config this
    storefield %2, "host", %1
    %3 = loadvar.string port
    %4 = loadvar.Config this
    storefield %4, "port", %3
    %5 = loadvar.Config this
    ret %5
}

function @Config.address(this: &Config) -> string {
  L0:
    %0 = loadvar.Config this
    %1 = loadfield.string %0, "port"
    %2 = nullconst string?
    %3 = binop "!=", %1, %2
    br %3, L2, L1

  L1:
    %4 = loadvar.Config this
    %5 = loadfield.string %4, "host"
    ret %5

  L2:
    %6 = loadvar.Config this
    %7 = loadfield.string %6, "host"
    %8 = strconst ":"
    %9 = binop "+", %7, %8
    %10 = loadvar.Config this
    %11 = loadfield.string %10, "port"
    %12 = binop "+", %9, %11
    ret %12
}

function @main() -> void {
  L0:
    %0 = strconst "localhost"
    %1 = strconst "8080"
    %2 = call.Config @Config.Config(%0 own, %1 own)
    local c1: Config = %2
    %3 = strconst "example.com"
    %4 = strconst "1111"
    %5 = call.Config @Config.Config(%3 own, %4 own)
    local c2: Config = %5
    %6 = loadvar.Config c1
    %7 = mcall.string %6, "address"()
    call @println(%7 borrow)
    %8 = loadvar.Config c1
    drop %8
    %9 = loadvar.Config c2
    %10 = mcall.string %9, "address"()
    call @println(%10 borrow)
    %11 = loadvar.Config c2
    drop %11
    %12 = strconst "first"
    local a: string? = %12
    %13 = nullconst string?
    local b: string? = %13
    %14 = strconst "third"
    local c: string? = %14
    %15 = const.int32 0
    local count: int32 = %15
    %16 = loadvar.string? a
    %17 = nullconst string?
    %18 = binop "!=", %16, %17
    br %18, L2, L1

  L1:
    %19 = loadvar.string? a
    drop %19
    %20 = loadvar.string? b
    %21 = nullconst string?
    %22 = binop "!=", %20, %21
    br %22, L4, L3

  L2:
    %23 = loadvar.int32 count
    %24 = const.int32 1
    %25 = binop "+", %23, %24
    storevar count, %25
    jmp L1

  L3:
    %26 = loadvar.string? b
    drop %26
    %27 = loadvar.string? c
    %28 = nullconst string?
    %29 = binop "!=", %27, %28
    br %29, L6, L5

  L4:
    %30 = loadvar.int32 count
    %31 = const.int32 1
    %32 = binop "+", %30, %31
    storevar count, %32
    jmp L3

  L5:
    %33 = loadvar.string? c
    drop %33
    %34 = loadvar.int32 count
    call @println(%34 borrow)
    %35 = nullconst string?
    local val: string? = %35
    %36 = loadvar.string? val
    %37 = nullconst string?
    %38 = binop "==", %36, %37
    call @println(%38 borrow)
    %39 = strconst "assigned"
    %40 = loadvar.string? val
    drop %40
    storevar val, %39
    %41 = loadvar.string? val
    %42 = nullconst string?
    %43 = binop "!=", %41, %42
    call @println(%43 borrow)
    %44 = loadvar.string? val
    drop %44
    ret

  L6:
    %45 = loadvar.int32 count
    %46 = const.int32 1
    %47 = binop "+", %45, %46
    storevar count, %47
    jmp L5
}
