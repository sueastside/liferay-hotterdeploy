'''
Based in python-livereload (https://github.com/lepture/python-livereload)
You need Tornado 2.2.0 or higher

https://launchpad.net/~chris-lea/+archive/python-tornado/
https://launchpad.net/~chris-lea/+archive/python-pycares
'''

import logging
from datetime import datetime
from pkg_resources import resource_string
from tornado.ioloop import IOLoop
from tornado import escape
from tornado.web import RequestHandler
from tornado import web
from tornado.websocket import WebSocketHandler
from tornado.util import ObjectDict

from jinja2 import Template


class LiveReloadHandler(WebSocketHandler):
    waiters = set()

    def allow_draft76(self):
        return True

    def check_origin(self, origin):
        return True

    def on_close(self):
        if self in LiveReloadHandler.waiters:
            LiveReloadHandler.waiters.remove(self)

    def send_message(self, message):
        if isinstance(message, dict):
            message = escape.json_encode(message)
        try:
            self.write_message(message)
        except:
            logging.error('Error sending message', exc_info=True)

    @staticmethod
    def reload(path=None):
        logging.info('Reload %s waiters', len(LiveReloadHandler.waiters))

        msg = {
            'command': 'reload',
            'path': path or '*',
            'liveCSS': True,
            'liveImg': True
        }
        print 'sending', msg
        for waiter in LiveReloadHandler.waiters:
            try:
                waiter.write_message(msg)
            except:
                logging.error('Error sending message', exc_info=True)
                LiveReloadHandler.waiters.remove(waiter)

    def on_message(self, message):
        """Handshake with livereload.js

        1. client send 'hello'
        2. server reply 'hello'
        3. client send 'info'

        http://feedback.livereload.com/knowledgebase/articles/86174-livereload-protocol
        """
        message = ObjectDict(escape.json_decode(message))
        if message.command == 'hello':
            handshake = {
                'command': 'hello',
                'protocols': [
                    'http://livereload.com/protocols/official-7',
                ],
                'serverName': 'livereload-tornado',
            }
            self.send_message(handshake)

        if message.command == 'info' and 'url' in message:
            # print '- Client connected for url {0}'.format(message.url)
            self.url = message.url
            LiveReloadHandler.waiters.add(self)
            if hasattr(LiveReloadHandler, 'update_status'):
                LiveReloadHandler.update_status()


class LiveReloadJSHandler(RequestHandler):
    def get(self):
        self.set_header('Content-Type', 'application/javascript')
        self.write(resource_string(__name__, 'livereload.js'))


class ForceReloadHandler(RequestHandler):
    def get(self):
        msg = {
            'command': 'reload',
            'path': self.get_argument('path', default=None) or '*',
            'liveCSS': True,
            'liveImg': True
        }
        for waiter in LiveReloadHandler.waiters:
            try:
                waiter.write_message(msg)
            except:
                logging.error('Error sending message', exc_info=True)
                LiveReloadHandler.waiters.remove(waiter)
        self.write('ok')


class LiveReloadInfoHandler(RequestHandler):
    def get(self):
        self.set_header('Content-Type', 'text/html')
        if hasattr(LiveReloadInfoHandler, 'hotterDeployer'):
            tmpl = resource_string(__name__, 'index.html')
            template = Template(tmpl)
            data = template.render(
                ctx=self.hotterDeployer,
                waiters=LiveReloadHandler.waiters,
                now=datetime.now()
                )
            self.write(data)
        else:
            self.write('''
            <html>
                <body>
                Not initialized
                </body>
            </html>
            ''')


class Server(object):
    def __init__(self, port=None, host=None, liveport=None):
        self.host = None
        self.port = 35729
        if port:
            self.port = port

        self.host = host or '0.0.0.0'
        self.liveport = liveport

    def application(self, port, host, liveport=None, debug=True):
        if liveport is None:
            liveport = port

        live_handlers = [
            (r'/livereload', LiveReloadHandler),
            (r'/forcereload', ForceReloadHandler),
            (r'/livereload.js', LiveReloadJSHandler),
            (r'/info', LiveReloadInfoHandler),
        ]

        live = web.Application(handlers=live_handlers, debug=debug)
        live.listen(liveport, address=host)

    def serve(self):
        """Start serve the server with the given port.

        :param port: serve on this port, default is 35729
        :param host: serve on this hostname, default is 0.0.0.0
        """
        self.application(self.port, self.host, liveport=self.liveport)

        try:
            IOLoop.instance().start()
        except KeyboardInterrupt as e:
            print('Shutting down...')
            raise e

    def stop(self):
        IOLoop.instance().stop()

    def reload(self, path=None):
        LiveReloadHandler.reload(path)


def main():
    server = Server()
    from threading import Thread
    t = Thread(target=server.serve)
    t.start()
    from time import sleep
    try:
        while True:
            sleep(2)
            print 'reloading'
            server.reload()
    except KeyboardInterrupt:
        server.stop()
        t.join()

if __name__ == '__main__':
    main()
