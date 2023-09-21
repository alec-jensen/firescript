add_library(lexer STATIC lexer.cpp)

add_executable(firescript main.cpp)

target_link_libraries(firescript lexer)