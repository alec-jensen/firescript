#ifndef CONVERSIONS_H
#define CONVERSIONS_H

#include <stdio.h>
#include <string.h>
#include <stdbool.h>
#include <stdlib.h>
#include <mpfr.h>
#include <gmp.h>

static int firescript_toInt_impl_string(const char *s)
{
    return atoi(s);
}

static int firescript_toInt_impl_bool(bool b)
{
    return b ? 1 : 0;
}

static int firescript_toInt_impl_int(int i)
{
    return i;
}

static int firescript_toInt_impl_float(float f)
{
    return (int)f;
}

static int firescript_toInt_impl_double(double d)
{
    return (int)d;
}

#define firescript_toInt(x) _Generic((x),       \
    char *: firescript_toInt_impl_string,       \
    const char *: firescript_toInt_impl_string, \
    bool: firescript_toInt_impl_bool,           \
    int: firescript_toInt_impl_int,             \
    float: firescript_toInt_impl_float,         \
    double: firescript_toInt_impl_double,       \
    default: firescript_toInt_impl_string)(x)

static float firescript_toFloat_impl_string(const char *s)
{
    return atof(s);
}

static float firescript_toFloat_impl_bool(bool b)
{
    return b ? 1.0f : 0.0f;
}

static float firescript_toFloat_impl_int(int i)
{
    return (float)i;
}

static float firescript_toFloat_impl_float(float f)
{
    return f;
}

static float firescript_toFloat_impl_double(double d)
{
    return (float)d;
}

#define firescript_toFloat(x) _Generic((x),       \
    char *: firescript_toFloat_impl_string,       \
    const char *: firescript_toFloat_impl_string, \
    bool: firescript_toFloat_impl_bool,           \
    int: firescript_toFloat_impl_int,             \
    float: firescript_toFloat_impl_float,         \
    double: firescript_toFloat_impl_double,       \
    default: firescript_toFloat_impl_string)(x)

static double firescript_toDouble_impl_string(const char *s)
{
    return atof(s);
}

static double firescript_toDouble_impl_bool(bool b)
{
    return b ? 1.0 : 0.0;
}

static double firescript_toDouble_impl_int(int i)
{
    return (double)i;
}

static double firescript_toDouble_impl_float(float f)
{
    return (double)f;
}

static double firescript_toDouble_impl_double(double d)
{
    return d;
}

#define firescript_toDouble(x) _Generic((x),       \
    char *: firescript_toDouble_impl_string,       \
    const char *: firescript_toDouble_impl_string, \
    bool: firescript_toDouble_impl_bool,           \
    int: firescript_toDouble_impl_int,             \
    float: firescript_toDouble_impl_float,         \
    double: firescript_toDouble_impl_double,       \
    default: firescript_toDouble_impl_string)(x)

static bool firescript_toBool_impl_string(const char *s)
{
    return strcmp(s, "true") == 0 || strcmp(s, "1") == 0;
}

static bool firescript_toBool_impl_bool(bool b)
{
    return b;
}

static bool firescript_toBool_impl_int(int i)
{
    return i != 0;
}

static bool firescript_toBool_impl_float(float f)
{
    return f != 0.0f;
}

static bool firescript_toBool_impl_double(double d)
{
    return d != 0.0;
}

#define firescript_toBool(x) _Generic((x),       \
    char *: firescript_toBool_impl_string,       \
    const char *: firescript_toBool_impl_string, \
    bool: firescript_toBool_impl_bool,           \
    int: firescript_toBool_impl_int,             \
    float: firescript_toBool_impl_float,         \
    double: firescript_toBool_impl_double,       \
    default: firescript_toBool_impl_string)(x)

static char *firescript_toString_impl_string(const char *s)
{
    return strdup(s);
}

static char *firescript_toString_impl_bool(bool b)
{
    return strdup(b ? "true" : "false");
}

static char *firescript_toString_impl_int(int i)
{
    char buffer[32];
    snprintf(buffer, sizeof(buffer), "%d", i);
    return strdup(buffer);
}

static char *firescript_toString_impl_int8(int8_t i)
{
    char buffer[32];
    snprintf(buffer, sizeof(buffer), "%" PRId8, i);
    return strdup(buffer);
}

static char *firescript_toString_impl_int16(int16_t i)
{
    char buffer[32];
    snprintf(buffer, sizeof(buffer), "%" PRId16, i);
    return strdup(buffer);
}

static char *firescript_toString_impl_int32(int32_t i)
{
    char buffer[32];
    snprintf(buffer, sizeof(buffer), "%" PRId32, i);
    return strdup(buffer);
}

static char *firescript_toString_impl_int64(int64_t i)
{
    char buffer[32];
    snprintf(buffer, sizeof(buffer), "%" PRId64, i);
    return strdup(buffer);
}

static char *firescript_toString_impl_uint8(uint8_t i)
{
    char buffer[32];
    snprintf(buffer, sizeof(buffer), "%" PRIu8, i);
    return strdup(buffer);
}

static char *firescript_toString_impl_uint16(uint16_t i)
{
    char buffer[32];
    snprintf(buffer, sizeof(buffer), "%" PRIu16, i);
    return strdup(buffer);
}

static char *firescript_toString_impl_uint32(uint32_t i)
{
    char buffer[32];
    snprintf(buffer, sizeof(buffer), "%" PRIu32, i);
    return strdup(buffer);
}

static char *firescript_toString_impl_uint64(uint64_t i)
{
    char buffer[32];
    snprintf(buffer, sizeof(buffer), "%" PRIu64, i);
    return strdup(buffer);
}

static char *firescript_toString_impl_float(float f)
{
    char buffer[32];
    snprintf(buffer, sizeof(buffer), "%f", f);
    return strdup(buffer);
}

static char *firescript_toString_impl_double(double d)
{
    char buffer[32];
    snprintf(buffer, sizeof(buffer), "%f", d);
    return strdup(buffer);
}

static char *firescript_toString_impl_long_double(long double d)
{
    char buffer[128];
    firescript_format_long_double(buffer, sizeof(buffer), d);
    return strdup(buffer);
}

static char *firescript_toString_impl_mpfr(mpfr_t d)
{
    char buffer[128];
    mpfr_snprintf(buffer, sizeof(buffer), "%.10Rf", d);
    return strdup(buffer);
}

#define firescript_toString(x) _Generic((x),       \
    char *: firescript_toString_impl_string,       \
    const char *: firescript_toString_impl_string, \
    bool: firescript_toString_impl_bool,           \
    int8_t: firescript_toString_impl_int8,         \
    int16_t: firescript_toString_impl_int16,       \
    int32_t: firescript_toString_impl_int32,       \
    int64_t: firescript_toString_impl_int64,       \
    uint8_t: firescript_toString_impl_uint8,       \
    uint16_t: firescript_toString_impl_uint16,     \
    uint32_t: firescript_toString_impl_uint32,     \
    uint64_t: firescript_toString_impl_uint64,     \
    float: firescript_toString_impl_float,         \
    double: firescript_toString_impl_double,       \
    long double: firescript_toString_impl_long_double, \
    mpfr_t: firescript_toString_impl_mpfr,         \
    default: firescript_toString_impl_string)(x)

static char firescript_toChar_impl_string(const char *s)
{
    return *s;
}

static char firescript_toChar_impl_bool(bool b)
{
    return b ? 't' : 'f';
}

static char firescript_toChar_impl_int(int i)
{
    return (char)i;
}

static char firescript_toChar_impl_float(float f)
{
    return (char)f;
}

static char firescript_toChar_impl_double(double d)
{
    return (char)d;
}

#define firescript_toChar(x) _Generic((x),       \
    char *: firescript_toChar_impl_string,       \
    const char *: firescript_toChar_impl_string, \
    bool: firescript_toChar_impl_bool,           \
    int: firescript_toChar_impl_int,             \
    float: firescript_toChar_impl_float,         \
    double: firescript_toChar_impl_double,       \
    default: firescript_toChar_impl_string)(x)

#endif