#!/usr/bin/env python3
"""Splice a built Image into a stock boot image.

Usage:
    splice_boot.py <stock_boot.img> <Image> <out_boot.img>
"""
import struct
import sys


def main():
    if len(sys.argv) != 4:
        print(__doc__)
        sys.exit(1)
    stock, image, out = sys.argv[1:4]

    OFF = 0x1000
    AVB0 = 0x22B5000

    with open(stock, 'rb') as f:
        img = bytearray(f.read())
    with open(image, 'rb') as f:
        k = f.read()

    if OFF + len(k) >= AVB0:
        print('error: kernel too large for this boot image layout')
        sys.exit(1)

    img[8:12] = struct.pack('<I', len(k))
    img[OFF:OFF + len(k)] = k

    with open(out, 'wb') as f:
        f.write(img)
    with open(out, 'rb') as f:
        f.seek(AVB0)
        if f.read(4) != b'AVB0':
            print('warning: AVB0 signature block not found at expected offset')

    print('written:', out)
    print('kernel size:', len(k), hex(len(k)))


if __name__ == '__main__':
    main()
