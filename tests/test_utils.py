
from fnmatch import fnmatch
from os import listdir
from os.path import dirname, join
from re import sub

import rover
from rover.config import BaseConfig
from rover.args import Arguments, MSEEDDIR, TEMPDIR, LOGDIR, LEAP, MSEEDCMD
from rover.ingest import Ingester
from rover.logs import init_log
from rover.sqlite import init_db
from rover.utils import create_parents, canonify


class TestArgs:

    def __init__(self, **kargs):
        self._kargs = kargs
        self._argparser = Arguments()

    def __getattr__(self, item):
        if item in self._kargs:
            value = self._kargs[item]
        else:
            value = self._argparser.get_default(item)
        return value


def _(text):
    return sub(r'\-', '_', text)


class TestConfig(BaseConfig):

    def __init__(self, dir, **kargs):
        kargs = dict(kargs)
        kargs[_(MSEEDDIR)] = join(dir, 'mseed')
        kargs[_(TEMPDIR)] = join(dir, 'tmp')
        kargs[_(LOGDIR)] = join(dir, 'logs')
        root = find_root()
        kargs[_(MSEEDCMD)] = join(root, '..', 'mseedindex', 'mseedindex')
        kargs[_(LEAP)] = False
        args = TestArgs(**kargs)
        log, log_path = init_log(args.log_dir, 7, 1, 5, 0, 'test', args.leap, 0)
        dbpath = join(canonify(args.mseed_dir), 'index.sql')
        create_parents(dbpath)
        super().__init__(log, log_path, args, init_db(dbpath, log), dir)


def find_root():
    return dirname(dirname(rover.__file__))


def assert_files(dir, *files):
    found = listdir(dir)
    if 'index.sql' in found:
        found.remove('index.sql')
    assert len(files) == len(found), 'Found %d files in %s (not %d)' % (len(found), dir, len(files))
    for file in found:
        ok = False
        for glob in files:
            if fnmatch(file, glob):
                ok = True
        if not ok:
            raise Exception('Unexpected file: "%s"', file)


def ingest_and_index(dir, data, **opts):
    config = TestConfig(dir, **opts)
    ingester = Ingester(config)
    ingester.run(data)
    return config


