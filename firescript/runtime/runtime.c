#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdbool.h>
#include "varray.h"
#include <gmp.h>

typedef struct RefCountedObject {
    void *data;
    size_t ref_count;
    void (*destructor)(void *);
} RefCountedObject;

// Function to create a reference-counted object
RefCountedObject *create_ref_counted_object(void *data, void (*destructor)(void *)) {
    RefCountedObject *obj = malloc(sizeof(RefCountedObject));
    if (!obj) return NULL;
    obj->data = data;
    obj->ref_count = 1; // Initial reference count is 1
    obj->destructor = destructor;
    return obj;
}

// Function to increment the reference count
void increment_ref_count(RefCountedObject *obj) {
    if (obj) {
        obj->ref_count++;
    }
}

// Function to decrement the reference count and free the object if necessary
void decrement_ref_count(RefCountedObject *obj) {
    if (obj && --obj->ref_count == 0) {
        if (obj->destructor) {
            obj->destructor(obj->data);
        }
        free(obj);
    }
}

// Generic destructor for strings
static void string_destructor(void *str) {
    if (str) {
        free(str);
    }
}

// Big integer support: initialize rop from decimal string (allocates and sets)
void firescript_toBigInt(mpz_t rop, const char *s) {
    mpz_init(rop);
    if (s) mpz_set_str(rop, s, 10);
}

// Print a big integer followed by newline
void firescript_print_int(const mpz_t x) {
    mpz_out_str(stdout, 10, x);
    printf("\n");
}

// New function that returns a RefCountedObject containing a string
RefCountedObject* firescript_create_string(const char* str) {
    char* copy = str ? strdup(str) : strdup("");
    if (!copy) return NULL;
    return create_ref_counted_object(copy, string_destructor);
}

// Updated input function that returns a reference counted string
RefCountedObject* firescript_input_ref(const char* prompt) {
    printf("%s", prompt);

    char buffer[256];
    if (scanf("%255s", buffer) != 1) {
        buffer[0] = '\0';
    }
    
    char* result = strdup(buffer);
    if (!result) return NULL;
    
    return create_ref_counted_object(result, string_destructor);
}

// Legacy input function for backward compatibility
char *firescript_input(char *prompt) {
    RefCountedObject* ref_str = firescript_input_ref(prompt);
    if (!ref_str) return NULL;
    
    // For the legacy function, we can't track this memory,
    // but the caller is responsible for it
    char* result = strdup((char*)ref_str->data);
    
    // Clean up the ref counted object
    decrement_ref_count(ref_str);
    
    return result;
}

// String concatenation function that uses reference counting
RefCountedObject* firescript_strcat_ref(RefCountedObject* s1_obj, RefCountedObject* s2_obj) {
    const char* s1 = s1_obj ? (const char*)s1_obj->data : "";
    const char* s2 = s2_obj ? (const char*)s2_obj->data : "";

    size_t len1 = strlen(s1);
    size_t len2 = strlen(s2);

    char *result = malloc(len1 + len2 + 1);
    if (!result) {
        return NULL;
    }

    memcpy(result, s1, len1);
    memcpy(result + len1, s2, len2);
    result[len1 + len2] = '\0';

    return create_ref_counted_object(result, string_destructor);
}

// Legacy strcat function for backward compatibility
char *firescript_strcat(const char *s1, const char *s2) {
    if (!s1) s1 = "";
    if (!s2) s2 = "";

    size_t len1 = strlen(s1);
    size_t len2 = strlen(s2);

    char *result = malloc(len1 + len2 + 1);
    if (!result) return NULL;

    memcpy(result, s1, len1);
    memcpy(result + len1, s2, len2);
    result[len1 + len2] = '\0';

    return result;
}

bool firescript_strcmp(const char *s1, const char *s2) {
    return strcmp(s1, s2) == 0;
}

// New function for comparing reference counted strings
bool firescript_strcmp_ref(RefCountedObject* s1_obj, RefCountedObject* s2_obj) {
    if (!s1_obj || !s2_obj) return s1_obj == s2_obj;
    return strcmp((const char*)s1_obj->data, (const char*)s2_obj->data) == 0;
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

// Print a reference counted string
void firescript_print_string_ref(RefCountedObject* str_obj) {
    if (str_obj && str_obj->data) {
        printf("%s\n", (const char*)str_obj->data);
    } else {
        printf("null\n");
    }
}

void firescript_cleanup(void) {
    // No registries to clean up - objects clean themselves up via reference counting
}