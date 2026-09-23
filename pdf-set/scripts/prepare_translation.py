"""Prepare numbered translation files in one local, non-network operation."""
import argparse
from pathlib import Path
import re

from translation_preparation import pack_paragraphs, process_text, split_paragraphs, read_single_path


def canonical(text):
    return re.sub(r'\s+', '', re.sub(r'</?sup>', '', text, flags=re.I))


def validate_content(original, processed):
    if canonical(original) != canonical(processed):
        raise ValueError('Preparation changed source text; no files written')
    for paragraph in re.split(r'\n\s*\n', processed):
        depth = 0
        for tag in re.finditer(r'<(/?)sup>', paragraph, re.I):
            depth += -1 if tag.group(1) else 1
            if depth < 0 or depth > 1:
                raise ValueError('Unbalanced or nested sup tags; no files written')
        if depth:
            raise ValueError('Unclosed sup tag; no files written')


def prepare(input_file, split_dir, output_dir, file_chars=40000,
            paragraph_chars=250, buffer_chars=200):
    input_file, split_dir, output_dir = map(Path, (input_file, split_dir, output_dir))
    if file_chars <= 0 or paragraph_chars <= 0 or buffer_chars < 0:
        raise ValueError('Character targets must be positive; buffer must be non-negative')
    paths = [input_file.resolve(), split_dir.resolve(), output_dir.resolve()]
    if paths[1] == paths[2] or any(paths[0].is_relative_to(p) for p in paths[1:]):
        raise ValueError('Input file and the two output directories must be distinct')
    # Do not mutate numbered inputs used by an existing translation resume cursor.
    # Explicit new directories are the safe way to test or migrate an old book.
    for directory in (split_dir, output_dir):
        if directory.exists() and any(directory.iterdir()):
            raise FileExistsError(f'Output directory is not empty: {directory}. Use new output directories; existing translation inputs are not overwritten.')
    source = input_file.read_text(encoding='utf-8-sig')
    if not source.strip():
        raise ValueError('Input book is empty')
    chunks = pack_paragraphs(split_paragraphs(source), file_chars)
    prepared = []
    for chunk in chunks:
        raw = '\n\n'.join(chunk).rstrip() + '\n'
        formatted = process_text(raw, paragraph_chars, buffer_chars)
        validate_content(raw, formatted)
        prepared.append((raw, formatted))
    if canonical(source) != canonical(''.join(raw for raw, _ in prepared)):
        raise ValueError('File grouping changed source text; no files written')
    for directory in (split_dir, output_dir):
        directory.mkdir(parents=True, exist_ok=True)
    for index, (raw, formatted) in enumerate(prepared, 1):
        for directory, content in ((split_dir, raw), (output_dir, formatted)):
            with (directory / f'{index}.md').open('x', encoding='utf-8', newline='\n') as stream:
                stream.write(content)
    print(f'Prepared {len(prepared)} files: {output_dir}')
    return prepared


def main():
    parser = argparse.ArgumentParser(description='Split and typeset a book for translation in one step.')
    for name, default, help_text in (
        ('base-dir', '.', 'Book directory (default: current directory)'),
        ('book-name', None, 'Book name (default: directory name)'),
        ('input-file', None, 'Book Markdown path'),
        ('split-dir', None, 'Intermediate directory (default: translate-split)'),
        ('output-dir', None, 'Translation input directory (default: translate-typeset)'),
    ):
        parser.add_argument('--' + name, default=default, help=help_text)
        parser.add_argument('--' + name + '-from', help='UTF-8 file containing the path/name')
    parser.add_argument('--file-chars', type=int, default=40000)
    parser.add_argument('--max-chars', type=int, default=250, help='Paragraph target, not a hard limit')
    parser.add_argument('--buffer-chars', type=int, default=200)
    args = parser.parse_args()
    for name in ('base_dir', 'book_name', 'input_file', 'split_dir', 'output_dir'):
        from_file = getattr(args, name + '_from')
        if from_file:
            value = read_single_path(from_file)
            if not value:
                parser.error(f'Empty path file: {from_file}')
            setattr(args, name, value)
    base = Path(args.base_dir).resolve()
    name = args.book_name or base.name
    prepare(args.input_file or base / f'{name}.md',
            args.split_dir or base / 'translate-split',
            args.output_dir or base / 'translate-typeset',
            args.file_chars, args.max_chars, args.buffer_chars)


if __name__ == '__main__':
    main()
