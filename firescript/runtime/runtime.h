#ifndef RUNTIME_H
#define RUNTIME_H

#include "varray.h"

char *firescript_input(char *prompt);
char *firescript_strcat(const char *s1, const char *s2);
bool firescript_strcmp(const char *s1, const char *s2);
void firescript_print_array(VArray* array, const char* elem_type);
void free_all_inputs(void);
void firescript_cleanup(void);

#endif