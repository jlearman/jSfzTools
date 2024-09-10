
def get_sint24(file):
    bytes = file.read(3)
    if len(bytes) < 3:
        raise EOFError
    return int.from_bytes(bytes, byteorder='little', signed=True)

def put_sint24(file, val):
    bytes = val.to_bytes(length=3, byteorder='little', signed=True)
    file.write(bytes)

def get_sint16(file):
    bytes = file.read(2)
    if len(bytes) < 2:
        raise EOFError
    return int.from_bytes(bytes, byteorder='little', signed=True)

def put_sint16(file):
    bytes = val.to_bytes(length=2, byteorder='little', signed=True)
    file.write(bytes)

def get_uint32(file):
    bytes = file.read(4)
    if len(bytes) < 4:
        raise EOFError
    return int.from_bytes(bytes, byteorder='little', signed=False)

def put_uint32(file, val):
    bytes = val.to_bytes(length=4, byteorder='little', signed=False)
    file.write(bytes)

def get_uint24(file):
    bytes = file.read(3)
    if len(bytes) < 3:
        raise EOFError
    return int.from_bytes(bytes, byteorder='little', signed=False)

def get_uint16(file):
    bytes = file.read(2)
    if len(bytes) < 2:
        raise EOFError
    return int.from_bytes(bytes, byteorder='little', signed=False)

def put_uint16(file, val):
    bytes = val.to_bytes(length=2, byteorder='little', signed=False)
    file.write(bytes)

def get_uint8(file):
    bytes = file.read(1)
    if len(bytes) < 1:
        raise EOFError
    return int.from_bytes(bytes, byteorder='little', signed=False)

