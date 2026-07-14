fir module string_escape_edge_cases

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
    %0 = strconst "it\'s here"
    local s1: string = %0
    %1 = loadvar.string s1
    call @println(%1 borrow)
    %2 = loadvar.string s1
    drop %2
    %3 = strconst "a\qb"
    local s2: string = %3
    %4 = loadvar.string s2
    call @println(%4 borrow)
    %5 = loadvar.string s2
    drop %5
    ret
}
