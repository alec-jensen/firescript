#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdbool.h>
#include "varray.h"

#define MAX_INPUTS 1024

static char *input_registry[MAX_INPUTS];
static int input_count = 0;

static char *strcat_registry[MAX_INPUTS];
static int strcat_count = 0;

char *firescript_input(char *prompt)
{
    printf("%s", prompt);

    char buffer[256];
    if (scanf("%255s", buffer) != 1)
    {
        buffer[0] = '\0';
    }
    // Duplicate the string so that the caller owns it.
    char *result = strdup(buffer);
    if (input_count < MAX_INPUTS)
    {
        input_registry[input_count++] = result;
    }
    else
    {
        // If you run out of registry slots, free immediately (or handle error)
        free(result);
        result = NULL;
    }
    return result;
}

char *firescript_strcat(const char *s1, const char *s2)
{
    if (!s1)
        s1 = "";
    if (!s2)
        s2 = "";

    size_t len1 = strlen(s1);
    size_t len2 = strlen(s2);

    char *result = malloc(len1 + len2 + 1);
    if (!result)
    {
        return NULL;
    }

    memcpy(result, s1, len1);
    memcpy(result + len1, s2, len2);
    result[len1 + len2] = '\0';

    if (strcat_count < MAX_INPUTS)
    {
        strcat_registry[strcat_count++] = result;
    }
    else
    {
        free(result);
        result = NULL;
    }

    return result;
}

bool firescript_strcmp(const char *s1, const char *s2)
{
    return strcmp(s1, s2) == 0;
}

void firescript_print_array(VArray* array, const char* elem_type) {
    if (!array) {
        printf("null");
        return;
    }

    printf("[");
    for (size_t i = 0; i < array->size; i++) {
        // Print each element according to its type
        if (strcmp(elem_type, "int") == 0) {
            int value = ((int*)(array->data))[i];
            printf("%d", value);
        } 
        else if (strcmp(elem_type, "float") == 0) {
            float value = ((float*)(array->data))[i];
            printf("%f", value);
        } 
        else if (strcmp(elem_type, "double") == 0) {
            double value = ((double*)(array->data))[i];
            printf("%f", value);
        } 
        else if (strcmp(elem_type, "bool") == 0) {
            bool value = ((bool*)(array->data))[i];
            printf("%s", value ? "true" : "false");
        } 
        else if (strcmp(elem_type, "string") == 0) {
            char* value = ((char**)(array->data))[i];
            printf("\"%s\"", value ? value : "null");
        }
        else {
            printf("?");
        }
        
        // Print comma between elements, but not after the last one
        if (i < array->size - 1) {
            printf(", ");
        }
    }
    printf("]\n");
}

void free_all_registries(void)
{
    for (int i = 0; i < input_count; i++)
    {
        free(input_registry[i]);
    }
    for (int i = 0; i < strcat_count; i++)
    {
        free(strcat_registry[i]);
    }
}

void firescript_cleanup(void)
{
    free_all_registries();
}