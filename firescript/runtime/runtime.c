#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdbool.h>
#include <stdint.h>
#include <gmp.h>
#include <mpfr.h>
#include <float.h>
#include <fcntl.h>
#include <unistd.h>
#include "runtime.h"

// Internal registry to track heap pointers allocated via firescript_malloc/strdup
typedef struct PtrNode {
    void *p;
    struct PtrNode *next;
} PtrNode;

static PtrNode *g_ptrs = NULL;
static int32_t g_process_argc = 0;
static char **g_process_argv = NULL;

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

void firescript_set_process_args(int argc, char **argv)
{
    if (g_process_argv != NULL)
    {
        for (int32_t i = 0; i < g_process_argc; i++)
        {
            if (g_process_argv[i] != NULL)
            {
                firescript_free(g_process_argv[i]);
            }
        }
        firescript_free(g_process_argv);
        g_process_argv = NULL;
        g_process_argc = 0;
    }

    if (argc <= 0 || argv == NULL)
    {
        return;
    }

    g_process_argv = (char **)firescript_malloc((size_t)argc * sizeof(char *));
    if (g_process_argv == NULL)
    {
        return;
    }

    g_process_argc = (int32_t)argc;
    for (int32_t i = 0; i < g_process_argc; i++)
    {
        const char *src = argv[i] ? argv[i] : "";
        g_process_argv[i] = firescript_strdup(src);
        if (g_process_argv[i] == NULL)
        {
            g_process_argv[i] = firescript_strdup("");
        }
    }
}

int32_t firescript_argc(void)
{
    return g_process_argc;
}

char *firescript_argv_at(int32_t index)
{
    if (index < 0 || index >= g_process_argc || g_process_argv == NULL)
    {
        return firescript_strdup("");
    }
    return firescript_strdup(g_process_argv[index] ? g_process_argv[index] : "");
}

int32_t firescript_str_length(const char *s)
{
    if (s == NULL)
    {
        return 0;
    }
    return (int32_t)strlen(s);
}

char *firescript_str_char_at(const char *s, int32_t index)
{
    if (s == NULL)
    {
        return firescript_strdup("");
    }
    int32_t len = (int32_t)strlen(s);
    if (index < 0 || index >= len)
    {
        return firescript_strdup("");
    }
    char *out = (char *)firescript_malloc(2);
    if (out == NULL)
    {
        return firescript_strdup("");
    }
    out[0] = s[index];
    out[1] = '\0';
    return out;
}

int32_t firescript_str_index_of(const char *haystack, const char *needle)
{
    if (haystack == NULL || needle == NULL)
    {
        return -1;
    }
    const char *pos = strstr(haystack, needle);
    if (pos == NULL)
    {
        return -1;
    }
    return (int32_t)(pos - haystack);
}

char *firescript_str_slice(const char *s, int32_t start, int32_t end)
{
    if (s == NULL)
    {
        return firescript_strdup("");
    }

    int32_t len = (int32_t)strlen(s);
    if (start < 0)
    {
        start = 0;
    }
    if (end < 0)
    {
        end = 0;
    }
    if (start > len)
    {
        start = len;
    }
    if (end > len)
    {
        end = len;
    }
    if (end < start)
    {
        end = start;
    }

    int32_t out_len = end - start;
    char *out = (char *)firescript_malloc((size_t)out_len + 1);
    if (out == NULL)
    {
        return firescript_strdup("");
    }
    if (out_len > 0)
    {
        memcpy(out, s + start, (size_t)out_len);
    }
    out[out_len] = '\0';
    return out;
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

// Type conversion functions  
char *firescript_i32_to_str(int32_t value) {
    // Allocate buffer (max int32 is -2147483648, which is 11 chars + null)
    char *buf = firescript_malloc(12);
    if (!buf) return NULL;
    snprintf(buf, 12, "%d", (int)value);
    return buf;
}

char *firescript_i64_to_str(int64_t value) {
    // Allocate buffer (max int64 is -9223372036854775808, which is 20 chars + null)
    char *buf = firescript_malloc(21);
    if (!buf) return NULL;
    snprintf(buf, 21, "%lld", (long long)value);
    return buf;
}

char *firescript_f32_to_str(float value) {
    // Float can need up to ~15 characters for representation
    char *buf = firescript_malloc(32);
    if (!buf) return NULL;
    snprintf(buf, 32, "%g", value);
    return buf;
}

char *firescript_f64_to_str(double value) {
    // Double can need up to ~24 characters for representation
    char *buf = firescript_malloc(32);
    if (!buf) return NULL;
    snprintf(buf, 32, "%g", value);
    return buf;
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

/* ---- POSIX syscall helpers (directive enable_syscalls) ---- */

SyscallResult firescript_syscall_open(const char *path, const char *mode)
{
    if (!path || !mode)
        return (SyscallResult){ .status = -1, .data = firescript_strdup("") };

    int flags = 0;
    mode_t perm = 0644;
    if (strcmp(mode, "r") == 0)
        flags = O_RDONLY;
    else if (strcmp(mode, "w") == 0)
        flags = O_WRONLY | O_CREAT | O_TRUNC;
    else if (strcmp(mode, "a") == 0)
        flags = O_WRONLY | O_CREAT | O_APPEND;
    else if (strcmp(mode, "r+") == 0)
        flags = O_RDWR;
    else if (strcmp(mode, "w+") == 0)
        flags = O_RDWR | O_CREAT | O_TRUNC;
    else
        return (SyscallResult){ .status = -22, .data = firescript_strdup("") }; /* -EINVAL */

    int fd = open(path, flags, perm);
    return (SyscallResult){ .status = (int32_t)fd, .data = firescript_strdup("") };
}

SyscallResult firescript_syscall_read(int fd, int32_t n)
{
    if (n <= 0)
        return (SyscallResult){ .status = -22, .data = firescript_strdup("") };

    char *buf = firescript_malloc((size_t)n + 1);
    if (!buf)
        return (SyscallResult){ .status = -12, .data = firescript_strdup("") }; /* -ENOMEM */

    ssize_t bytes = read(fd, buf, (size_t)n);
    if (bytes < 0) {
        firescript_free(buf);
        return (SyscallResult){ .status = (int32_t)bytes, .data = firescript_strdup("") };
    }
    buf[bytes] = '\0';
    return (SyscallResult){ .status = (int32_t)bytes, .data = buf };
}

SyscallResult firescript_syscall_write(int fd, const char *buf)
{
    if (!buf)
        return (SyscallResult){ .status = -22, .data = firescript_strdup("") };

    ssize_t written = write(fd, buf, strlen(buf));
    return (SyscallResult){ .status = (int32_t)written, .data = firescript_strdup("") };
}

SyscallResult firescript_syscall_close(int fd)
{
    int result = close(fd);
    return (SyscallResult){ .status = result, .data = firescript_strdup("") };
}