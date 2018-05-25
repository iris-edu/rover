
from .summary import Summarizer
from .daemon import Starter, Stopper
from .args import RESET_CONFIG, INDEX, INGEST, LIST_INDEX, \
    RETRIEVE, HELP, SUBSCRIBE, DOWNLOAD, LIST_RETRIEVE, START, STOP, LIST_SUBSCRIPTIONS, UNSUBSCRIBE, DAEMON, \
    MULTIPROCESS, DEV, SUMMARY
from .config import Config, ConfigResetter
from .download import Downloader
from .index import Indexer, IndexLister
from .ingest import Ingester
from .process import Processes
from .retrieve import Retriever, ListRetriever
from .subscribe import Subscriber, SubscriptionLister, Unsubscriber


COMMANDS = {
    RESET_CONFIG: (ConfigResetter, 'Reset the configuration'),
    INDEX: (Indexer, 'Index the local store'),
    INGEST: (Ingester, 'Ingest data from a file into the local store'),
    LIST_INDEX: (IndexLister, 'List the contents of the local store'),
    DOWNLOAD: (Downloader, 'Download data from a remote service'),
    RETRIEVE: (Retriever, 'Download, ingest and index missing data'),
    LIST_RETRIEVE: (ListRetriever, 'Show what data "rover retrieve" will download'),
    START: (Starter, 'Start the background daemon'),
    STOP: (Stopper, 'Stop the background daemon'),
    SUBSCRIBE: (Subscriber, 'Add a subscription'),
    SUMMARY: (Summarizer, 'Update summary table'),
    LIST_SUBSCRIPTIONS: (SubscriptionLister, 'List the subscriptions'),
    UNSUBSCRIBE: (Unsubscriber, 'Remove a subscription')
}


def execute(command, config):
    from .help import Helper   # avoid import loop
    if not command:
        command = 'help'
    commands = dict(COMMANDS)
    commands[HELP] = (Helper, '')
    if command in commands:
        commands[command][0](config).run(config.args)
    else:
        raise Exception('Unknown command %s' % command)


def main():
    config = None
    try:
        config = Config()
        processes = Processes(config)
        if not (config.arg(DAEMON) or config.arg(MULTIPROCESS)):
            processes.add_singleton_me('rover')
        try:
            execute(config.command, config)
        finally:
            processes.remove_me()
    except Exception as e:
        if config and config.log:
            config.log.error(str(e))
            if config.command in COMMANDS:
                config.log.info('See "rover help %s"' % config.command)
            elif config.command != HELP:
                config.log.info('See "rover help help" for a list of commands')
            if not config or not config._args or config.arg(DEV):
                raise e
        else:
            raise e
