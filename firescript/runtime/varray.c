#include <stdio.h>
#include <stdlib.h>
#include <string.h>

typedef struct
{
    size_t size;      // number of elements stored
    size_t capacity;  // number of elements allocated
    size_t elem_size; // size (in bytes) of each element
    char data[];      // raw storage for elements
} VArray;

VArray *varray_create(size_t capacity, size_t elem_size)
{
    VArray *va = malloc(sizeof(VArray) + capacity * elem_size);
    if (va)
    {
        va->size = 0;
        va->capacity = capacity;
        va->elem_size = elem_size;
    }
    return va;
}

VArray *varray_resize(VArray *va, size_t new_capacity)
{
    va = realloc(va, sizeof(VArray) + new_capacity * va->elem_size);
    if (va)
    {
        va->capacity = new_capacity;
        if (va->size > new_capacity)
            va->size = new_capacity;
    }
    return va;
}

VArray *varray_append(VArray *va, const void *element)
{
    if (va->size >= va->capacity)
    {
        size_t new_capacity = (va->capacity > 0) ? va->capacity * 2 : 1;
        VArray *temp = varray_resize(va, new_capacity);
        if (!temp)
        {
            return va; // allocation failed; return original
        }
        va = temp;
    }
    memcpy(va->data + va->size * va->elem_size, element, va->elem_size);
    va->size++;
    return va;
}

VArray *varray_insert(VArray *va, size_t index, const void *element)
{
    if (index > va->size)
    {
        // Invalid index; do nothing.
        return va;
    }
    if (va->size >= va->capacity)
    {
        size_t new_capacity = (va->capacity > 0) ? va->capacity * 2 : 1;
        VArray *temp = varray_resize(va, new_capacity);
        if (!temp)
        {
            return va;
        }
        va = temp;
    }
    // Shift elements to the right.
    memmove(va->data + (index + 1) * va->elem_size,
            va->data + index * va->elem_size,
            (va->size - index) * va->elem_size);
    memcpy(va->data + index * va->elem_size, element, va->elem_size);
    va->size++;
    return va;
}

VArray *varray_remove(VArray *va, size_t index)
{
    if (index >= va->size)
    {
        // Invalid index; do nothing.
        return va;
    }
    // Shift elements left.
    memmove(va->data + index * va->elem_size,
            va->data + (index + 1) * va->elem_size,
            (va->size - index - 1) * va->elem_size);
    va->size--;
    // Shrink capacity if size is less than one-quarter of capacity.
    if (va->capacity > 1 && va->size < va->capacity / 4)
    {
        size_t new_capacity = va->capacity / 2;
        VArray *temp = varray_resize(va, new_capacity);
        if (temp)
        {
            va = temp;
        }
    }
    return va;
}

void varray_clear(VArray *va)
{
    va->size = 0;
}

void varray_free(VArray *va)
{
    free(va);
}