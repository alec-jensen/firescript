#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdbool.h>
#include <stdint.h>
#include <gmp.h>
#include <mpfr.h>
#include <float.h>
#include "runtime.h"

// Internal registry to track heap pointers allocated via firescript_malloc/strdup
typedef struct PtrNode {
    void *p;
    struct PtrNode *next;
} PtrNode;

static PtrNode *g_ptrs = NULL;

// Use the real libc functions inside our wrappers
#undef malloc
#undef strdup
#undef free

static void registry_add(void *p) {
    if (!p) return;
    PtrNode *n = (PtrNode*)malloc(sizeof(PtrNode));
    if (!n) return; // out of memory, best effort: still return allocated pointer
    n->p = p;
    n->next = g_ptrs;
    g_ptrs = n;
}

static int registry_remove(void *p) {
    if (!p) return 0;
    PtrNode *prev = NULL;
    PtrNode *cur = g_ptrs;
    while (cur) {
        if (cur->p == p) {
            if (prev) prev->next = cur->next; else g_ptrs = cur->next;
            free(cur);
            return 1;
        }
        prev = cur;
        cur = cur->next;
    }
    return 0;
}

void *firescript_malloc(size_t size) {
    void *p = malloc(size);
    registry_add(p);
    return p;
}

char *firescript_strdup(const char *s) {
    char *p = strdup(s ? s : "");
    registry_add(p);
    return p;
}

void firescript_free(void *p) {
    // Only free if we allocated and tracked it
    if (registry_remove(p)) {
        free(p);
    }
    // ignore frees of untracked pointers (e.g., string literals or already freed)
}

// Function to create a reference-counted object
RefCountedObject *create_ref_counted_object(void *data, void (*destructor)(void *))
{
    RefCountedObject *obj = malloc(sizeof(RefCountedObject));
    if (!obj)
        return NULL;
    obj->data = data;
    obj->ref_count = 1; // Initial reference count is 1
    obj->destructor = destructor;
    return obj;
}

// Function to increment the reference count
void increment_ref_count(RefCountedObject *obj)
{
    if (obj)
    {
        obj->ref_count++;
    }
}

// Function to decrement the reference count and free the object if necessary
void decrement_ref_count(RefCountedObject *obj)
{
    if (obj && --obj->ref_count == 0)
    {
        if (obj->destructor)
        {
            obj->destructor(obj->data);
        }
        free(obj);
    }
}

// Generic destructor for strings
static void string_destructor(void *str)
{
    if (str)
    {
        free(str);
    }
}

// Big integer support: initialize rop from decimal string (allocates and sets)
void firescript_toBigInt(mpz_t rop, const char *s)
{
    mpz_init(rop);
    if (s)
        mpz_set_str(rop, s, 10);
}

// Print a big integer followed by newline
void firescript_print_int(const mpz_t x)
{
    mpz_out_str(stdout, 10, x);
    printf("\n");
}

// Print a int64_t followed by newline
void firescript_print_int64(int64_t x)
{
    printf("%ld\n", x);
}

// New function that returns a RefCountedObject containing a string
RefCountedObject *firescript_create_string(const char *str)
{
    char *copy = str ? strdup(str) : strdup("");
    if (!copy)
        return NULL;
    return create_ref_counted_object(copy, string_destructor);
}

// Updated input function that returns a reference counted string
RefCountedObject *firescript_input_ref(const char *prompt)
{
    printf("%s", prompt);

    char buffer[256];
    if (scanf("%255s", buffer) != 1)
    {
        buffer[0] = '\0';
    }

    char *result = strdup(buffer);
    if (!result)
        return NULL;

    return create_ref_counted_object(result, string_destructor);
}

// Legacy input function for backward compatibility
char *firescript_input(char *prompt)
{
    RefCountedObject *ref_str = firescript_input_ref(prompt);
    if (!ref_str)
        return NULL;

    // For the legacy function, we can't track this memory,
    // but the caller is responsible for it
    char *result = strdup((char *)ref_str->data);

    // Clean up the ref counted object
    decrement_ref_count(ref_str);

    return result;
}

// String concatenation function that uses reference counting
RefCountedObject *firescript_strcat_ref(RefCountedObject *s1_obj, RefCountedObject *s2_obj)
{
    const char *s1 = s1_obj ? (const char *)s1_obj->data : "";
    const char *s2 = s2_obj ? (const char *)s2_obj->data : "";

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

    return create_ref_counted_object(result, string_destructor);
}

// Legacy strcat function for backward compatibility
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
        return NULL;

    memcpy(result, s1, len1);
    memcpy(result + len1, s2, len2);
    result[len1 + len2] = '\0';

    return result;
}

bool firescript_strcmp(const char *s1, const char *s2)
{
    return strcmp(s1, s2) == 0;
}

// New function for comparing reference counted strings
bool firescript_strcmp_ref(RefCountedObject *s1_obj, RefCountedObject *s2_obj)
{
    if (!s1_obj || !s2_obj)
        return s1_obj == s2_obj;
    return strcmp((const char *)s1_obj->data, (const char *)s2_obj->data) == 0;
}


// Print a float followed by newline
void firescript_print_float(float x)
{
    printf("%f\n", x);
}

// Print a double followed by newline
void firescript_print_double(double x)
{
    printf("%f\n", x);
}

// Format a long double into a buffer (portable across platforms lacking %Lf in printf)
size_t firescript_format_long_double(char *buf, size_t size, long double x)
{
    if (!buf || size == 0)
        return 0;
    buf[0] = '\0';

    mpfr_t tmp;
    mpfr_init2(tmp, (mpfr_prec_t)LDBL_MANT_DIG);
    mpfr_set_ld(tmp, x, MPFR_RNDN);
    int n = mpfr_snprintf(buf, size, "%.10Rf", tmp);
    mpfr_clear(tmp);

    if (n < 0)
    {
        buf[0] = '\0';
        return 0;
    }
    // Ensure null-termination even if truncated
    buf[size - 1] = '\0';
    return (size_t)n;
}

// Print a long double followed by newline
void firescript_print_long_double(long double x)
{
    char buf[128];
    firescript_format_long_double(buf, sizeof(buf), x);
    puts(buf);
}

// Print a reference counted string
void firescript_print_string_ref(RefCountedObject *str_obj)
{
    if (str_obj && str_obj->data)
    {
        printf("%s\n", (const char *)str_obj->data);
    }
    else
    {
        printf("null\n");
    }
}

void firescript_cleanup(void)
{
    // Cleanup any leaked tracked pointers (best-effort)
    PtrNode *cur = g_ptrs;
    while (cur) {
        PtrNode *n = cur->next;
        free(cur->p);
        free(cur);
        cur = n;
    }
    g_ptrs = NULL;
}