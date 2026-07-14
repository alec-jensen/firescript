fir module move_semantics_test

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

function @take_ownership(s: string) -> void {
  L0:
    %0 = loadvar.string s
    call @println(%0 borrow)
    %1 = loadvar.string s
    drop %1
    ret
}

function @borrow_only(s: &string) -> void {
  L0:
    %0 = loadvar.string s
    call @println(%0 borrow)
    ret
}

function @main() -> void {
  L0:
    %0 = strconst "hello"
    local s1: string = %0
    %1 = loadvar.string s1
    call @take_ownership(%1 own)
    %2 = strconst "world"
    local s2: string = %2
    %3 = loadvar.string s2
    call @borrow_only(%3 borrow)
    %4 = loadvar.string s2
    call @println(%4 borrow)
    %5 = loadvar.string s2
    drop %5
    %6 = strconst "test"
    local s3: string = %6
    %7 = loadvar.string s3
    local s4: string = %7
    %8 = loadvar.string s4
    call @println(%8 borrow)
    %9 = loadvar.string s4
    drop %9
    ret
}
