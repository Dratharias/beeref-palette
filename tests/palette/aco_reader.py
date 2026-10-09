import struct


def read_aco(path):
    """Parse an .aco file; return [(name, (r, g, b))] from its v2 block."""
    with open(path, 'rb') as f:
        data = f.read()
    version, count = struct.unpack_from('>HH', data, 0)
    assert version == 1
    offset = 4 + count * 10
    version, count = struct.unpack_from('>HH', data, offset)
    assert version == 2
    offset += 4
    result = []
    for _ in range(count):
        space, r, g, b, _z = struct.unpack_from('>5H', data, offset)
        assert space == 0
        offset += 10
        (length,) = struct.unpack_from('>I', data, offset)
        offset += 4
        name = data[offset:offset + 2 * (length - 1)].decode('utf-16-be')
        assert data[offset + 2 * (length - 1):offset + 2 * length] == b'\0\0'
        offset += 2 * length
        result.append((name, (r // 257, g // 257, b // 257)))
    assert offset == len(data)
    return result
