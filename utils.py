import csv
import logging
import chardet


logger = logging.getLogger()


CSV_SAMPLE_SIZE = 5000


def get_file_encoding(filename):
    with open(filename, 'rb') as f:
        result = chardet.detect(f.read(CSV_SAMPLE_SIZE))
        return result['encoding']


def sniff_file_dialect(filename, encoding):
    with open(filename, encoding=encoding) as csvfile:
        dialect = csv.Sniffer().sniff(csvfile.read(CSV_SAMPLE_SIZE))
    return dialect


def read_csv_file(filename, delimiter=None):
    encoding = get_file_encoding(filename)
    if delimiter:
        reader_kwargs = dict(delimiter=delimiter)
    else:
        reader_kwargs = dict(dialect=sniff_file_dialect(filename, encoding))

    with open(filename, encoding=encoding) as f:
        yield from csv.DictReader(f, **reader_kwargs)
