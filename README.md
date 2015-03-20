Liferay Hotterdeploy
====
HotterDeployer is a Liferay utility meant to ease development.

It will monitor resources (.jsp,.js,.css,.tag,.vm,.jspf), jsp-hooks and
java code of deployed portlets in your workspace and hot-copy them on changes,
without the need for a redeployment. (Keeping the permgen problem at bay)

It also offers an alternative to the liferay 'deploy' directory,
called 'hotterdeploy' which can detect conflicting jar changes and will
automatically undeploy and redeploy the affected portlet.
(Change the `liferay.auto.deploy.dir` property in your settings.xml accordingly
 e.g. `<liferay.auto.deploy.dir>
        /liferay-developer-studio/liferay-portal-6.2-ee-sp3/hotterdeploy
      </liferay.auto.deploy.dir>`)

If you have a [LiveReload](http://feedback.livereload.com/knowledgebase/articles/86242-how-do-i-install-and-use-the-browser-extensions-)
extension installed, your browser will automatically reload the page
when it detects a change.


Notes
-----
~~As this uses inotify to detect changed files, it is linux only at the moment.~~

Moved from pyinotify to watchdog for detecting changes, so should support all platforms now.
You can also sepecify --poll on the commandline, allowing to switch to a polling scheme for file detection in case your underlying filesystem does not support FS events (vboxfs for example)

Installation
-----
Checkout Hotterdeploy
 ```
 git clone https://github.com/sueastside/liferay-hotterdeploy.git
 ```

Install Hotterdeploy
 ```
 cd liferay-hotterdeploy
 sudo python setup.py install
 ```

Download and configure Spring Loaded
Get https://github.com/spring-projects/spring-loaded
edit setenv.sh and on a new line add
 ```
 JAVA_OPTS="$JAVA_OPTS -javaagent:<pathTo>/springloaded-<version>.jar -noverify"
 ```

Usage
-----
 ```
 hotterdeploy "/home/user/workspace" "/home/user/liferay-developer-studio/liferay-portal-6.2-ee-sp3/tomcat-7.0.42"
 ```
