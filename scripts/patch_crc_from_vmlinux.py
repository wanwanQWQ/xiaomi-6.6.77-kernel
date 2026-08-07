#!/usr/bin/env python3
"""Patch a freshly built vmlinux's __kcrctab to reference (stock) CRC values.

Usage:
    patch_crc_from_vmlinux.py <reference_vmlinux> <built_vmlinux> [out_vmlinux]

The reference vmlinux is a kernel build whose exported symbol CRCs match the
prebuilt vendor modules (for example, a build with the stock configuration).
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
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(1)
    ref_path = sys.argv[1]
    target_path = sys.argv[2]
    out_path = sys.argv[3] if len(sys.argv) > 3 else target_path + '.patched'

    ref = crc_entries(ref_path)
    target = crc_entries(target_path)
    print('reference entries:', len(ref), 'target entries:', len(target))
    print('module_layout in reference:', ref.get('module_layout'))
    print('module_layout in target:', target.get('module_layout'))

    data = bytearray(open(target_path, 'rb').read())
    changed = 0
    for name, (pos, old, _) in target.items():
        if name in ref:
            want = ref[name][1]
            if want != old:
                data[pos:pos + 4] = struct.pack('<I', want)
                changed += 1
    print('changed:', changed)
    open(out_path, 'wb').write(bytes(data))

    # verify
    new = bytearray(open(out_path, 'rb').read())
    ok = 0
    for name, (pos, _, _) in target.items():
        if name in ref and struct.unpack('<I', bytes(new[pos:pos + 4]))[0] == ref[name][1]:
            ok += 1
    print('verify: %d/%d match reference' % (ok, len(ref)))
    if 'module_layout' in target:
        print('module_layout patched to:', hex(struct.unpack('<I', bytes(new[target['module_layout'][0]:target['module_layout'][0] + 4]))[0]))


if __name__ == '__main__':
    main()
