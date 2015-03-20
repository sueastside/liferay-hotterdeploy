import os
import sys
from xml.dom import minidom


def getElementsByTagName(xmldoc, name, parent_name='project'):
    elements = xmldoc.getElementsByTagName(name)
    els = []
    for el in elements:
        if parent_name and el.parentNode and el.parentNode.tagName == parent_name:
            els.append(el)
    return els


def is_jsp_hook(cwd, rel_path):
    liferay_hook_path = os.path.join(cwd, 'src/main/webapp/WEB-INF/liferay-hook.xml')
    if os.path.exists(liferay_hook_path):
        xmldoc = minidom.parse(liferay_hook_path)
        custom_jsp_dir = getElementsByTagName(xmldoc, 'custom-jsp-dir', 'hook')[0].firstChild.nodeValue
        if rel_path.startswith(custom_jsp_dir[1:]+'/'):
            rel_path = rel_path.split(custom_jsp_dir[1:]+'/')[1]
            return rel_path


def filter_filename(file_name, patterns=[]):
    for pattern in patterns:
        if pattern == file_name:
            return True
    return False


def scan_working_directory_for_portlet_contexts(directory):
    portlets = {}

    def get_version(xmldoc):
        els = getElementsByTagName(xmldoc, 'version')
        if len(els):
            return els[0].firstChild.nodeValue
        els = getElementsByTagName(xmldoc, 'parent')
        els = els[0].getElementsByTagName('version')
        return els[0].firstChild.nodeValue

    for file_name in os.listdir(directory):
        path = os.path.join(directory, file_name)
        if (os.path.isdir(path)
            and not filter_filename(file_name, ['.svn',
                                                'target',
                                                '.metadata',
                                                '.settings',
                                                'src',
                                                'Servers'])):
            portlets.update(scan_working_directory_for_portlet_contexts(path))
        else:
            # Deployed portlet name is derived from the war name
            if file_name == 'pom.xml':
                xmldoc = minidom.parse(path)
                portlet_name = getElementsByTagName(xmldoc, 'artifactId')[0].firstChild.nodeValue
                if not any(map(lambda x: portlet_name.endswith('-'+x), ['portlet', 'hook', 'theme', 'web', 'layouttpl'])):
                    portlet_name += '-'+get_version(xmldoc)
                # TODO: fetch the war name if its specified in the build config
                webapp_path = os.path.abspath(directory)
                portlets[webapp_path] = portlet_name

    return portlets


def scan_tomcat_temporary_directory(directory):
    deploys = {}
    # Collect the temp deploy dirs for all portlets
    for deploy in os.listdir(directory):
        portlet_name = deploy.split('-', 1)
        deploy_path = os.path.join(directory, deploy)
        if os.path.isdir(deploy_path) and len(portlet_name) > 1:
            portlet_name = portlet_name[1]
            if portlet_name not in deploys:
                deploys[portlet_name] = []
            deploys[portlet_name].append(deploy_path)

    # Now only save the latest temp deploy dir per portlet
    for portlet_name, deploy_paths in deploys.items():
        deploys[portlet_name] = max(deploy_paths, key=os.path.getmtime)

    return deploys


def scan_tomcat_webapps_directory(directory):
    deploys = {}
    # Collect the temp deploy dirs for all portlets
    for deploy in os.listdir(directory):
        deploy_path = os.path.join(directory, deploy)
        if os.path.isdir(deploy_path):
            deploys[deploy] = deploy_path

    return deploys


if __name__ == '__main__':
    for k, v in scan_working_directory_for_portlet_contexts(sys.argv[1]).items():
        print " * ", v, k

    for k, v in scan_tomcat_temporary_directory(sys.argv[2]).items():
        print " * ", v, k
