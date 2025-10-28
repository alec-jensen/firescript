#ifndef RUNTIME_H
#define RUNTIME_H

#include <stddef.h>
#include <stdbool.h>
#include <stdint.h>
#include <gmp.h>
#include <mpfr.h>

// Structure for reference-counted objects
typedef struct RefCountedObject
{
    void *data;                 // Pointer to the actual data
    size_t ref_count;           // Reference count
    void (*destructor)(void *); // Function to free the data
} RefCountedObject;

// Function prototypes for reference counting
RefCountedObject *create_ref_counted_object(void *data, void (*destructor)(void *));
void increment_ref_count(RefCountedObject *obj);
void decrement_ref_count(RefCountedObject *obj);

// Reference counted string operations
RefCountedObject *firescript_create_string(const char *str);
RefCountedObject *firescript_input_ref(const char *prompt);
RefCountedObject *firescript_strcat_ref(RefCountedObject *s1_obj, RefCountedObject *s2_obj);
bool firescript_strcmp_ref(RefCountedObject *s1_obj, RefCountedObject *s2_obj);
void firescript_print_string_ref(RefCountedObject *str_obj);

// Big integer support
// Initialize rop from decimal string
void firescript_toBigInt(mpz_t rop, const char *s);
// Print a big integer with newline
void firescript_print_int(const mpz_t x);

// Print a int64_t with newline
void firescript_print_int64(int64_t x);

// Decimal support
// Initialize rop with precision and set from string
void firescript_initDecimal(mpfr_t rop, const char *s);
// Print a decimal with newline
void firescript_print_bigfloat(const mpfr_t x);
// Decimal arithmetic operations
void firescript_decimal_add(mpfr_t result, const mpfr_t a, const mpfr_t b);
void firescript_decimal_sub(mpfr_t result, const mpfr_t a, const mpfr_t b);
void firescript_decimal_mul(mpfr_t result, const mpfr_t a, const mpfr_t b);
void firescript_decimal_div(mpfr_t result, const mpfr_t a, const mpfr_t b);
// Decimal comparison
int firescript_decimal_cmp(const mpfr_t a, const mpfr_t b);

// Print a float with newline
void firescript_print_float(float x);
// Print a double with newline
void firescript_print_double(double x);

// Legacy functions for backward compatibility
char *firescript_input(char *prompt);
char *firescript_strcat(const char *s1, const char *s2);
bool firescript_strcmp(const char *s1, const char *s2);
void firescript_cleanup(void);

#endif