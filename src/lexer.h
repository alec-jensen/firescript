#ifndef LEXER_H
#define LEXER_H

#include <vector>
#include <string>

#include "logger.h"

using std::string;
using std::vector;

struct Token
{
    string type; // "identifier", "keyword", "seperator", "operator", "literal", "comment"
    string value;
};

class Lexer
{
public:
    string input;
    string working_input;
    int index;
    vector<Token> tokens;
    Logger *logger;

    Lexer(string input, Logger *logger);

    vector<Token> lex();
};

#endif