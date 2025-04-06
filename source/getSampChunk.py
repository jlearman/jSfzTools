#!/usr/bin/env python3

# get SMPL chunk from a RIFF file

import struct
import sys

def get_smpl_chunk(file_path: str):
    """
    Prints all headers in a RIFF file.

    Args:
        file_path (str): The path to the RIFF file.
    """
    try:
        with open(file_path, 'rb') as f:
            # Read the RIFF header
            riff_tag = f.read(4)
            if riff_tag != b'RIFF':
                raise ValueError("Not a valid RIFF file")
            
            file_size = struct.unpack("<I", f.read(4))[0]
            wave_tag = f.read(4)
            if verbose:
                print(f"RIFF Header: {riff_tag.decode('ascii')}, Size: {file_size}, Format: {wave_tag.decode('ascii')}")

            # Read chunks
            while f.tell() < file_size + 8:  # RIFF header is 8 bytes
                chunk_header = f.read(8)
                if len(chunk_header) < 8:
                    break
                chunk_id, chunk_size = struct.unpack("<4sI", chunk_header)
                if verbose:
                    print(f"Chunk ID: {chunk_id.decode('ascii')}, Size: {chunk_size}")
                if chunk_id == b'smpl':
                    chunk_data = f.read(chunk_size)
                    return chunk_header + chunk_data
                else:
                    f.seek(chunk_size, 1)
    except Exception as e:
        print(f"Error reading RIFF file: {e}", file=sys.stderr)

verbose = False

if __name__ == '__main__':
    import argparse
    import os

    wav_file_path = ''
    chunk_file_path = ''
    verbose = False

    if len(sys.argv) == 1 and os.environ.get('TERM_PROGRAM') == 'vscode':
        # Test values when running in VSCode
        wav_file_path = 'source/hamlet_a3_long_rr1.wav'
        chunk_file_path = 'chunk'
        verbose = True
    else:
        parser = argparse.ArgumentParser(description="Extract a specific chunk from a WAV file.")
        parser.add_argument('wav_file_path', type=str, help="Input WAV file.")
        parser.add_argument('chunk_file_path', type=str, help="Output file (smpl chunk).")
        parser.add_argument('-v', '--verbose', action='store_true', help="Enable verbose output.")
        args = parser.parse_args()

        wav_file_path = args.wav_file_path
        chunk_file_path = args.chunk_file_path
        verbose = args.verbose
    
    chunk_data = get_smpl_chunk(wav_file_path)

    if chunk_data == None:
        print(f"SMPL chunk not found in '{wav_file_path}'", file=sys.stderr)
        sys.exit(1)
    with open(chunk_file_path, 'wb') as wf:
        wf.write(chunk_data)       