#include <iostream>
#include <vector>
#include <regex>

#include "lexer.h"

using std::string;
using std::vector;

string identifier = "[a-zA-Z_][a-zA-Z0-9_]*";

vector<string> keywords = {
    "int",
    "float",
    "double",
    "bool",
    "string",
    "tuple",
    "if",
    "else",
    "elif",
    "while",
    "for",
    "break",
    "continue",
    "return",
    "nullable",
    "const"};

vector<string> seperators = {
    "(",
    ")",
    "{",
    "}",
    "[",
    "]",
    ",",
    ";",
    ":",
};

vector<string> operators = {
    "+",
    "+=",
    "++",
    "-",
    "-=",
    "--",
    "*",
    "*=",
    "/",
    "/=",
    "%",
    "%=",
    "**",
    "**=",
    "=",
    "==",
    "!=",
    ">",
    ">=",
    "<",
    "<=",
    "&&",
    "||",
    "!",
};

// Regex for literals
vector<string> literals = {
    "true",
    "false",
    "null",
    "(-?)[0-9]+",        //        Integer
    "(-?)[0-9]+.[0-9]+", // Double
    "f\".*\"",           //           Formatted String
    "\".*\"",            //            String
    "\\((.*?,.*?)\\)",   //     Tuple
};

// Regex for comments
vector<string> comments = {
    "\\/\\/.*", // //
    "\\/\\*",   // /*
    "\\*\\/"    // */
};

Lexer::Lexer(string input)
{
    this->input = input;
    this->index = 0;
    this->tokens = {};
}

vector<Token> Lexer::lex()
{
    while (this->index < this->input.length())
    {
        // Precedence: comments, keywords, seperators, operators, literals, identifiers

        // Comments
        for (string comment : comments)
        {
            std::regex regex(comment);
            std::smatch match;

            if (std::regex_search(this->input, match, regex))
            {
                Token token;
                token.type = "comment";
                token.value = match.str(0);
                this->tokens.push_back(token);

                this->input = match.suffix().str();
                this->index = 0;
            }
        }
    }

    return this->tokens;
}