#!/usr/bin/env python3 import ctypes import re import sys import os

PTRACE_ATTACH = 16 PTRACE_DETACH = 17

libc = ctypes.CDLL("libc.so.6") _libc_ptrace = libc.ptrace _libc_ptrace.argtypes = [ctypes.c_int, ctypes.c_int, ctypes.c_void_p, ctypes.c_void_p] _libc_ptrace.restype = ctypes.c_long

class PtraceError(Exception): pass

def ptrace(attach: bool, pid: int) -> None: op = PTRACE_ATTACH if attach else PTRACE_DETACH ret = _libc_ptrace(ctypes.c_int(op), ctypes.c_int(pid), None, None) if ret == -1: errno = ctypes.get_errno() raise PtraceError(f"ptrace(op={op}) failed (errno={errno})")

def parse_maps_line(line: str): m = re.match(r'([0-9A-Fa-f]+)-([0-9A-Fa-f]+)\s+([rwxps-]{4})', line) if not m: return None start = int(m.group(1), 16) end = int(m.group(2), 16) perms = m.group(3) return start, end, perms

def read_memory_regions(pid: int, maps_path=None, mem_path=None, do_ptrace: bool=False, max_read_size=10_000_000): if maps_path is None: maps_path = f"/proc/{pid}/maps" if mem_path is None: mem_path = f"/proc/{pid}/mem"

if do_ptrace: ptrace(True, pid)

try: with open(maps_path, "r", encoding="utf-8", errors="replace") as maps_file: with open(mem_path, "rb", buffering=0) as mem_file: for line in maps_file: parsed = parse_maps_line(line) if not parsed: continue start, end, perms = parsed if 'r' in perms: size = end - start if size <= 0 or size > max_read_size: continue try: # Use os.lseek for 64-bit addresses os.lseek(mem_file.fileno(), start, os.SEEK_SET) data = mem_file.read(size) yield (start, end, data) except (OSError, ValueError, OverflowError): continue finally: if do_ptrace: try: ptrace(False, pid) except Exception: pass def main(argv=None): if argv is None: argv = sys.argv if len(argv) < 2: print(f"Usage: {argv[0]} <pid> [--ptrace]") return 2 pid = int(argv[1]) do_ptrace = ("--ptrace" in argv) for start, end, data in read_memory_regions(pid, do_ptrace=do_ptrace): try: sys.stdout.buffer.write(data) except Exception: print(data) return 0

if name == "main": raise SystemExit(main())
