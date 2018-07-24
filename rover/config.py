
from argparse import Namespace
from genericpath import exists
from os import makedirs, getcwd
from os.path import isabs, join, realpath, abspath, expanduser, dirname
from re import compile, sub

from .args import Arguments, LOGDIR, LOGSIZE, LOGCOUNT, LOGVERBOSITY, VERBOSITY, LOGUNIQUE, LOGUNIQUEEXPIRE, \
    FILEVAR, DIRVAR, TEMPDIR, DATADIR, COMMAND, unbar, DYNAMIC_ARGS, INIT_REPOSITORY, m, F, FILE
from .logs import init_log
from .sqlite import init_db
from .utils import safe_unlink, canonify

"""
Package common data used in all/most classes (db connection, lgs and parameters).
"""


class BaseConfig:
    """
    The configuration of the system (log, parameters, database).

    The Config subclass provides a different constructor.
    """

    def __init__(self, log, log_path, args, db, configdir):
        self.log = log
        self.log_path = log_path
        self._args = args
        self.db = db
        self._configdir = configdir
        self.args = args.args
        self.command = args.command

    def arg(self, name, depth=0):
        """
        Look-up an arg with variable substitution.
        """
        name = sub('-', '_', name)
        if depth > 10:
            raise Exception('Circular definition involving %s' % name)
        try:
            value = getattr(self._args, name)
        except:
            raise Exception('Parameter %s does not exist' % name)
        while True:
            try:
                matchvar = compile(r'(.*(?:^|[^\$]))\${(\w+)}(.*)').match(value)
            except:
                # not a string variable
                break
            if matchvar:
                if matchvar.group(2) == 'CONFIGDIR':
                    inner = self._configdir
                else:
                    inner = self.arg(matchvar.group(2), depth=depth+1)
                try:
                    value = matchvar.group(1) + inner + matchvar.group(3)
                except:
                    raise Exception('String substitution only works with string parameters (%s)' % name)
            else:
                value = sub(r'\$\$', '$', value)
                break
        return value

    def absolute(self):
        """
        Clone this configuration, making file and directories absolute.  Used before we write a
        config for a sub-process, because it may be written in a different location to the original,
        so relative paths will change value (yeah that was a fun bug to fix).
        """
        args = {}
        for action in Arguments()._actions:
            name = action.dest
            if unbar(name) not in DYNAMIC_ARGS:   # todo - should this include FILE?
                if action.metavar in (DIRVAR, FILEVAR):
                    value = self.path(name)
                else:
                    value = self.arg(name)
                args[name] = value
        return BaseConfig(self.log, self.log_path, Namespace(**args), self.db, self._configdir)

    def path(self, name):
        """
        Paths have an implicit configdir if they are relative.
        """
        path = expanduser(self.arg(name))
        if not isabs(path):
            path = join(self._configdir, path)
        return realpath(abspath(path))

    def dir(self, name, create_dir=True):
        """
        Ensure the directory exists.
        """
        path = self.path(name)
        if create_dir and not exists(path):
            makedirs(path)
        return path

    def file(self, name, create_dir=True):
        """
        Ensure the enclosing directory exists.
        """
        path = self.path(name)
        dir = dirname(path)
        if create_dir and not exists(dir):
            makedirs(dir)
        return path


def mseed_db(config):
    return join(config.dir(DATADIR), 'index.sql')


class Config(BaseConfig):
    """
    An alternative constructor for BaseConfig (bootstrap from command line).
    """

    def __init__(self):
        # there's a pile of ugliness here so that we delay error handling until we have logs.
        # see also comments in parse_args.
        argparse = Arguments()
        args, self.__config = argparse.parse_args()
        self.__error = self.__config and not exists(self.__config)  # see logic in parse_args
        full_config = self.__config and not self.__error
        # this is a bit ugly, but we need to use the base methods to construct the log and db
        # note that log is not used in base!
        super().__init__(None, None, args, None, dirname(self.__config) if full_config else None)
        self.log, self.log_path = \
            init_log(self.dir(LOGDIR) if full_config else None, self.arg(LOGSIZE), self.arg(LOGCOUNT),
                     self.arg(LOGVERBOSITY), self.arg(VERBOSITY), self.arg(COMMAND) or 'rover',
                     self.arg(LOGUNIQUE), self.arg(LOGUNIQUEEXPIRE))
        if full_config:  # if initializing, we have no database...
            self.db = init_db(mseed_db(self), self.log)

    def lazy_validate(self):
        # allow Config() to be created so we can log on error
        if self.__error:
            self.log.error('You may need to configure the local store using `rover %s %s %s`).' %
                           (INIT_REPOSITORY, m(F), self.__config))
            raise Exception('Could not find configuration file (%s)' % self.__config)

    def set_configdir(self, configdir):
        """
        Called only from initialisation, when using a new config dir.
        """
        self._configdir = configdir


class RepoInitializer:
    """
### Init Repository

    rover init-repository [directory]

Creates the expected directory structure and writes default values to the
config file.

To avoid over-writing data, it is an error if the config file, data directory
or log directory already exist.

##### Significant Parameters

@verbosity
@log-dir
@log-verbosity

##### Examples

    rover init-repository

will create the local store in the current directory.

    rover init-repository ~/rover

will create the local store in ~/rover

    """

    def __init__(self, config):
        self.__config = config
        self.__log = config.log
        self.__args = config._args

    def run(self, args):
        self.__validate(args)
        self.__check_empty()
        self.__create()

    def __validate(self, args):
        if not args:
            configdir = getcwd()
        elif len(args) == 1:
            configdir = args[0]
        else:
            raise Exception('Command %s takes at most one argument - the directory to initialise' %
                            INIT_REPOSITORY)
        configdir = canonify(configdir)
        self.__config.set_configdir(configdir)
        file = self.__config.file(FILE, create_dir=False)
        if not file.startswith(configdir):
            raise Exception('A configuration file was specified outside the local store (%s)' % file)
        return configdir

    def __check_empty(self):
        data_dir = self.__config.dir(DATADIR, create_dir=False)
        if exists(data_dir):
            raise Exception('The data directory already exists (%s)' % data_dir)
        config_file = self.__config.file(FILE, create_dir=False)
        if exists(config_file):
            raise Exception('The configuration file already exists (%s)' % config_file)
        log_dir = self.__config.dir(LOGDIR, create_dir=False)
        if exists(log_dir):
            raise Exception('The log directory already exists (%s)' % log_dir)
        # no need to check database because that's inside the data dir

    def __create(self):
        config_file = self.__config.file(FILE)
        self.__log.info('Writing new config file "%s"' % config_file)
        Arguments().write_config(config_file, self.__args)
        self.__config.dir(DATADIR)
        # we don't really need this
        init_db(mseed_db(self.__config), self.__log)
        # todo - log to memory and dump log in logdir


def write_config(config, filename, **kargs):
    """
    Write a config file for sub-processes.
    """
    args = config.absolute()._args
    temp_dir = config.dir(TEMPDIR)
    config_path = join(temp_dir, filename)
    safe_unlink(config_path)
    Arguments().write_config(config_path, args, **kargs)
    return config_path
