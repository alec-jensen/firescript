fir module strings_concatenation

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

function @main() -> void {
  L0:
    %0 = strconst "Hello"
    local s1: string = %0
    %1 = strconst "World"
    local s2: string = %1
    %2 = loadvar.string s1
    %3 = strconst ", "
    %4 = binop "+", %2, %3
    %5 = loadvar.string s2
    %6 = binop "+", %4, %5
    %7 = strconst "!"
    %8 = binop "+", %6, %7
    local greeting: string = %8
    %9 = loadvar.string s1
    drop %9
    %10 = loadvar.string s2
    drop %10
    %11 = loadvar.string greeting
    call @println(%11 borrow)
    %12 = loadvar.string greeting
    drop %12
    %13 = strconst "Line 1"
    %14 = strconst " "
    %15 = binop "+", %13, %14
    %16 = strconst "Line 2"
    %17 = binop "+", %15, %16
    %18 = strconst " "
    %19 = binop "+", %17, %18
    %20 = strconst "Line 3"
    %21 = binop "+", %19, %20
    local multi: string = %21
    %22 = loadvar.string multi
    call @println(%22 borrow)
    %23 = loadvar.string multi
    drop %23
    %24 = const.int32 5
    local count: int32 = %24
    %25 = strconst "Count: "
    %26 = loadvar.int32 count
    %27 = cast.string %26
    %28 = binop "+", %25, %27
    local result: string = %28
    %29 = loadvar.string result
    call @println(%29 borrow)
    %30 = loadvar.string result
    drop %30
    %31 = strconst "Alice"
    local name: string = %31
    %32 = strconst "30"
    local age_str: string = %32
    %33 = strconst "Name: "
    %34 = loadvar.string name
    %35 = binop "+", %33, %34
    %36 = strconst ", Age: "
    %37 = binop "+", %35, %36
    %38 = loadvar.string age_str
    %39 = binop "+", %37, %38
    local info: string = %39
    %40 = loadvar.string name
    drop %40
    %41 = loadvar.string age_str
    drop %41
    %42 = loadvar.string info
    call @println(%42 borrow)
    %43 = loadvar.string info
    drop %43
    %44 = strconst ""
    local build: string = %44
    %45 = loadvar.string build
    %46 = strconst "a"
    %47 = binop "+", %45, %46
    %48 = loadvar.string build
    drop %48
    storevar build, %47
    %49 = loadvar.string build
    %50 = strconst "b"
    %51 = binop "+", %49, %50
    %52 = loadvar.string build
    drop %52
    storevar build, %51
    %53 = loadvar.string build
    %54 = strconst "c"
    %55 = binop "+", %53, %54
    %56 = loadvar.string build
    drop %56
    storevar build, %55
    %57 = loadvar.string build
    call @println(%57 borrow)
    %58 = loadvar.string build
    drop %58
    ret
}
