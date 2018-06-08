
from os.path import exists, join, dirname
from smtplib import SMTP_PORT
from textwrap import dedent
import sys
from re import sub, compile

from argparse import ArgumentParser, Action, RawDescriptionHelpFormatter

from .utils import create_parents, canonify, check_cmd


"""
Command line / file configuration parameters.
"""


# commands
DAEMON = 'daemon'
DOWNLOAD = 'download'
HELP = 'help'
INDEX = 'index'
INGEST = 'ingest'
LIST_INDEX = 'list-index'
LIST_RETRIEVE = 'list-retrieve'
LIST_SUBSCRIBE = 'list-subscribe'
LIST_SUMMARY = 'list-summary'
RETRIEVE = 'retrieve'
START = 'start'
STOP = 'stop'
STATUS = 'status'
SUMMARY = 'summary'
SUBSCRIBE = 'subscribe'
RESUBSCRIBE = 'resubscribe'
UNSUBSCRIBE = 'unsubscribe'
WEB = 'web'
WRITE_CONFIG = 'write-config'


# flag negation
NO = '--no-'


# parameters
ALL = 'all'
ARGS = 'args'
AVAILABILITYURL = 'availability-url'
COMMAND = 'command'
DATASELECTURL = 'dataselect-url'
DELETEFILES = 'delete-files'
DOWNLOADWORKERS = 'download-workers'
DEV = 'dev'
EMAIL = 'email'
EMAILFROM = 'email-from'
F, FILE = 'f', 'file'
FORCEFAILURES = 'force-failures'
FORCEREQUEST = 'force-request'
HTTPBINDADDRESS = 'http-bind-address'
HTTPPORT = 'http-port'
HTTPRETRIES = 'http-retries'
HTTPTIMEOUT = 'http-timeout'
LEAP = 'leap'
LEAPEXPIRE = 'leap-expire'
LEAPFILE = 'leap-file'
LEAPURL = 'leap-url'
LOGDIR = 'log-dir'
LOGVERBOSITY = 'log-verbosity'
LOGSIZE = 'log-size'
LOGUNIQUE = 'log-unique'
LOGUNIQUEEXPIRE = 'log-unique-expire'
LOGCOUNT = 'log-count'
MDFORMAT = 'md-format'
MSEEDDIR = 'mseed-dir'
MSEEDINDEXCMD = 'mseedindex-cmd'
MSEEDINDEXWORKERS = 'mseedindex-workers'
POSTSUMMARY = 'post-summary'
PREINDEX = 'pre-index'
RECHECKPERIOD = 'recheck-period'
RECURSE = "recurse"
ROVERCMD = 'rover-cmd'
SMTPADDRESS = 'smtp-address'
SMTPPORT = 'smtp-port'
SUBSCRIPTIONSDIR = 'subscriptions-dir'
TEMPDIR = 'temp-dir'
TEMPEXPIRE = 'temp-expire'
TIMESPANTOL = 'timespan-tol'
V, VERBOSITY = 'v', 'verbosity'


# default values (for non-boolean parameters)
DEFAULT_AVAILABILITYURL = 'http://service.iris.edu/irisws/availability/1/query'
DEFAULT_DATASELECTURL = 'http://service.iris.edu/fdsnws/dataselect/1/query'
DEFAULT_DOWNLOADWORKERS = 10
DEFAULT_EMAILFROM = 'noreply@rover'
DEFAULT_FILE = join('~', 'rover', 'config')
DEFAULT_FORCEFAILURES = 0
DEFAULT_HTTPBINDADDRESS = '127.0.0.1'
DEFAULT_HTTPPORT = 8000
DEFAULT_HTTPRETRIES = 3
DEFAULT_HTTPTIMEOUT = 60
DEFAULT_LEAPEXPIRE = 30
DEFAULT_LEAPFILE = 'leap-seconds.lst'
DEFAULT_LEAPURL = 'http://www.ietf.org/timezones/data/leap-seconds.list'
DEFAULT_LOGDIR = 'logs'
DEFAULT_LOGVERBOSITY = 5
DEFAULT_LOGSIZE = 6
DEFAULT_LOGCOUNT = 10
DEFAULT_LOGUNIQUE_EXPIRE = 7
DEFAULT_MSEEDDIR = 'mseed'
DEFAULT_MSEEDINDEXCMD = 'mseedindex'
DEFAULT_MSEEDINDEXWORKERS = 10
DEFAULT_RECHECKPERIOD = 12
DEFAULT_ROVERCMD = 'rover'
DEFAULT_SMTPADDRESS = 'localhost'
DEFAULT_SMTPPORT = SMTP_PORT
DEFAULT_SUBSCRIPTIONSDIR = 'subscriptions'
DEFAULT_TEMPDIR = 'tmp'
DEFAULT_TEMPEXPIRE = 1
DEFAULT_TIMESPANTOL = 1.5
DEFAULT_VERBOSITY = 4

DIRVAR = 'DIR'
FILEVAR = 'FILE'


def parse_bool(value):
    """
    Treat caseless true, yes and on and true, anything else as false.
    """
    if not value:
        value = 'False'
    value = value.lower()
    return value in ('true', 'yes', 'on')


class StoreBoolAction(Action):
    """
    We need a special action for booleans because we must covertly
    parse them as '--foo True' even though the user only types '--foo'.
    """

    def __init__(self,
                 option_strings,
                 dest,
                 default=None,
                 choices=None,
                 required=False,
                 help=None,
                 metavar=None):
        super().__init__(
            option_strings=option_strings,
            dest=dest,
            nargs=1,
            const=None,
            default=default,
            type=parse_bool,
            choices=choices,
            required=required,
            help=help,
            metavar=metavar)

    def __call__(self, parser, namespace, values, option_string=None):
        setattr(namespace, self.dest, values[0])


def m(string): return '-' + string
def mm(string): return '--' + string


class Arguments(ArgumentParser):
    """
    Extend the standard arg parsing to:
    * scan initial args to find if config file location specifed
    * if config file is missing, generate defaults
    * read config file before command line args

    To do this correctly for boolean flags (which behave differently on
    the command line and in the config file) we also have to pre-process those.

    The aim is to:
    * have (almost) all config duplcaited, both in config and command line
    * have default config be self-documenting and discoverable
    """

    def __init__(self):
        super().__init__(fromfile_prefix_chars='@', prog='rover',
                         formatter_class=RawDescriptionHelpFormatter,
                         description='ROVER: Retrieval of Various Experiment data Robustly',
                         epilog=dedent('''
                         Flags can be negated (eg --no-daemon).
                         Defaults are read from the configuration file (%s).
                         Type "rover help" for more information on available commands.''' % DEFAULT_FILE))
        self.register('action', 'store_bool', StoreBoolAction)

        # operation details
        self.add_argument(m(F), mm(FILE), default=DEFAULT_FILE, help='specify configuration file')
        # metavar must be empty string to hide value since user options
        # are flags that are automatically given values below.
        self.add_argument(mm(DEV), default=False, action='store_bool', help='development mode (show exceptions)?', metavar='')
        self.add_argument(mm(DELETEFILES), default=True, action='store_bool', help='delete temporary files?', metavar='')
        self.add_argument(mm(MDFORMAT), default=False, action='store_bool', help='display help in markdown format?', metavar='')

        # the local store
        self.add_argument(mm(MSEEDDIR), default=DEFAULT_MSEEDDIR, action='store', help='the local store - mseed data, index.sql', metavar=DIRVAR)

        # retrieval
        self.add_argument(mm(TIMESPANTOL), default=DEFAULT_TIMESPANTOL, action='store', help='fractional tolerance for overlapping timespans', metavar='SAMPLE', type=float)
        self.add_argument(mm(DOWNLOADWORKERS), default=DEFAULT_DOWNLOADWORKERS, action='store', help='number of download instances to run', metavar='N', type=int)
        self.add_argument(mm(ROVERCMD), default=DEFAULT_ROVERCMD, action='store', help='command to run rover', metavar='CMD')
        self.add_argument(mm(PREINDEX), default=True, action='store_bool', help='index before retrieval?', metavar='')
        self.add_argument(mm(INGEST), default=True, action='store_bool', help='call ingest after retrieval?', metavar='')
        self.add_argument(mm(INDEX), default=True, action='store_bool', help='call index after ingest?', metavar='')
        self.add_argument(mm(POSTSUMMARY), default=True, action='store_bool', help='call summary after retrieval?', metavar='')

        # downloads
        self.add_argument(mm(AVAILABILITYURL), default=DEFAULT_AVAILABILITYURL, action='store', help='availability service url', metavar=DIRVAR)
        self.add_argument(mm(DATASELECTURL), default=DEFAULT_DATASELECTURL, action='store', help='dataselect service url', metavar=DIRVAR)
        self.add_argument(mm(TEMPDIR), default=DEFAULT_TEMPDIR, action='store', help='temporary storage for downloads', metavar=DIRVAR)
        self.add_argument(mm(TEMPEXPIRE), default=DEFAULT_TEMPEXPIRE, action='store', help='number of days before deleting temp files', metavar='DAYS', type=int)
        self.add_argument(mm(HTTPTIMEOUT), default=DEFAULT_HTTPTIMEOUT, action='store', help='timeout for HTTP requests', metavar='SECS', type=int)
        self.add_argument(mm(HTTPRETRIES), default=DEFAULT_HTTPRETRIES, action='store', help='max retries for HTTP requests', metavar='N', type=int)
        self.add_argument(mm(FORCEFAILURES), default=DEFAULT_FORCEFAILURES, action='store', help='force failures for testing (dangerous)', metavar='PERCENT', type=int)

        # index
        self.add_argument(mm(ALL), default=False, action='store_bool', help='process all files (not just modified)?', metavar='')
        self.add_argument(mm(RECURSE), default=True, action='store_bool', help='when given a directory, process children?', metavar='')

        # subscription
        self.add_argument(mm(SUBSCRIPTIONSDIR), default=DEFAULT_SUBSCRIPTIONSDIR, action='store', help='directory for subscriptions', metavar=DIRVAR)
        self.add_argument(mm(RECHECKPERIOD), default=DEFAULT_RECHECKPERIOD, action='store', help='time between availabilty checks', metavar='HOURS', type=int)
        self.add_argument(mm(FORCEREQUEST), default=False, action='store_bool', help='skip overlap checks (dangerous)?', metavar='')

        # logging
        self.add_argument(mm(LOGDIR), default=DEFAULT_LOGDIR, action='store', help='directory for logs', metavar=DIRVAR)
        self.add_argument(mm(LOGUNIQUE), default=False, action='store_bool', help='unique log names (with PIDs)?', metavar='')
        self.add_argument(mm(LOGUNIQUEEXPIRE), default=DEFAULT_LOGUNIQUE_EXPIRE, action='store', help='number of days before deleting unique logs', metavar='DAYS', type=int)
        self.add_argument(mm(LOGVERBOSITY), default=DEFAULT_LOGVERBOSITY, action='store', help='log verbosity (0-5)', metavar='V', type=int)
        self.add_argument(mm(LOGSIZE), default=DEFAULT_LOGSIZE, action='store', help='maximum log size (1-10)', metavar='N', type=int)
        self.add_argument(mm(LOGCOUNT), default=DEFAULT_LOGCOUNT, action='store', help='maximum number of logs', metavar='N', type=int)
        self.add_argument(mm(VERBOSITY), default=DEFAULT_VERBOSITY, action='store', help='console verbosity (0-5)', metavar='V', type=int)

        # mseedindex
        self.add_argument(mm(MSEEDINDEXCMD), default=DEFAULT_MSEEDINDEXCMD, action='store', help='mseedindex command', metavar='CMD')
        self.add_argument(mm(MSEEDINDEXWORKERS), default=DEFAULT_MSEEDINDEXWORKERS, action='store', help='number of mseedindex instances to run', metavar='N', type=int)

        # leap seconds
        self.add_argument(mm(LEAP), default=True, action='store_bool', help='use leapseconds file?', metavar='')
        self.add_argument(mm(LEAPEXPIRE), default=DEFAULT_LEAPEXPIRE, action='store', help='number of days before refreshing file', metavar='N', type=int)
        self.add_argument(mm(LEAPFILE), default=DEFAULT_LEAPFILE, action='store', help='file for leapsecond data', metavar=FILEVAR)
        self.add_argument(mm(LEAPURL), default=DEFAULT_LEAPURL, action='store', help='URL for leapsecond data', metavar='URL')

        # user feedback
        self.add_argument(mm(WEB), default=True, action='store_bool', help='auto-start the download progress web server?', metavar='')
        self.add_argument(mm(HTTPBINDADDRESS), default=DEFAULT_HTTPBINDADDRESS, action='store', help='bind address for HTTP server', metavar='ADDRESS')
        self.add_argument(mm(HTTPPORT), default=DEFAULT_HTTPPORT, action='store', help='port for HTTP server', metavar='N', type=int)
        self.add_argument(mm(EMAIL), default='', action='store', help='address for completion status', metavar='ADDRESS')
        self.add_argument(mm(EMAILFROM), default=DEFAULT_EMAILFROM, action='store', help='from address for email', metavar='ADDRESS')
        self.add_argument(mm(SMTPADDRESS), default=DEFAULT_SMTPADDRESS, action='store', help='address of SMTP server', metavar='ADDRESS')
        self.add_argument(mm(SMTPPORT), default=DEFAULT_SMTPPORT, action='store', help='port for SMTP server', metavar='N', type=int)

        # commands / args
        self.add_argument(COMMAND, metavar='COMMAND', nargs='?', help='use "help" for further information')
        self.add_argument(ARGS, nargs='*', help='command arguments (depend on the command)')

    def parse_args(self, args=None, namespace=None):
        """
        Intercept normal arg parsing to:
        * scan initial args to find if config file location specified
        * if config file is missing, generate defaults
        * read config file before command line args
        """
        if args is None:
            args = sys.argv[1:]
        args = self.__preprocess_booleans(args)
        config, args = self.__extract_config(args)
        if not exists(config):
            self.write_config(config, None)
        args = self.__patch_config(args, config)
        return super().parse_args(args=args, namespace=namespace), dirname(config)

    def __preprocess_booleans(self, args):
        """
        Replace --foo with '--foo True' and --no-foo with '--foo False'.
        This makes the interface consistent with the config file (which has
        the format 'foo=True') while letting the user type simple flags.
        """
        indices = []
        for (index, arg) in enumerate(args):
            if arg.startswith(NO):
                arg = '--' + arg[5:]
            for action in self._actions:
                name = '--' + sub('_', '-', action.dest)
                if name == arg and type(action) is StoreBoolAction:
                    indices.append(index)
        for index in reversed(indices):
            negative = args[index].startswith(NO)
            if negative:
                args[index] = mm(args[index][5:])
            args.insert(index+1, str(not negative))
        return args

    def __extract_config(self, args):
        """
        Find the config file, if given, otherwise use the default.
        This must be done before argument parsing because we need
        to add the contents of the file to the arguments (that is
        how the file is read).
        """
        config, indices = None, []
        # find all occurences of file params, saving last
        for (index, arg) in enumerate(args):
            # must skip file name
            if arg in ('-f', '--file') and (not indices or index+1 != indices[-1]):
                if index+1 >= len(args):
                    raise Exception('No argument for %s' % arg)
                indices.append(index)
                config = args[index+1]
        # remove all occurrences
        for index in reversed(indices):
            args = args[:index] + args[index+2:]
        if not config:
            config = self.get_default(FILE)
        config = canonify(config)
        # include config flag so that it is set correctly, even if the extracted
        # value is the one that is used here
        return config, [mm(FILE), config] + args

    def write_config(self, path, args, **kargs):
        """
        If the config file is missing, fill it with values.
        If args is None, defaults are used.
        If keywords are specified, they over-ride defaults and args.
        """
        create_parents(path)
        with open(path, 'w') as out:
            for action in self._actions:
                name, default = action.dest, action.default
                if name not in (HELP, FILE):
                    if default is not None:
                        if name in kargs:
                            value = kargs[name]
                        elif args is not None:  # py2.7 no __bool__ on values
                            value = getattr(args, name)
                        else:
                            value = default
                        if action.help:
                            out.write('# %s\n' % action.help)
                        out.write('%s=%s\n' % (sub('_', '-', name), value))

    def __patch_config(self, args, config):
        """
        Force the reading of the config file (ignored for reset-config
        because we may be rewriting it because it has errors).
        """
        if WRITE_CONFIG in args:
            return args
        else:
            return ['@'+config] + args

    def convert_arg_line_to_args(self, arg_line):
        '''
        Parse a line from the config file, constructing '--name value" from name=value
        and ignoring comments.
        '''
        arg_line = arg_line.strip()
        if arg_line.startswith('#'):
            return []
        elif '=' in arg_line:
            name, value = arg_line.split('=', 1)
            return [mm(name), value]
        else:
            raise Exception('Cannot parse "%s"' % arg_line)

    @staticmethod
    def __document_action(action):
        name = sub('_', '-', action.dest)
        default = action.default
        help = action.help
        if name == FILE:
            name += ' / -f'
        elif name == HELP:
            name += ' / -h'
            default = False
            help = help.replace('this', 'the')
        if help:
            help = help[0].upper() + help[1:]
        return name, default, help

    def __documentation(self, name):
        for action in self._actions:
            if name == sub('_', '-', action.dest):
                return self.__document_action(action)
        raise Exception('Unknown parameter %s' % name)

    def __documentation_names(self):
        for action in self._actions:
            name = sub('_', '-', action.dest)
            if name not in (COMMAND, ARGS):
                yield name

    NAME_WIDTH = 19
    DEFAULT_WIDTH = 20
    DESCRIPTION_WIDTH = 30

    def __print_docs_table_row(self, name, default, description):
        print('| %-*s | %-*s | %-*s |' %(self.NAME_WIDTH, name, self.DEFAULT_WIDTH, default, self.DESCRIPTION_WIDTH, description))

    def print_docs_header(self):
        """
        Print the table header row.
        """
        self.__print_docs_table_row(' Name', 'Default', 'Description')
        self.__print_docs_table_row('-' * self.NAME_WIDTH, '-' * self.DEFAULT_WIDTH, '-' * self.DESCRIPTION_WIDTH)

    def print_docs_row_md(self, name):
        """
        Print a table entry for the give argument, markdown formatted
        """
        self.__print_docs_table_row(*self.__documentation(name))

    def print_docs_row_text(self, name):
        """
        Print a table entry for the give argument, text formatted
        """
        name, default, description = self.__documentation(name)
        left = '| %-*s | %-*s' % (self.NAME_WIDTH, name, self.DEFAULT_WIDTH, default)
        right = ' | %-*s |' % (self.DESCRIPTION_WIDTH, description)
        if len(left + right) > 79:
            print('%s\n%77s |' % (left, description))
        else:
            print(left + right)

    def __print_docs_rows_md(self):
        for name in self.__documentation_names():
           self.print_docs_row_md(name)

    def print_docs_table_md(self):
        """
        Print all arguments in a table (called externally from python to generate docs).
        """
        self.print_docs_header()
        self.__print_docs_rows_md()


def fail_early(config):
    """
    Check commands so that we fail early.
    """
    check_cmd(config, ROVERCMD, 'rover')
    check_cmd(config, MSEEDINDEXCMD, 'mseedindex')


class UserFeedback:
    """
    Display info on web and email status.
    """
    # can't put this in utils because we get a dependency loop.

    def __init__(self, config):
        self._log = config.log
        self._web = config.arg(WEB)
        self._url = 'http://%s:%s' % (config.arg(HTTPBINDADDRESS), config.arg(HTTPPORT))
        self._email = config.arg(EMAIL)

    def display_feedback(self):
        if self._web:
            self._log.info('Status available at %s' % self._url)
        else:
            self._log.info('No web status (see %s configuration parameter)' % mm(WEB))
        if self._email:
            self._log.info('Email status will be sent to %s' % self._email)
        else:
            self._log.info('No email status (see %s configuration parameter)' % mm(EMAIL))
