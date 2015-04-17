import os
import weakref
import shutil
import logging

from watchdog.events import FileSystemEventHandler

from .utilities import is_jsp_hook
from .deploy import Deploy

from . import sassc

LOG = logging.getLogger(__name__)

def normalize_path(path):
    return path.replace('/', os.sep)

def contains_path(path, sub_path):
    return path.find(normalize_path(sub_path)) != -1


class OnDeployHandler(FileSystemEventHandler):
    def __init__(self, hotterDeployer):
        super(OnDeployHandler, self).__init__()
        self.hotterDeployer = weakref.proxy(hotterDeployer)

    def on_created(self, event):
        d = Deploy(self.hotterDeployer,
                   event.src_path,
                   self.hotterDeployer.tomcat_directory
                   )
        d.start()


class OnTempDeployHandler(FileSystemEventHandler):
    def __init__(self, hotterDeployer):
        super(OnTempDeployHandler, self).__init__()
        self.hotterDeployer = weakref.proxy(hotterDeployer)

    def process_default(self, event):
        self.hotterDeployer._scan_temp()

    def on_created(self, event):
        self.process_default(event)

    def on_delete(self, event):
        self.process_default(event)


class OnWebappsDeployHandler(FileSystemEventHandler):
    def __init__(self, hotterDeployer):
        super(OnWebappsDeployHandler, self).__init__()
        self.hotterDeployer = weakref.proxy(hotterDeployer)

    def process_default(self, event):
        self.hotterDeployer._scan_webapps()

    def on_created(self, event):
        self.process_default(event)

    def on_delete(self, event):
        self.process_default(event)


class WorkSpaceHandler(FileSystemEventHandler):
    def __init__(self, hotterDeployer):
        super(WorkSpaceHandler, self).__init__()
        self.hotterDeployer = weakref.proxy(hotterDeployer)

    def dispatch(self, event):
        LOG.debug('WorkSpaceHandler::dispatch {0} {1}'.format(event.src_path, event))
        path = event.src_path
        if (path.find('.svn') == -1 and
                contains_path(path, 'src/main/webapp/WEB-INF')):
            super(WorkSpaceHandler, self).dispatch(event)
        else:
            LOG.debug('WorkSpaceHandler::dispatch ignored {0}'.format(event.src_path))

    def on_created(self, event):
        self.process_default(event)

    def on_delete(self, event):
        self.process_default(event)

    def on_modified(self, event):
        self.process_default(event)

    def process_default(self, event):
        if event.src_path.endswith('.xml'):
            LOG.debug('WorkSpaceHandler::process_default {0} {1}'.format(event.src_path, event))
            self.hotterDeployer._scan_wd(self.hotterDeployer.workspace_directory)


class OnFileChangedHandler(FileSystemEventHandler):
    def __init__(self, hotterDeployer):
        super(OnFileChangedHandler, self).__init__()
        self.hotterDeployer = weakref.proxy(hotterDeployer)
        extension = '.jsp,.js,.css,.tag,.vm,.jspf'
        self.extensions = extension.split(',')

    def dispatch(self, event):
        path = event.src_path
        print 'FF', os.sep
        LOG.debug('OnFileChangedHandler::dispatch {0} {1}'.format(event.src_path, event))
        if path.find('.svn') == -1 and contains_path(path, 'src/main/webapp'):
            super(OnFileChangedHandler, self).dispatch(event)
        else:
            LOG.debug('OnFileChangedHandler::dispatch ignored {0}'.format(event.src_path))

    def on_modified(self, event):
        cwd = event.src_path.split(normalize_path('/src/main/webapp'))[0]

        # Handle portlets
        portlet_name = self.hotterDeployer.portlets.get(cwd, None)
        if portlet_name:
            if all(not event.src_path.endswith(ext) for ext in self.extensions):
                return
            rel_path = event.src_path.split(cwd+normalize_path('/src/main/webapp'))[1][1:]

            jsp_hook = is_jsp_hook(cwd, rel_path)
            if jsp_hook:
                print 'JSP HOOK', rel_path
                rel_path = jsp_hook
                latest_subdir = self.hotterDeployer.liferay_dir
                dest_path = os.path.join(latest_subdir, rel_path)
                print dest_path
                if not os.path.exists(dest_path+'.hotterdeploy'):
                    shutil.copy2(dest_path, dest_path+'.hotterdeploy')
            else:
                # Find latest dir
                latest_subdir = self.hotterDeployer.find_latest_temp_dir(portlet_name)

            if not latest_subdir:
                LOG.debug('- Skipped {0} ({1} not deployed)'.format(rel_path, portlet_name))
            else:
                dest_path = os.path.join(latest_subdir, rel_path)
                LOG.info('- Copying {0} ({1}) [{2}]'.format(rel_path, portlet_name, os.path.basename(latest_subdir)))
                if not os.path.exists(os.path.dirname(dest_path)):
                    os.makedirs(os.path.dirname(dest_path))
                print 'dest_path', dest_path

                if rel_path.endswith('.js'):
                    shutil.copy2(event.src_path, dest_path)
                    if self.hotterDeployer.statics_directory:
                        dest_path = os.path.join(self.hotterDeployer.statics_directory, portlet_name, rel_path)
                        if not os.path.exists(os.path.dirname(dest_path)):
                            os.makedirs(os.path.dirname(dest_path))
                        shutil.copy2(event.src_path, dest_path)
                    self.hotterDeployer.trigger_browser_reload()
                elif rel_path.endswith('.css'):
                    #shutil.copy2(event.src_path, dest_path)
                    try:
                        print 'compiling scss'
                        data = sassc.compile(event.src_path)

                        with open(dest_path, 'wb') as f:
                            f.write(data)

                        # TODO: copy output
                        # /home/sueastside/Projects/CreDoc/static - credoc-theme
                        print 'output for portlet ', portlet_name, rel_path

                        if self.hotterDeployer.statics_directory:
                            dest_path = os.path.join(self.hotterDeployer.statics_directory, portlet_name, rel_path)

                            if not os.path.exists(os.path.dirname(dest_path)):
                                os.makedirs(os.path.dirname(dest_path))

                            with open(dest_path, 'wb') as f:
                                f.write(data)

                        self.hotterDeployer.trigger_browser_reload(portlet_name+'/'+rel_path)
                    except sassc.SassException as e:
                        log.warn(e)

                else:
                    self.hotterDeployer.trigger_browser_reload()
                    shutil.copy2(event.src_path, dest_path)


class OnClassChangedHandler(FileSystemEventHandler):
    def __init__(self, hotterDeployer):
        super(OnClassChangedHandler, self).__init__()
        self.hotterDeployer = weakref.proxy(hotterDeployer)

    def dispatch(self, event):
        path = event.src_path
        if (path.find('.svn') == -1
            and path.find('target/classes') != -1
            and os.path.isfile(path)):
                super(OnClassChangedHandler, self).dispatch(event)

    def on_modified(self, event):
        cwd = event.src_path.split('/target/classes')[0]

        # Handle portlets
        portlet_name = self.hotterDeployer.portlets.get(cwd, None)
        print 'portlet_name', portlet_name
        if portlet_name:
            rel_path = event.src_path.split(cwd+'/target/classes')[1][1:]
            print rel_path

            latest_subdir = self.hotterDeployer.find_latest_temp_dir(portlet_name)

            print 'rel_path', rel_path

            if not latest_subdir:
                print '- Skipped {0} ({1} not deployed)'.format(rel_path, portlet_name)
            else:
                dest_path = os.path.join(latest_subdir, 'WEB-INF', 'classes', rel_path)
                print '- Copying {0} ({1}) [{2}]'.format(rel_path, portlet_name, os.path.basename(latest_subdir))
                if not os.path.exists(os.path.dirname(dest_path)):
                    os.makedirs(os.path.dirname(dest_path))
                print 'OnClassChangedHandler::on_modified', dest_path
                shutil.copy2(event.src_path, dest_path)

                # self.hotterDeployer.trigger_browser_reload()

                from threading import Timer
                t = Timer(1.2, self.hotterDeployer.trigger_browser_reload)
                t.start()
