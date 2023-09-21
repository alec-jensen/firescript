#include <iostream>
#include <vector>
#include <fstream>

#include "logger.h"
#include "lexer.h"

using std::cout;
using std::endl;
using std::string;
using std::vector;

struct Arguments
{
    string firescriptPath; // Path to currently running firescript compiler
    string file;           // File to compile
    bool debug = false;    // Debug mode
    bool help = false;     // Help mode
    string outputBinary;   // Output binary path
    bool argError = false; // Error in arguments; quit immediately
};

Arguments getArguments(int argc, char **argv);

int main(int argc, char **argv)
{
    Logger *logger = new Logger("info");
    Arguments args = getArguments(argc, argv);
    if (args.argError)
    {
        return 1;
    }

    if (args.debug)
    {
        logger->level = 0;
        logger->debug("Debug mode enabled");
    }

    if (args.help)
    {
        cout << "Usage: firescript [options] [file]" << endl;
        cout << "Options:" << endl;
        cout << "  -d, --debug\t\tEnable debug mode" << endl;
        cout << "  -h, --help\t\tShow this help message" << endl;
        cout << "  -o, --output\t\tSpecify output binary path" << endl;
        return 0;
    }

    if (args.file.empty())
    {
        cout << "Error: no file specified" << endl;
        return 1;
    }

    logger->debug("Opening file '" + args.file + "'");

    std::ifstream file(args.file);

    std::string content((std::istreambuf_iterator<char>(file)),
                        (std::istreambuf_iterator<char>()));

    logger->debug("Lexing file '" + args.file + "'");

    Lexer *lex = new Lexer(content, logger);

    vector<Token> tokens = lex->lex();

    free(lex);

    for (int i = 0; i < tokens.size(); i++)
    {
        Token token = tokens[i];
        cout << token.type << ": " << token.value << endl;
    }

    free(logger);

    return 0;
}

Arguments getArguments(int argc, char **argv)
{
    Arguments args;
    for (int i = 1; i < argc; i++)
    {
        string arg = argv[i];
        if (arg == "-d" || arg == "--debug")
        {
            args.debug = true;
        }
        else if (arg == "-h" || arg == "--help")
        {
            args.help = true;
        }
        else if (arg == "-o" || arg == "--output")
        {
            if (i + 1 < argc)
            {
                args.outputBinary = argv[i + 1];
                i++;
            }
            else
            {
                cout << "Error: no output file specified" << endl;
                args.argError = true;
            }
        }
        else if (i == argc - 1)
        {
            args.file = arg;
        }
        else
        {
            cout << "Error: unknown argument '" << arg << "'" << endl;
            args.argError = true;
        }
    }
    return args;
}