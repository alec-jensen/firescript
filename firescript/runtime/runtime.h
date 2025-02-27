#ifndef RUNTIME_H
#define RUNTIME_H

char *firescript_input(char *prompt);
char *firescript_strcat(const char *s1, const char *s2);
bool firescript_strcmp(const char *s1, const char *s2);
void free_all_inputs(void);
void firescript_cleanup(void);

#endif