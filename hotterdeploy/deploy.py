import os
import shutil
import re
import datetime
import logging
import binascii
from pyjavaproperties import Properties
from xml.dom import minidom
from zipfile import ZipFile
from threading import Thread

LOG = logging.getLogger(__name__)


class DeploymentTimedOutException(Exception):
    pass


class Deploy(Thread):
    '''
    Conditionally deploy a portlet war
    '''
    def __init__(self, hotterDeployer_weakref, war_path, tomcat_directory):
        self.hotterDeployer = hotterDeployer_weakref
        self.war_path = war_path
        self.tomcat_directory = tomcat_directory
        super(Deploy, self).__init__()

    def _get_portlet_name(self):
        with ZipFile(self.war_path, 'r') as war:
            with war.open('WEB-INF/portlet.xml') as xml:
                xmldoc = minidom.parse(xml)
                portlet_name = xmldoc.getElementsByTagName('portlet-name')[0].firstChild.nodeValue
                return portlet_name

    def _get_bundle_name(self):
        matcher = re.compile('(.+)(-(\d\.\d\.\d(-SNAPSHOT)?))?\.war')
        war_name = os.path.basename(self.war_path)
        match = matcher.match(war_name)
        return match.group(1)

    def _undeploy(self, portlet_name):
        webapps_path = os.path.join(self.tomcat_directory, 'webapps', portlet_name)
        if os.path.exists(webapps_path):
            shutil.rmtree(webapps_path)
            return True
        else:
            return False

    def _deploy(self):
        dst = os.path.abspath(os.path.join(self.tomcat_directory, '..', 'deploy/'))
        shutil.move(self.war_path, dst)
        return True

    def _wait_for_string_in_log(self, string, action):
        matcher = re.compile(string)
        start = datetime.datetime.now()
        with open(os.path.join(self.tomcat_directory, 'logs/catalina.out')) as f:
            # Start listening to the log
            f.seek(0, 2)  # go to end
            p = f.tell()
            if action():
                while True:
                    f.seek(p)
                    latest_data = f.read()
                    p = f.tell()
                    if latest_data:
                        # print latest_data
                        # print str(p).center(10).center(80, '=')
                        print '.',
                        if matcher.search(latest_data):
                            break

                        # Liferay 6.1 hack
                        if latest_data.find('Initializing Spring root WebApplicationContext'):
                            break
                        if latest_data.find('Closing Spring root WebApplicationContext'):
                            break

                    elapsed = datetime.datetime.now() - start
                    if elapsed > datetime.timedelta(minutes=1):
                        raise DeploymentTimedOutException()

    def do(self):
        bundle_name = self._get_bundle_name()
        latest_dir = self.hotterDeployer.find_latest_temp_dir(bundle_name)

        try:
            if latest_dir:
                # The portlet seems to be deployed, let's compare
                needs_undeploy = check_for_lib_diffs(self.war_path, latest_dir)
                if needs_undeploy:
                    # We found lib differences
                    # We undeployed, now wait for LifeRay to notice
                    LOG.info('Undeploying {0}'.format(bundle_name))
                    self._wait_for_string_in_log('for '+bundle_name+' (\w+) unregistered', lambda: self._undeploy(bundle_name))

            LOG.info('Deploying {0}'.format(bundle_name))
            self._wait_for_string_in_log('for '+bundle_name+' (\w+) available for use', lambda: self._deploy())
            self.hotterDeployer.trigger_browser_reload()
        except DeploymentTimedOutException:
            LOG.error('Deployment of {0} failed!!!'.format(bundle_name))

    def run(self):
        self.do()


def check_for_lib_diffs(war_path, temp_portlet_path):
    '''
    Checks whether the jars in a war and on a deployed path are the same
    '''
    jars = {}
    # Calculate crc32 for all deployed jars
    webinf_lib_dir = os.path.join(temp_portlet_path, 'WEB-INF/lib/')
    if os.path.exists(webinf_lib_dir):
        for lib in os.listdir(webinf_lib_dir):
            path = os.path.join(temp_portlet_path, 'WEB-INF/lib/', lib)
            if os.path.isfile(path):
                with open(os.path.join(temp_portlet_path, 'WEB-INF/lib/', lib)) as jar:
                    jars['WEB-INF/lib/'+lib] = binascii.crc32(jar.read())
            else:
                jars['WEB-INF/lib/'+lib] = None  # directory assume changed

    # Process the war to be deployed
    with ZipFile(war_path, 'r') as war:
        # Process liferay dependencies
        dep_jars = ['util-taglib.jar', 'util-java.jar', 'util-bridges.jar']
        try:
            with war.open('WEB-INF/liferay-plugin-package.properties') as prop:
                p = Properties()
                # p.load(prop) does not work
                p._Properties__parse(prop.readlines())

                dep_jars.extend(p['portal-dependency-jars'].split(','))
        except KeyError:
            pass
        for jar in dep_jars:
            jars['WEB-INF/lib/'+jar] = 'LR_DEP'

        # Calculate crc32 for jars in war
        for info in war.infolist():
            if info.filename.startswith('WEB-INF/lib/') and not info.filename == 'WEB-INF/lib/':
                    crc = jars.get(info.filename, None)
                    if crc:
                        with war.open(info.filename) as lib:
                            crco = binascii.crc32(lib.read())  # info.CRC
                        jars[info.filename] = crco == crc
                    else:
                        jars[info.filename] = None

    # Iterate the file listing to check for missing/outdated/lingering
    # files
    needs_undeploy = False
    for filename, crc in jars.items():
        if crc == 'LR_DEP':
            pass
        elif crc is True:
            pass
        elif crc is None:
            LOG.info('{0} is missing'.format(filename))
        elif crc is False:
            LOG.info('{0} is out of date'.format(filename))
            needs_undeploy = True
        else:
            LOG.info('{0} is lingering'.format(filename))
            needs_undeploy = True

    return needs_undeploy
