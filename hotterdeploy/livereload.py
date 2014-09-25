'''
Based in python-livereload (https://github.com/lepture/python-livereload)
You need Tornado 2.2.0 or higher

https://launchpad.net/~chris-lea/+archive/python-tornado/
https://launchpad.net/~chris-lea/+archive/python-pycares
'''
import os
import logging
from tornado.ioloop import IOLoop
from tornado import escape
from tornado.web import Application, RequestHandler
from tornado.websocket import WebSocketHandler
from tornado.util import ObjectDict

class LiveReloadHandler(WebSocketHandler):
    waiters = set()

    def allow_draft76(self):
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
    def reload():
        logging.info('Reload %s waiters', len(LiveReloadHandler.waiters))

        msg = {
            'command': 'reload',
            'path': '*',
            'liveCSS': True
        }

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
            handshake = {}
            handshake['command'] = 'hello'
            handshake['protocols'] = [
                'http://livereload.com/protocols/official-7',
                'http://livereload.com/protocols/official-8',
                'http://livereload.com/protocols/official-9',
                'http://livereload.com/protocols/2.x-origin-version-negotiation',
                'http://livereload.com/protocols/2.x-remote-control'
            ]
            handshake['serverName'] = 'livereload-tornado'
            self.send_message(handshake)

        if message.command == 'info' and 'url' in message:
            #print '- Client connected for url {0}'.format(message.url)
            self.url = message.url
            LiveReloadHandler.waiters.add(self)
            if hasattr(LiveReloadHandler, 'update_status'):
                LiveReloadHandler.update_status()


class LiveReloadJSHandler(RequestHandler):
    def initialize(self, port):
        self._port = port

    def get(self):
        js = os.path.join(
            os.path.abspath(os.path.dirname(__file__)), 'livereload.js',
        )
        self.set_header('Content-Type', 'application/javascript')
        with open(js, 'r') as f:
            content = f.read()
            content = content.replace('{{port}}', str(self._port))
            self.write(content)


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


class Server(object):
    def __init__(self):
        self.host = None
        self.port = 35729
        
    def application(self):
        handlers = [
            (r'/livereload', LiveReloadHandler),
            (r'/forcereload', ForceReloadHandler),
            (r'/livereload.js', LiveReloadJSHandler, dict(port=self.port)),
        ]

        return Application(handlers=handlers, debug=True)

    def serve(self, port=None, host=None):
        """Start serve the server with the given port.

        :param port: serve on this port, default is 5500
        :param host: serve on this hostname, default is 0.0.0.0
        """
        if port:
            self.port = port
        if host is None:
            host = ''

        self.application().listen(self.port, address=host)

        self.host = host or '127.0.0.1'
        #print('Serving on %s:%s' % (self.host, self.port))

        try:
            IOLoop.instance().start()
        except KeyboardInterrupt:
            print('Shutting down...')
            
    def stop(self):
        IOLoop.instance().stop()

    def reload(self):
        LiveReloadHandler.reload()
        
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
