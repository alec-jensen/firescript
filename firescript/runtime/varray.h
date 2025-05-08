#ifndef VARRAY_H
#define VARRAY_H

#include <stddef.h>
#include <gmp.h>

typedef struct
{
    size_t size;      // number of elements stored
    size_t capacity;  // number of elements allocated
    size_t elem_size; // size (in bytes) of each element
    char data[];      // raw storage for elements
} VArray;

VArray *varray_create(size_t capacity, size_t elem_size);
VArray *varray_resize(VArray *va, size_t new_capacity);
VArray *varray_append(VArray *va, const void *element);
VArray *varray_insert(VArray *va, size_t index, const void *element);
VArray *varray_remove(VArray *va, size_t index);
void varray_clear(VArray *va);
void varray_free(VArray *va);
// Pop element at index and return it in popped_value (for mpz_t arrays)
// Signature: popped_value receives the element, va is updated
void varray_pop(mpz_t popped_value, VArray **va, size_t index);

#endif
