# File System (`std.fs`)

The `std.fs` module provides file-system operations through an object-oriented `File` API centered on methods and result types.

## Core Classes

### `File`

Represents a file path and provides methods for common file operations.

```firescript
class File {
    path: string;

    fn File(&mut this, path: string);

    fn read(&this) -> FileResult;
    fn readBytes(&this, bytes: int32) -> FileResult;
    fn writeAll(&this, data: string) -> FileResult;
    fn appendAll(&this, data: string) -> FileResult;
    fn exists(&this) -> bool;
    fn remove(&this) -> FileResult;
    fn renameTo(&mut this, new_path: string) -> FileResult;
    fn moveTo(&mut this, dst_path: string) -> FileResult;
}
```

**Constructor:**

```firescript
fn File(&mut this, path: string)
```

Create a `File` instance for the given path. The path is stored but the file is not opened until an operation is called.

**Parameters:**
- `path`: File path (relative or absolute)

**Example:**

```firescript
import @firescript/std.fs.File;

myFile: File = File("hello.txt");
```

### `FileResult`

Encapsulates the result of a file operation.

```firescript
class FileResult {
    status: int32;
    data: string;

    fn FileResult(status: int32, data: string);

    fn ok(&this) -> bool;
    fn err_code(&this) -> int32;
    fn result_status(&this) -> int32;
    fn result_data(&this) -> string;
}
```

**Fields:**
- `status`: Operation status (≥ 0 for success, negative errno for failure)
- `data`: Operation output (e.g., file contents for reads), empty for most writes

**Check the status:** A negative `status` indicates an error. Use `FileResult` methods to inspect results.

## File Methods

### `read()`

```firescript
fn read(&this) -> FileResult
```

Read the entire file contents into a string.

**Returns:** `FileResult` with status = bytes read (on success) or negative error code

**Example:**

```firescript
import @firescript/std.fs.File;
import @firescript/std.io.println;

f: File = File("data.txt");
r: FileResult = f.read();
if (r.ok()) {
    println(r.result_data());
}
```

### `readBytes(bytes: int32)`

```firescript
fn readBytes(&this, bytes: int32) -> FileResult
```

Read up to the specified number of bytes.

**Parameters:**
- `bytes`: Maximum bytes to read

**Returns:** `FileResult` with status = bytes actually read

**Example:**

```firescript
chunk: FileResult = f.readBytes(1024);
```

### `writeAll(data: string)`

```firescript
fn writeAll(&this, data: string) -> FileResult
```

Write data to the file, overwriting if it exists.

**Parameters:**
- `data`: String data to write

**Returns:** `FileResult` with status = bytes written (on success) or error code

**Example:**

```firescript
w: FileResult = f.writeAll("Hello!");
```

### `appendAll(data: string)`

```firescript
fn appendAll(&this, data: string) -> FileResult
```

Append data to the end of the file.

**Parameters:**
- `data`: String data to append

**Returns:** `FileResult` with status = bytes written (on success) or error code

**Example:**

```firescript
a: FileResult = f.appendAll("\nMore text");
```

### `exists()`

```firescript
fn exists(&this) -> bool
```

Check if the file exists and is readable.

**Returns:** `true` if file exists and can be opened for reading, `false` otherwise

**Example:**

```firescript
if (f.exists()) {
    println("File found!");
}
```

### `remove()`

```firescript
fn remove(&this) -> FileResult
```

Delete the file.

**Returns:** `FileResult` with status = 0 on success, negative error code on failure

**Example:**

```firescript
f.remove();
```

### `renameTo(new_path: string)`

```firescript
fn renameTo(&mut this, new_path: string) -> FileResult
```

Rename (or move within same filesystem) to a new path. Updates the `File` path on success.

**Parameters:**
- `new_path`: New file path

**Returns:** `FileResult` with status = 0 on success

**Example:**

```firescript
f.renameTo("newname.txt");
```

### `moveTo(dst_path: string)`

```firescript
fn moveTo(&mut this, dst_path: string) -> FileResult
```

Move file to a new location with cross-filesystem fallback. On cross-device moves, automatically falls back to copy + delete.
Updates the `File` path on success.

**Parameters:**
- `dst_path`: Destination path

**Returns:** `FileResult` with status = 0 on success

**Example:**

```firescript
f.moveTo("/other/location/file.txt");
```

## FileResult Methods

### `ok()`

```firescript
fn ok(&this) -> bool
```

Check if operation succeeded (status >= 0).

**Example:**

```firescript
if (result.ok()) {
    println("Success!");
}
```

### `err_code()`

```firescript
fn err_code(&this) -> int32
```

Extract the error code (positive errno value). Returns 0 if operation succeeded.

**Example:**

```firescript
err: int32 = result.err_code();
if (err > 0) {
    println("Error: " + (err as string));
}
```

### `result_status()`

```firescript
fn result_status(&this) -> int32
```

Get the raw status field (positive on success, negative errno on failure).

### `result_data()`

```firescript
fn result_data(&this) -> string
```

Get the data field (file contents for reads, empty for writes).

## Error Codes

File operations return negative errno values on error:

- `-2`: ENOENT (file not found)
- `-13`: EACCES (permission denied)
- `-28`: ENOSPC (no space on device)
- `-30`: EROFS (read-only filesystem)
- etc.

Consult your system's `errno.h` for a complete list.

## Example

```firescript
import @firescript/std.fs.File;
import @firescript/std.io.println;

config: File = File("config.txt");

// Write
write_result: FileResult = config.writeAll("setting=value");
if (write_result.ok()) {
    println("Configuration saved");
}

// Read
read_result: FileResult = config.read();
if (read_result.ok()) {
    println("Configuration: " + read_result.result_data());
}

// Cleanup
config.remove();
```
