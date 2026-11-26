"""Check cross-build provenance before committing GPU time to a candidate."""
import argparse
import hashlib
import re
import subprocess
from pathlib import Path

def output(*args):
    return subprocess.check_output(args, text=True)

def field(text, name):
    match = re.search(r'^\s*' + name + r':\s*(\S+)', text, re.MULTILINE)
    if not match:
        raise ValueError('Missing ' + name)
    return match[1].casefold()

def check(checkout, exe, pdb, expected):
    pe = output('llvm-readobj', '--coff-debug-directory', exe)
    summary = output('llvm-pdbutil', 'dump', '--summary', pdb)
    if (field(pe, 'PDBGUID'), field(pe, 'PDBAge')) != (field(summary, 'GUID'), field(summary, 'Age')):
        raise ValueError('Executable and PDB differ')
    sources = output('llvm-pdbutil', 'dump', '--files', pdb)
    recorded = {}
    for digest, source in re.findall(r'^\s*- \(SHA-256: ([0-9A-Fa-f]+)\) (.+)$', sources, re.MULTILINE):
        suffix = re.search(r'(?:^|/)((?:crates/victory-[\w-]+|apps/victory)/src/.+)$', source.replace('\\', '/'))
        if suffix:
            recorded.setdefault(suffix[1], set()).add(digest.lower())
    errors = []
    for path in set(expected) | recorded.keys():
        local = checkout / path
        if not local.is_file() or recorded.get(path) != {hashlib.sha256(local.read_bytes()).hexdigest()}:
            errors.append(path)
    if errors or not recorded:
        raise ValueError('Missing or mismatched runtime sources: ' + ', '.join(sorted(errors)))
    return len(recorded)

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('checkout', type=Path)
    parser.add_argument('executable', type=Path)
    parser.add_argument('pdb', type=Path)
    parser.add_argument('sources', nargs='*')
    args = parser.parse_args()
    try:
        count = check(args.checkout, args.executable, args.pdb, args.sources)
    except (ValueError, OSError, subprocess.CalledProcessError) as error:
        parser.exit(1, f'{error}\n')
    print(f'Executable and PDB match, {count} runtime source checksums verified.')
