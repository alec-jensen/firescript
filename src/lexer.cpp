#include <iostream>
#include <vector>
#include <regex>
#include <map>

#include "logger.h"
#include "lexer.h"

using std::string;
using std::vector;
using std::map;

string identifier = "[a-zA-Z_][a-zA-Z0-9_]*";

map<string, string> keywords = {
    {"INT", "int"},
    {"FLOAT", "float"},
    {"DOUBLE", "double"},
    {"BOOL", "bool"},
    {"STRING", "string"},
    {"TUPLE", "tuple"},
    {"IF", "if"},
    {"ELSE", "else"},
    {"ELIF", "elif"},
    {"WHILE", "while"},
    {"FOR", "for"},
    {"BREAK", "break"},
    {"CONTINUE", "continue"},
    {"RETURN", "return"},
    {"NULLABLE", "nullable"},
    {"CONST", "const"},
};

map<string, string> seperators = {
    {"OPEN_PAREN", "("},
    {"CLOSE_PAREN", ")"},
    {"OPEN_BRACE", "{"},
    {"CLOSE_BRACE", "}"},
    {"OPEN_BRACKET", "["},
    {"CLOSE_BRACKET", "]"},
    {"COMMA", ","},
    {"SEMICOLON", ";"},
    {"COLON", ":"},
};

map<string, string> operators = {
    {"ADD", "\\+"},
    {"ADD_ASSIGN", "\\+="},
    {"INCREMENT", "\\+\\+"},
    {"SUBTRACT", "\\-"},
    {"SUBTRACT_ASSIGN", "\\-="},
    {"DECREMENT", "\\-\\-"},
    {"MULTIPLY", "\\*"},
    {"MULTIPLY_ASSIGN", "\\*="},
    {"DIVIDE", "\\/"},
    {"DIVIDE_ASSIGN", "\\/="},
    {"MODULO", "\\%"},
    {"MODULO_ASSIGN", "\\%="},
    {"POWER", "\\*\\*"},
    {"POWER_ASSIGN", "\\*\\*="},
    {"ASSIGN", "\\="},
    {"EQUALS", "\\=\\="},
    {"NOT_EQUALS", "\\!\\="},
    {"GREATER_THAN", "\\>"},
    {"GREATER_THAN_OR_EQUAL", "\\>\\="},
    {"LESS_THAN", "\\<"},
    {"LESS_THAN_OR_EQUAL", "\\<\\="},
    {"AND", "\\&\\&"},
    {"OR", "\\|\\|"},
    {"NOT", "\\!"},
};

map<string, string> literals = {
    {"BOOLEAN", "true|false"},
    {"NULL", "null"},
    {"INTEGER", "(-?)[0-9]+"},
    {"DOUBLE", "(-?)[0-9]+.[0-9]+"},
    {"FORMATTED_STRING", "f\".*\""},
    {"STRING", "\".*\""},
    {"TUPLE", "\\((.*?,.*?)\\)"},
};

Lexer::Lexer(string input, Logger *logger)
{
    this->input = input;
    this->working_input = input;
    this->index = 0;
    this->tokens = {};
    this->logger = logger;
}

vector<Token> Lexer::lex()
{
    this->logger->debug("Lexing file");
    while (this->index < this->input.length())
    {
        // Precedence: comments, keywords, separators, operators, literals, identifiers

        // Comments
        if (this->input.substr(this->index, 2) == "//")
        {
            // Single-line comment
            size_t endOfComment = this->input.find('\n', this->index);
            if (endOfComment == string::npos)
                endOfComment = this->input.length();
            this->tokens.push_back(Token{"COMMENT", this->input.substr(this->index, endOfComment - this->index)});
            this->index = endOfComment;
        }
        else if (this->input.substr(this->index, 2) == "/*")
        {
            // Multi-line comment
            size_t endOfComment = this->input.find("*/", this->index);
            if (endOfComment == string::npos)
            {
                this->logger->error("Unterminated multi-line comment.");
                // Handle the error or continue parsing, depending on your needs.
                break;
            }
            this->tokens.push_back(Token{"COMMENT", this->input.substr(this->index, endOfComment - this->index + 2)});
            this->index = endOfComment + 2;
        }
        else
        {
            // Handle other tokens (keywords, separators, operators, literals, identifiers) here.
        }

        this->index++;
    }

    return this->tokens;
}
