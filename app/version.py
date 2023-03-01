import pathlib
import re

version_rexp = re.compile(r'^\[(\d+.\d+.\d+\w*)\]', re.MULTILINE)
change_log = pathlib.Path(__file__).parent.joinpath('docs', 'source', 'changelog.rst').read_text('utf8')
try:
    VERSION = version_rexp.findall(change_log)[0]
except IndexError:
    raise SystemError('Fail to parse version from changelog.rst')

if __name__ == '__main__':
    print(VERSION)
