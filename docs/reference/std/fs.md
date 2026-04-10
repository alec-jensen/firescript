# File System (`std.fs`)

The `std.fs` module provides file-system operations through an object-oriented `File` API centered on methods and result types.

## Core Classes

### `File`

Represents a file path and provides methods for common file operations.

```firescript
class File {
    string path;
    
    File(&this, string path);
    
    FileResult read(&this);
    FileResult readBytes(&this, int32 bytes);
    FileResult writeAll(&this, string data);
    FileResult appendAll(&this, string data);
    bool exists(&this);
    FileResult remove(&this);
    FileResult renameTo(&this, string new_path);
    FileResult moveTo(&this, string dst_path);
}
```

**Constructor:**

```firescript
File(&this, string path)
```

Create a `File` instance for the given path. The path is stored but the file is not opened until an operation is called.

**Parameters:**
- `path`: File path (relative or absolute)

**Example:**

```firescript
import @firescript/std.fs.File;

File myFile = File("hello.txt");
```

### `FileResult`

Encapsulates the result of a file operation.

```firescript
class FileResult {
    int32 status;
    string data;
    
    FileResult(int32 status, string data);
}
```

**Fields:**
- `status`: Operation status (≥ 0 for success, negative errno for failure)
- `data`: Operation output (e.g., file contents for reads), empty for most writes

**Check the status:** A negative `status` indicates an error. Use helper functions to inspect results (see below).

## File Methods

### `read()`

```firescript
FileResult read(&this)
```

Read the entire file contents into a string.

**Returns:** `FileResult` with status = bytes read (on success) or negative error code

**Example:**

```firescript
import @firescript/std.fs.File;
import @firescript/std.fs.result_data;
import @firescript/std.fs.ok;

File f = File("data.txt");
FileResult r = f.read();
if (ok(r)) {
    println(result_data(r));
}
```

### `readBytes(int32 bytes)`

```firescript
FileResult readBytes(&this, int32 bytes)
```

Read up to the specified number of bytes.

**Parameters:**
- `bytes`: Maximum bytes to read

**Returns:** `FileResult` with status = bytes actually read

**Example:**

```firescript
FileResult chunk = f.readBytes(1024);
```

### `writeAll(string data)`

```firescript
FileResult writeAll(&this, string data)
```

Write data to the file, overwriting if it exists.

**Parameters:**
- `data`: String data to write

**Returns:** `FileResult` with status = bytes written (on success) or error code

**Example:**

```firescript
FileResult w = f.writeAll("Hello!");
```

### `appendAll(string data)`

```firescript
FileResult appendAll(&this, string data)
```

Append data to the end of the file.

**Parameters:**
- `data`: String data to append

**Returns:** `FileResult` with status = bytes written (on success) or error code

**Example:**

```firescript
FileResult a = f.appendAll("\nMore text");
```

### `exists()`

```firescript
bool exists(&this)
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
FileResult remove(&this)
```

Delete the file.

**Returns:** `FileResult` with status = 0 on success, negative error code on failure

**Example:**

```firescript
f.remove();
```

### `renameTo(string new_path)`

```firescript
FileResult renameTo(&this, string new_path)
```

Rename (or move within same filesystem) to a new path. Updates the `File` path on success.

**Parameters:**
- `new_path`: New file path

**Returns:** `FileResult` with status = 0 on success

**Example:**

```firescript
f.renameTo("newname.txt");
```

### `moveTo(string dst_path)`

```firescript
FileResult moveTo(&this, string dst_path)
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

## Result Helper Functions

### `ok(FileResult)`

```firescript
bool ok(&FileResult result)
```

Check if operation succeeded (status ≥ 0).

**Example:**

```firescript
if (ok(result)) {
    println("Success!");
}
```

### `err_code(FileResult)`

```firescript
int32 err_code(&FileResult result)
```

Extract the error code (positive errno value). Returns 0 if operation succeeded.

**Example:**

```firescript
int32 err = err_code(result);
if (err > 0) {
    println("Error: " + err);
}
```

### `result_status(FileResult)`

```firescript
int32 result_status(&FileResult result)
```

Get the raw status field (positive on success, negative errno on failure).

### `result_data(FileResult)`

```firescript
string result_data(&FileResult result)
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
import @firescript/std.fs.ok;
import @firescript/std.fs.result_data;
import @firescript/std.io.println;

File config = File("config.txt");

// Write
FileResult write_result = config.writeAll("setting=value");
if (ok(write_result)) {
    println("Configuration saved");
}

// Read
FileResult read_result = config.read();
if (ok(read_result)) {
    println("Configuration: " + result_data(read_result));
}

// Cleanup
config.remove();
```
