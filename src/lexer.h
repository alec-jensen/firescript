#ifndef LEXER_H
#define LEXER_H

#include <vector>
#include <string>

struct Token
{
    string type; // "identifier", "keyword", "seperator", "operator", "literal", "comment"
    string value;
};

class Lexer
{
public:
    string input;
    int index;
    vector<Token> tokens;

    Lexer(string input);

    vector<Token> lex();
};

#endif