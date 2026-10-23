#!/usr/bin/env python3
"""OptiScaler.dll UI 字符串汉化器（索引版）

把指定文件偏移处的 ASCII 显示串替换成 UTF-8 中文：
- 中文写进新增的 .zh 节
- 重写 .text 里所有 RIP-relative 引用（lea/mov + disp32）
- 重写 8 字节绝对指针

用法: python patch_ui.py <src.dll> <dst.dll> <translations.json>
"""
import struct, json, sys, time

IB = 0x180000000
TEXT_RAW, TEXT_VA, TEXT_SZ = 0x400, 0x1000, 0x39b600
SEC_ALIGN, FILE_ALIGN = 0x1000, 0x200


def align(v, a):
    return (v + a - 1) // a * a


def parse_pe(d):
    pe = struct.unpack_from('<I', d, 0x3c)[0]
    nsec = struct.unpack_from('<H', d, pe + 6)[0]
    opt = pe + 24
    optsz = 240 if struct.unpack_from('<H', d, opt)[0] == 0x20b else 224
    info = {'pe': pe, 'nsec': nsec, 'opt': opt,
            'imagebase': struct.unpack_from('<Q', d, opt + 24)[0],
            'sizeofimage': struct.unpack_from('<I', d, opt + 56)[0],
            'sectiontable': opt + optsz, 'sections': []}
    for i in range(nsec):
        s = info['sectiontable'] + i * 40
        vs, va, rs, ra = struct.unpack_from('<IIII', d, s + 8)
        info['sections'].append({'name': d[s:s + 8].rstrip(b'\x00').decode('latin1'),
                                 'vsize': vs, 'vaddr': va, 'rawsize': rs, 'rawptr': ra})
    return info


def off_to_va(off, info):
    for s in info['sections']:
        if s['rawptr'] <= off < s['rawptr'] + s['rawsize']:
            return info['imagebase'] + off - s['rawptr'] + s['vaddr']
    raise ValueError('offset 0x%x not mapped' % off)


def build_ref_index(d, info):
    """一次扫过 .text，建 target_va -> [(disp32 文件偏移, 引用结束 VA)] 索引。"""
    text = bytes(d[TEXT_RAW:TEXT_RAW + TEXT_SZ])
    base = info['imagebase'] + TEXT_VA
    idx = {}
    geti = struct.Struct('<i').unpack_from
    for pos in range(1, len(text) - 8):
        if (text[pos - 1] & 0xC7) != 0x05:      # mod=00 rm=101 → RIP-relative
            continue
        for k in (4, 5, 6, 7):
            va_end = base + pos + k
            tgt = va_end + geti(text, pos)[0]
            idx.setdefault(tgt, []).append((TEXT_RAW + pos, va_end))
    return idx


def main():
    src, dst, tmap_path = sys.argv[1], sys.argv[2], sys.argv[3]
    t0 = time.time()
    d = bytearray(open(src, 'rb').read())
    info = parse_pe(d)
    tm = {int(k): v for k, v in json.load(open(tmap_path, encoding='utf-8')).items()}

    newsec = bytearray()
    plan = []
    for off, zh in sorted(tm.items()):
        end = d.find(b'\x00', off)
        orig = bytes(d[off:end])
        if not orig or not all(32 <= c < 127 or c in (9, 10, 13) for c in orig):
            raise SystemExit('bad original at 0x%x: %r' % (off, orig))
        if off and d[off - 1] != 0:
            raise SystemExit('offset 0x%x is not a string start' % off)
        plan.append((off_to_va(off, info), len(newsec), orig.decode('latin1')))
        newsec += zh.encode('utf-8') + b'\x00'

    last = info['sections'][-1]
    new_va = info['imagebase'] + align(last['vaddr'] + last['vsize'], SEC_ALIGN)
    new_raw = align(len(d), FILE_ALIGN)
    raw_size = align(len(newsec), FILE_ALIGN)

    idx = build_ref_index(d, info)
    print('ref index: %d targets in %.1fs' % (len(idx), time.time() - t0))

    refs = ptrs = 0
    old_va_map = {old_va: new_va + item_off for old_va, item_off, _ in plan}
    for old_va, new_target in old_va_map.items():
        for disp_off, va_end in idx.get(old_va, ()):
            struct.pack_into('<i', d, disp_off, new_target - va_end)
            refs += 1

    q = struct.Struct('<Q').unpack_from
    for i in range(0, len(d) - 8, 8):
        v = q(d, i)[0]
        if v in old_va_map:
            struct.pack_into('<Q', d, i, old_va_map[v])
            ptrs += 1

    d += b'\x00' * (new_raw - len(d))
    d += bytes(newsec) + b'\x00' * (raw_size - len(newsec))

    st = info['sectiontable'] + info['nsec'] * 40
    if st + 40 > info['sections'][0]['rawptr']:
        raise SystemExit('no room in section table')
    d[st:st + 40] = struct.pack('<8sIIIIIIHHI', b'.zh\x00\x00\x00\x00\x00',
                               len(newsec), new_va - info['imagebase'], raw_size,
                               new_raw, 0, 0, 0, 0, 0x40000040)
    struct.pack_into('<H', d, info['pe'] + 6, info['nsec'] + 1)
    new_soi = align(new_va - info['imagebase'] + len(newsec), SEC_ALIGN)
    struct.pack_into('<I', d, info['opt'] + 56, new_soi)

    open(dst, 'wb').write(d)
    print('strings=%d refs=%d absptrs=%d  (%.1fs)' % (len(plan), refs, ptrs, time.time() - t0))
    print('.zh va=0x%x raw=0x%x size=%d  SizeOfImage 0x%x -> 0x%x'
          % (new_va, new_raw, len(newsec), info['sizeofimage'], new_soi))


if __name__ == '__main__':
    main()
