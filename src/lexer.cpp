#include <iostream>
#include <vector>
#include <regex>

#include "logger.h"
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

Lexer::Lexer(string input, Logger *logger)
{
    this->input = input;
    this->index = 0;
    this->tokens = {};
    this->logger = logger;
}

vector<Token> Lexer::lex()
{
    this->logger->debug("Lexing file");
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
                this->logger->debug("Found comment: " + match.str());
                this->tokens.push_back(Token{"comment", match.str()});
                this->input = match.suffix();
                this->index = 0;
                break;
            }
        }

        this->index++;
    }

    return this->tokens;
}