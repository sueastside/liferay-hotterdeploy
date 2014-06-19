Liferay Hotterdeploy
====
HotterDeployer is a Liferay utility meant to ease development.

It will monitor the resources (jsp,css,js) in your workspace for deployed
portlets and hot-copy them on changes, without the need for a redeployment. 
(Keeping the permgen problem at bay)

It also offers an alternative to the liferay 'deploy' directory, 
called 'hotterdeploy' which can detect conflicting jar changes and will
automatically undeploy and redeploy the affected portlet.
(Change the `liferay.auto.deploy.dir` property in your settings.xml accordingly
 e.g. `<liferay.auto.deploy.dir>
        /liferay-developer-studio/liferay-portal-6.2-ee-sp3/hotterdeploy
      </liferay.auto.deploy.dir>`)
      
If you have a [LiveReload](http://feedback.livereload.com/knowledgebase/articles/86242-how-do-i-install-and-use-the-browser-extensions-) 
extension installed, your browser will automatically reload the page 
when it detects a changed resource or redeployed portlet.

      
Notes
----- 
As this uses inotify to detect changed files, it is linux only at the moment.

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

 
Usage
----- 
 ```
 hotterdeploy "/home/user/workspace" "/home/user/liferay-developer-studio/liferay-portal-6.2-ee-sp3/tomcat-7.0.42"
 ```
