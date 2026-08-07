#!/usr/bin/env python3
"""Patch a freshly built vmlinux's __kcrctab to stock CRC values.

Usage:
    patch_crc_table.py <vmlinux> <crc_table.txt> [out_vmlinux]

The CRC table is a text file with one "name 0x........" entry per line.
"""
import struct
import subprocess
import sys


def sections(path):
    out = subprocess.check_output(['readelf', '-SW', path], text=True, errors='replace')
    secs = []
    for line in out.splitlines():
        parts = line.split()
        if len(parts) < 11 or not parts[0].startswith('['):
            continue
        try:
            if parts[0] == '[':
                idx = int(parts[1].rstrip(']'))
            else:
                idx = int(parts[0].strip('[]'))
        except ValueError:
            continue
        name_idx = 1 if parts[0] != '[' else 2
        secs.append({'idx': idx, 'name': parts[name_idx],
                     'addr': int(parts[name_idx + 2], 16),
                     'off': int(parts[name_idx + 3], 16),
                     'size': int(parts[name_idx + 4], 16)})
    return secs


def symbols(path):
    out = subprocess.check_output(['readelf', '-sW', path], text=True, errors='replace')
    syms = []
    for line in out.splitlines():
        parts = line.split()
        if len(parts) < 8 or not parts[0].rstrip(':').isdigit():
            continue
        try:
            value = int(parts[1], 16)
            name = parts[7]
        except (ValueError, IndexError):
            continue
        syms.append({'value': value, 'name': name})
    return syms


def read_table(path):
    table = {}
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            name, crc = line.split()
            table[name] = int(crc, 16)
    return table


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(1)
    vmlinux = sys.argv[1]
    table_path = sys.argv[2]
    out = sys.argv[3] if len(sys.argv) > 3 else vmlinux + '.patched'

    table = read_table(table_path)
    print('table entries:', len(table))

    secs = sections(vmlinux)
    data = bytearray(open(vmlinux, 'rb').read())
    found = 0
    changed = 0
    missing = 0
    for s in symbols(vmlinux):
        if not s['name'].startswith('__crc_'):
            continue
        name = s['name'][6:]
        if name not in table:
            missing += 1
            continue
        for sec in secs:
            if sec['addr'] <= s['value'] < sec['addr'] + sec['size']:
                pos = sec['off'] + (s['value'] - sec['addr'])
                old = struct.unpack('<I', bytes(data[pos:pos + 4]))[0]
                if old != table[name]:
                    data[pos:pos + 4] = struct.pack('<I', table[name])
                    changed += 1
                found += 1
                break
    print('patched symbols:', found, 'changed:', changed, 'missing from table:', missing)
    open(out, 'wb').write(bytes(data))
    print('written:', out)


if __name__ == '__main__':
    main()
