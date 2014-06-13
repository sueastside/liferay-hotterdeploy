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
import pyinotify
import os
import shutil
import weakref
import binascii
from xml.dom import minidom
from zipfile import ZipFile
from pyjavaproperties import Properties
from threading import Thread


class HotterDeployer(object):
    def __init__(self, workspace_directory, tomcat_directory):
        self.workspace_directory = workspace_directory
        self.tomcat_directory = tomcat_directory
        self.portlets = {}
        self.deploys = {}
        self.wm = pyinotify.WatchManager()
        self.notifier = pyinotify.Notifier(self.wm)
        
        # Create our hotterdeploy directory and watch it for wars
        self.hotterdeploy_dir = os.path.abspath(os.path.join(tomcat_directory, '..', 'hotterdeploy'))
        if not os.path.exists(self.hotterdeploy_dir):
            os.mkdir(self.hotterdeploy_dir)
        self.wm.add_watch(self.hotterdeploy_dir, pyinotify.IN_CLOSE_WRITE, rec=False, auto_add=False, proc_fun=OnDeployHandler(hotterDeployer=self))
        
        # Scan tomcat directory for deployed portlets
        self._scan_temp()
        self.wm.add_watch(os.path.join(tomcat_directory, 'temp'), pyinotify.IN_CREATE | pyinotify.IN_DELETE, rec=False, auto_add=False, proc_fun=OnTempDeployHandler(hotterDeployer=self))
         
        # Scan the working directory for portlets
        self._scan_wd(workspace_directory)
        
        def portlet_exclude_filter(path):
            return path.find('.svn') != -1 or not path.endswith('src/main/webapp/WEB-INF')
        wdd = self.wm.add_watch(workspace_directory, pyinotify.IN_CREATE | pyinotify.IN_DELETE | pyinotify.IN_CLOSE_WRITE, 
                            rec=True, auto_add=True, proc_fun=WorkSpaceHandler(hotterDeployer=self),
                            exclude_filter=portlet_exclude_filter)   
                            
        def exclude_filter(path):
            return path.find('.svn') != -1 or path.find('src/main/webapp') == -1
        self.wm.add_watch(workspace_directory, pyinotify.IN_CLOSE_WRITE, 
                            rec=True, auto_add=True, proc_fun=OnFileChangedHandler(hotterDeployer=self),
                            exclude_filter=exclude_filter)
        
        self._print_status()
        self.notifier.loop()

    def __del__(self):
        if os.path.exists(self.hotterdeploy_dir):
            os.rmdir(self.hotterdeploy_dir)
        
    def _print_status(self):
        print '='*70
        for path, portlet_name in self.portlets.items():
            deployed = portlet_name in self.deploys
            print '{0: <50}: {1}'.format(portlet_name, 'DEPLOYED' if deployed else ' - ')
            
    def _scan_wd(self, directory):
       for file_name in os.listdir(directory):
           path = os.path.join(directory, file_name)
           if os.path.isdir(path) and file_name != '.svn' and file_name != 'target':
               self._scan_wd(path)
           else:
               if file_name == 'portlet.xml':
                   xmldoc = minidom.parse(path)
                   portlet_name = xmldoc.getElementsByTagName('portlet-name')[0].firstChild.nodeValue
                   webapp_path = os.path.abspath(os.path.join(directory, '..', '..', '..', '..'))
                   #print portlet_name, webapp_path
                   self.portlets[webapp_path] = portlet_name
    
    def _scan_temp(self):
        path = os.path.join(self.tomcat_directory, 'temp')
        deploys = {}
        # Collect the temp deploy dirs for all portlets
        for deploy in os.listdir(path):
            portlet_name = deploy.split('-', 1)
            deploy_path = os.path.join(path, deploy)
            if os.path.isdir(deploy_path) and len(portlet_name) > 1:
                portlet_name = portlet_name[1]
                if portlet_name not in deploys:
                    deploys[portlet_name] = []
                deploys[portlet_name].append(deploy_path)
        
        # Now only save the latest temp deploy dir per portlet
        for portlet_name, deploy_paths in deploys.items():
            deploys[portlet_name] = max(deploy_paths, key=os.path.getmtime)
            
        self.deploys = deploys

    def find_latest_temp_dir(self, portlet_name):
        '''
        Find the latest temp deploy directory for a given portlet:
        e.g. 21-my-portlet-name
        '''
        latest_subdir = self.deploys.get(portlet_name, None)
        return latest_subdir
        

class OnTempDeployHandler(pyinotify.ProcessEvent):
    def my_init(self, hotterDeployer):
        self.hotterDeployer = weakref.proxy(hotterDeployer)
    def process_default(self, event):
        self.hotterDeployer._scan_temp()
        self.hotterDeployer._print_status()


class WorkSpaceHandler(pyinotify.ProcessEvent):
    def my_init(self, hotterDeployer):
        self.hotterDeployer = weakref.proxy(hotterDeployer)
    def process_default(self, event):   
        if event.pathname.endswith('.xml'):
            print 'WorkSpaceHandler::process_default', event.pathname, event
            self.hotterDeployer._scan_wd(self.hotterDeployer.workspace_directory)
            self.hotterDeployer._print_status()


class OnFileChangedHandler(pyinotify.ProcessEvent):
    def my_init(self, hotterDeployer):
        self.hotterDeployer = weakref.proxy(hotterDeployer)
        extension = '.jsp,.js,.css'
        self.extensions = extension.split(',')
       
    def process_IN_CLOSE_WRITE(self, event):
        cwd = event.pathname.split('/src/main/webapp')[0]
        portlet_name = self.hotterDeployer.portlets.get(cwd, None)
        if portlet_name:
            if all(not event.pathname.endswith(ext) for ext in self.extensions):
                return
            rel_path = event.pathname.split(cwd)[1][1:]
                
            #Find latest dir
            latest_subdir = self.hotterDeployer.find_latest_temp_dir(portlet_name)
            if not latest_subdir:
                print 'Skipped {0} ({1} not deployed)'.format(rel_path, portlet_name)
            else:
                dest_path = os.path.join(latest_subdir, rel_path)
                print 'Copying {0} ({1}) [{2}]'.format(rel_path, portlet_name, os.path.basename(latest_subdir))
                if not os.path.exists(os.path.dirname(dest_path)):
                  os.makedirs(os.path.dirname(dest_path))
                
                shutil.copy2(event.pathname, dest_path)    
               

class OnDeployHandler(pyinotify.ProcessEvent):
    def my_init(self, hotterDeployer):
        self.hotterDeployer = weakref.proxy(hotterDeployer)
        
    def process_default(self, event):   
        d = Deploy(event.pathname, self.hotterDeployer.tomcat_directory)
        d.start()  


class Deploy(Thread):
    '''
    Conditionally deploy a portlet war
    '''
    def __init__(self, war_path, tomcat_directory):
        self.war_path = war_path
        self.tomcat_directory = tomcat_directory
        super(Deploy, self).__init__()
        
    def _get_portlet_name(self):
        with ZipFile(self.war_path, 'r') as war:
            with war.open('WEB-INF/portlet.xml') as xml:
                xmldoc = minidom.parse(xml)
                portlet_name = xmldoc.getElementsByTagName('portlet-name')[0].firstChild.nodeValue
                return portlet_name
                
    def _find_latest_temp_dir(self, portlet_name):
        to = os.path.join(self.tomcat_directory, 'temp')
        all_subdirs = [os.path.join(to, d) for d in os.listdir(to) if os.path.isdir(os.path.join(to, d)) and d.endswith(portlet_name)]
        if len(all_subdirs):
            latest_subdir = max(all_subdirs, key=os.path.getmtime)
            return latest_subdir
        return None
        
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
                       
    def run(self):
        portlet_name = self._get_portlet_name()
        latest_dir = self._find_latest_temp_dir(portlet_name)
        
        if latest_dir: 
            # The portlet seems to be deployed, let's compare
            needs_undeploy = check_for_lib_diffs(self.war_path, latest_dir)
            if needs_undeploy:
                # We found lib differences
                with open(os.path.join(self.tomcat_directory, 'logs/catalina.out')) as f:
                    # Start listening to the log
                    f.seek(0, 2) # go to end
                    p = f.tell()
                    if self._undeploy(portlet_name):
                        # We undeployed, now wait for LifeRay to notice
                        print 'Undeploying {0}'.format(portlet_name)
                        while True:
                            f.seek(p)
                            latest_data = f.read()
                            p = f.tell()
                            if latest_data:
                                print latest_data
                                print str(p).center(10).center(80, '=')
                                if latest_data.find('for '+portlet_name+' was unregistered') != -1:
                                    break
        
        print 'Deploying {0}'.format(portlet_name)
        self._deploy()
        
        
def check_for_lib_diffs(war_path, temp_portlet_path):
    '''
    Checks whether the jars in a war and on a deployed path are the same
    '''
    jars = {}
    # Calculate crc32 for all deployed jars
    for lib in os.listdir(os.path.join(temp_portlet_path, 'WEB-INF/lib/')):
        with open(os.path.join(temp_portlet_path, 'WEB-INF/lib/', lib)) as jar:
            jars['WEB-INF/lib/'+lib] = binascii.crc32(jar.read())

    # Process the war to be deployed
    with ZipFile(war_path, 'r') as war:
        # Process liferay dependencies
        dep_jars = ['util-taglib.jar', 'util-java.jar', 'util-bridges.jar']
        try:
            with war.open('WEB-INF/liferay-plugin-package.properties') as prop:
                p = Properties()
                #p.load(prop) does not work
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
                            crco = binascii.crc32(lib.read()) #info.CRC
                        jars[info.filename] = crco == crc
                    else:
                        jars[info.filename] = None

    # Iterate the file listing to check for missing/outdated/lingering
    # files
    needs_undeploy = False
    for filename, crc in jars.items():
        if crc == 'LR_DEP':
            pass
        elif crc == True:
            pass
        elif crc == None:
            print '{0} is missing'.format(filename)
        elif crc == False:
            print '{0} is out of date'.format(filename)
            needs_undeploy = True
        else:
            print '{0} is lingering'.format(filename)
            needs_undeploy = True
            
    return needs_undeploy


def main():
    parser = argparse.ArgumentParser(description='Hotter deploy')
    parser.add_argument('workspace_directory', help='path to your workspace')
    parser.add_argument('tomcat_directory', help='path to your tomcat')

    args = parser.parse_args()
    
    deployer = HotterDeployer(args.workspace_directory, args.tomcat_directory)
    del deployer


if __name__ == '__main__':
    main()
