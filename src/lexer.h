#ifndef LEXER_H
#define LEXER_H

#include <vector>
#include <string>

class lexer
{
public:
    lexer();
    std::vector<std::string> lex(std::string source);
};

#endif