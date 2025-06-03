import os
import argparse

EXTENSIONS = {'.cpp', '.c', '.h', '.hpp', '.py'}

def has_empty_eof(filepath):
    try:
        print(f"Checking {filepath} for empty EOF...")
        with open(filepath, 'rb') as f:
            f.seek(0, os.SEEK_END)
            if f.tell() == 0:
                return True  # Empty file
            f.seek(-1, os.SEEK_END)
            last_byte = f.read(1)
            if last_byte == b'\n':
                return True
        with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
            lines = f.readlines()
            if lines and lines[-1].strip() == '':
                return True
    except Exception as e:
        print(f"Error reading {filepath}: {e}")
    return False

def find_files_without_eof(root_dir):
    files = []
    for dirpath, _, filenames in os.walk(root_dir):
        for fname in filenames:
            ext = os.path.splitext(fname)[1]
            if ext in EXTENSIONS:
                fpath = os.path.join(dirpath, fname)
                if not has_empty_eof(fpath):
                    files.append(fpath)
    return files

def append_empty_line(filepath):
    with open(filepath, 'a', encoding='utf-8', errors='ignore') as f:
        f.write('\n')

def main():
    parser = argparse.ArgumentParser(description="Check and optionally fix missing empty lines at EOF for source files.")
    parser.add_argument('--append', action='store_true', help='Append empty line to files missing it')
    parser.add_argument('--root', default=os.getcwd(), help='Root directory to search (default: current directory)')
    args = parser.parse_args()

    files = find_files_without_eof(args.root)
    if not files:
        print("All files have an empty line at EOF.")
        return
    print("Files without empty line at EOF:")
    for f in files:
        print(f)
    if args.append:
        for f in files:
            append_empty_line(f)
        print("Appended empty line to listed files.")
    else:
        print("No changes made. Use --append to fix files.")

if __name__ == '__main__':
    main()