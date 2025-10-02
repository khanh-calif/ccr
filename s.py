#!/usr/bin/env python3
import ctypes
import re
import sys
import os
import mmap

PTRACE_ATTACH = 16
PTRACE_DETACH = 17

libc = ctypes.CDLL("libc.so.6")
_libc_ptrace = libc.ptrace
_libc_ptrace.argtypes = [ctypes.c_int, ctypes.c_int, ctypes.c_void_p, ctypes.c_void_p]
_libc_ptrace.restype = ctypes.c_long

class PtraceError(Exception):
    pass

def ptrace(attach: bool, pid: int) -> None:
    op = PTRACE_ATTACH if attach else PTRACE_DETACH
    ret = _libc_ptrace(ctypes.c_int(op), ctypes.c_int(pid), None, None)
    if ret == -1:
        errno = ctypes.get_errno()
        raise PtraceError(f"ptrace(op={op}) failed (errno={errno})")

def parse_maps_line(line: str):
    m = re.match(r'([0-9A-Fa-f]+)-([0-9A-Fa-f]+)\s+([rwxps\-]{4})', line)
    if not m:
        return None
    start = int(m.group(1), 16)
    end = int(m.group(2), 16)
    perms = m.group(3)
    return start, end, perms

def read_memory_regions(pid: int, maps_path=None, mem_path=None, do_ptrace: bool=False, max_read_size=10_000_000):
    if maps_path is None:
        maps_path = f"/proc/{pid}/maps"
    if mem_path is None:
        mem_path = f"/proc/{pid}/mem"

    if do_ptrace:
        ptrace(True, pid)

    try:
        with open(maps_path, "r", encoding="utf-8", errors="replace") as maps_file:
            for line in maps_file:
                parsed = parse_maps_line(line)
                if not parsed:
                    continue
                start, end, perms = parsed
                if 'r' in perms:
                    size = end - start
                    if size <= 0 or size > max_read_size:
                        continue
                    try:
                        # Open and mmap each region individually
                        with open(mem_path, "rb") as mem_file:
                            try:
                                # Try to mmap the specific region
                                with mmap.mmap(mem_file.fileno(), size, access=mmap.ACCESS_READ, offset=start) as mm:
                                    data = mm.read(size)
                                    yield (start, end, data)
                            except (OSError, ValueError, OverflowError):
                                # If mmap fails, try reading without seeking by opening at the start each time
                                try:
                                    # Use ctypes to handle large file operations
                                    import fcntl
                                    fd = os.open(mem_path, os.O_RDONLY)
                                    try:
                                        # Use lseek64 for large offsets
                                        libc = ctypes.CDLL("libc.so.6")
                                        lseek64 = libc.lseek64
                                        lseek64.argtypes = [ctypes.c_int, ctypes.c_longlong, ctypes.c_int]
                                        lseek64.restype = ctypes.c_longlong

                                        # Seek to the start position
                                        result = lseek64(fd, start, 0)  # SEEK_SET = 0
                                        if result != start:
                                            continue

                                        # Read the data
                                        data = os.read(fd, size)
                                        if len(data) > 0:
                                            yield (start, end, data)
                                    finally:
                                        os.close(fd)
                                except (OSError, ValueError):
                                    continue
                    except (OSError, ValueError):
                        continue
    finally:
        if do_ptrace:
            try:
                ptrace(False, pid)
            except Exception:
                pass

def main(argv=None):
    if argv is None:
        argv = sys.argv
    if len(argv) < 2:
        print(f"Usage: {argv[0]} <pid> [--ptrace] [-o output_file]")
        return 2

    pid = int(argv[1])
    do_ptrace = ("--ptrace" in argv)
    output_file = None

    # Parse -o parameter
    try:
        o_index = argv.index("-o")
        if o_index + 1 < len(argv):
            output_file = argv[o_index + 1]
        else:
            print("Error: -o parameter requires a filename")
            return 2
    except ValueError:
        pass  # -o not found, use stdout

    # Open output file or use stdout
    if output_file:
        try:
            with open(output_file, "wb") as f:
                for start, end, data in read_memory_regions(pid, do_ptrace=do_ptrace):
                    f.write(data)
        except IOError as e:
            print(f"Error writing to file {output_file}: {e}")
            return 1
    else:
        for start, end, data in read_memory_regions(pid, do_ptrace=do_ptrace):
            try:
                sys.stdout.buffer.write(data)
            except Exception:
                print(data)
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
