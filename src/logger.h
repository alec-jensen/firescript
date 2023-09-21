#ifndef LOGGER_H
#define LOGGER_H

#include <iostream>

using std::cout;
using std::endl;
using std::string;

class Logger
{
public:
    string mode;
    int level = 0;
    Logger(string mode)
    {
        this->mode = mode;

        if (this->mode == "debug")
        {
            this->level = 0;
        }
        else if (this->mode == "info")
        {
            this->level = 1;
        }
        else if (this->mode == "warn")
        {
            this->level = 2;
        }
        else if (this->mode == "error")
        {
            this->level = 3;
        }
        else
        {
            cout << "Invalid logger mode: " << this->mode << endl;
            cout << "Valid modes: debug, info, warn, error" << endl;
            exit(1);
        }
    }

    Logger(int level) {
        this->level = level;
    }

    void debug(string message)
    {
        if (this->level <= 0)
        {
            cout << "DEBUG: " << message << endl;
        }
    }

    void info(string message)
    {
        if (this->level <= 1)
        {
            cout << "INFO: " << message << endl;
        }
    }

    void warn(string message)
    {
        if (this->level <= 2)
        {
            cout << "WARN: " << message << endl;
        }
    }

    void error(string message)
    {
        if (this->level <= 3)
        {
            cout << "ERROR: " << message << endl;
        }
    }
};
#endif