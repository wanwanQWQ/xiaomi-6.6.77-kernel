#!/usr/bin/env python3
"""Patch __kcrctab entries in v32 vmlinux to v16 (stock) CRC values.

Locates every __crc_* symbol by the section that CONTAINS its address,
which also handles the LOCAL __crc_module_layout symbol.
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


def locate(secs, value):
    for sec in secs:
        if sec['addr'] <= value < sec['addr'] + sec['size']:
            return sec
    return None


def crc_entries(path):
    secs = sections(path)
    data = open(path, 'rb').read()
    out = {}
    for s in symbols(path):
        if not s['name'].startswith('__crc_'):
            continue
        name = s['name'][6:]
        sec = locate(secs, s['value'])
        if sec is None:
            print('WARN: no section for', s['name'], hex(s['value']))
            continue
        pos = sec['off'] + (s['value'] - sec['addr'])
        out[name] = (pos, struct.unpack('<I', data[pos:pos + 4])[0], sec['name'])
    return out


def main():
    v16path = sys.argv[1] if len(sys.argv) > 1 else '/build/out-v16/vmlinux'
    newpath = sys.argv[2] if len(sys.argv) > 2 else '/build/out-v32/vmlinux'
    outpath = sys.argv[3] if len(sys.argv) > 3 else '/build/out-v32/vmlinux_patched2'
    v16 = crc_entries(v16path)
    v32 = crc_entries(newpath)
    print('v16 entries:', len(v16), 'new entries:', len(v32))
    print('module_layout in v16:', v16.get('module_layout'))
    print('module_layout in new:', v32.get('module_layout'))

    data = bytearray(open(newpath, 'rb').read())
    changed = 0
    for name, (pos, old, secname) in v32.items():
        if name in v16:
            want = v16[name][1]
            if want != old:
                data[pos:pos + 4] = struct.pack('<I', want)
                changed += 1
    print('changed:', changed)
    open(outpath, 'wb').write(bytes(data))

    # verify
    new = bytearray(open(outpath, 'rb').read())
    ok = 0
    for name, (pos, _, _) in v32.items():
        if name in v16 and struct.unpack('<I', bytes(new[pos:pos + 4]))[0] == v16[name][1]:
            ok += 1
    print('verify: %d/%d match v16' % (ok, len(v16)))
    if 'module_layout' in v32:
        print('module_layout patched to:', hex(struct.unpack('<I', bytes(new[v32['module_layout'][0]:v32['module_layout'][0] + 4]))[0]))


if __name__ == '__main__':
    main()
