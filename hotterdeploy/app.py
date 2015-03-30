#!/bin/python
'''
author: Jelle Hellemans
copyright: Copyright (C) 2014 Jelle Hellemans

HotterDeployer is a Liferay utility meant to ease development.

It will monitor the resources (jsp,css,js) in your workspace for deployed
portlets and hot-copy them on changes, without the need for a deployment.

It also offers an alternative to the liferay 'deploy' directory,
called 'hotterdeploy' which can detect conflicting jar changes and will
automatically undeploy and redeploy the affected portlet.
(Change the liferay.auto.deploy.dir property in your settings.xml accordingly
 e.g. <liferay.auto.deploy.dir>
        /liferay-developer-studio/liferay-portal-6.2-ee-sp3/hotterdeploy
      </liferay.auto.deploy.dir>)
'''

import argparse
import os
import weakref
import logging
from logging.handlers import BufferingHandler

from watchdog.observers import Observer
from watchdog.observers.polling import PollingObserverVFS
from watchdog.utils import stat as default_stat

from livereload import Server

from .utilities import (
    scan_working_directory_for_portlet_contexts,
    scan_tomcat_temporary_directory,
    scan_tomcat_webapps_directory,
)
from .app_handlers import (
    OnTempDeployHandler,
    OnWebappsDeployHandler,
    WorkSpaceHandler,
    OnFileChangedHandler,
    OnClassChangedHandler,
    OnDeployHandler,
)


LOG = logging.getLogger(__name__)


def listdir(directory):
    paths = os.listdir(directory)
    ret = []
    patterns = '.java,.zip,.pptx'.split(',')
    dir_Names = ['test', '.svn', '.settings', '.metadata']
    for path in paths:
        if all(map(lambda x: path != x, dir_Names)):
            if path.find('.') == -1:
                ret.append(path)
            else:
                if not any(map(lambda x: path.endswith(x), patterns)):
                    ret.append(path)
                else:
                    pass
                    # LOG.debug('Ignoring {0}'.format(path))
    return ret


class HotterDeployer(object):
    def __init__(
            self,
            workspace_directory,
            tomcat_directory,
            hotterdeploy_dir,
            liferay_context,
            do_polling,
            statics_directory
            ):
        self.do_polling = do_polling
        self.workspace_directory = workspace_directory
        self.tomcat_directory = tomcat_directory
        self.liferay_context = liferay_context
        self.statics_directory = statics_directory
        self.portlets = {}
        self.themes = {}
        self.deploys = {}

        if hotterdeploy_dir == '':
            self.hotterdeploy_dir = os.path.abspath(os.path.join(tomcat_directory, '..', 'hotterdeploy'))
        else:
            self.hotterdeploy_dir = os.path.abspath(os.path.join(hotterdeploy_dir, 'hotterdeploy'))

        self.tomcat_temp_dir = os.path.join(tomcat_directory, 'temp')
        self.tomcat_webapps_dir = os.path.join(tomcat_directory, 'webapps')
        self.liferay_dir = os.path.join(self.tomcat_webapps_dir, self.liferay_context)

        if do_polling:
            self.observer = PollingObserverVFS(default_stat, listdir)
        else:
            self.observer = Observer()

        # Create our hotterdeploy directory and watch it for wars
        if not os.path.exists(self.hotterdeploy_dir):
            os.mkdir(self.hotterdeploy_dir)
        self.observer.schedule(OnDeployHandler(hotterDeployer=self), self.hotterdeploy_dir, recursive=False)

        # Scan tomcat temp directory for deployed portlets
        self._scan_temp()
        self.observer.schedule(OnTempDeployHandler(hotterDeployer=self), self.tomcat_temp_dir, recursive=False)

        # Scan tomcat webapps directory for deployed portlets
        self._scan_webapps()
        self.observer.schedule(OnWebappsDeployHandler(hotterDeployer=self), self.tomcat_webapps_dir, recursive=False)

        # Scan the working directory for portlets
        LOG.debug('Scanning workspace for portlets...')
        self._scan_wd(workspace_directory)
        LOG.debug('Done.')

        # path = os.path.join(self.workspace_directory, 'liferay-portal', 'credoc-newsletter-portlet')
        path = self.workspace_directory

        # IN_CREATE | IN_DELETE | IN_CLOSE_WRITE && src/main/webapp/WEB-INF
        w = self.observer.schedule(WorkSpaceHandler(hotterDeployer=self), path, recursive=True)
        # IN_CLOSE_WRITE && src/main/webapp
        self.observer.add_handler_for_watch(OnFileChangedHandler(hotterDeployer=self), w)
        # self.observer.schedule(OnFileChangedHandler(hotterDeployer=self), self.workspace_directory, recursive=True)
        # IN_CLOSE_WRITE && target/classes
        self.observer.add_handler_for_watch(OnClassChangedHandler(hotterDeployer=self), w)
        # self.observer.schedule(OnClassChangedHandler(hotterDeployer=self), self.workspace_directory, recursive=True)

        self.livereload_server = Server()

    def start(self):
        import time
        start_time = time.time()
        LOG.debug('Starting observer...')
        self.observer.start()
        LOG.debug('Starting observer took {0} seconds'.format(time.time() - start_time))

        from livereload import LiveReloadInfoHandler
        LiveReloadInfoHandler.hotterDeployer = weakref.proxy(self)

        LOG.info('Using {0}'.format('polling' if self.do_polling else 'FS events'))
        LOG.info('Serving livereload on http://{host}:{port}/info'.format(**vars(self.livereload_server)))

        try:
            self.livereload_server.serve()
        except KeyboardInterrupt:
            self.observer.stop()
            self.livereload_server.stop()
        self.observer.join()

    def __del__(self):
        if os.path.exists(self.hotterdeploy_dir):
            os.rmdir(self.hotterdeploy_dir)

    def _scan_wd(self, directory):
        self.portlets.update(scan_working_directory_for_portlet_contexts(directory))

    def _update_deploys(self):
        deploys = {}
        if hasattr(self, '_temp_deploys'):
            for name, path in self._temp_deploys.items():
                deploys[name] = path

        if hasattr(self, '_webapp_deploys'):
            for name, path in self._webapp_deploys.items():
                if name not in deploys:
                    deploys[name] = path

        self.deploys = deploys

    def _scan_temp(self):
        path = os.path.join(self.tomcat_directory, 'temp')
        self._temp_deploys = scan_tomcat_temporary_directory(path)
        self._update_deploys()

    def _scan_webapps(self):
        path = os.path.join(self.tomcat_directory, 'webapps')
        self._webapp_deploys = scan_tomcat_webapps_directory(path)
        self._update_deploys()

    def find_latest_temp_dir(self, portlet_name):
        '''
        Find the latest temp deploy directory for a given portlet:
        e.g. 21-my-portlet-name
        '''
        latest_subdir = self.deploys.get(portlet_name, None)
        return latest_subdir

    def trigger_browser_reload(self, path=None):
        LOG.debug('reloading browser')
        self.livereload_server.reload(path)


class MemoryBufferHandler(BufferingHandler):
    def __init__(self):
        super(MemoryBufferHandler, self).__init__(10)

    def emit(self, record):
        if record.module != 'web':
            super(MemoryBufferHandler, self).emit(record)

    def flush(self):
        if len(self.buffer):
            self.buffer.pop(0)


def main():
    parser = argparse.ArgumentParser(description='Hotter deploy')
    parser.add_argument('workspace_directory', help='path to your workspace')
    parser.add_argument('tomcat_directory', help='path to your tomcat')
    parser.add_argument('--hotterdeploy_dir', default='', help='where to place the hotterdeploy directory')
    parser.add_argument('--liferay_context', default='ROOT', help='the liferay context path')
    parser.add_argument('--poll', action='store_true', help='poll instead of listen for FS events, needed on network shares and vboxfs')
    parser.add_argument('--statics_dir', default=None, help='where to place the static resources')

    parser.add_argument(
        '-v',
        '--verbose',
        help='Be verbose',
        action="store_const",
        dest="loglevel",
        const=logging.DEBUG,
        default=logging.INFO
    )
    parser.add_argument(
        '-q',
        '--quiet',
        help='Hide most output',
        action="store_const",
        dest="loglevel",
        const=logging.ERROR
    )

    args = parser.parse_args()

    memory_handler = MemoryBufferHandler()

    # Setup basic logging
    logging.basicConfig(
        level=args.loglevel,
        format='%(levelname)7s:%(name)s: %(message)s',
        handlers=[logging.StreamHandler()]
    )

    logging.getLogger().addHandler(memory_handler)

    deployer = HotterDeployer(args.workspace_directory,
                              args.tomcat_directory,
                              args.hotterdeploy_dir,
                              args.liferay_context,
                              args.poll,
                              args.statics_dir)

    deployer.memory_handler = memory_handler
    deployer.start()
    del deployer


if __name__ == '__main__':
    main()
