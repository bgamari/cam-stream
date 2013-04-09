import gi
gi.require_version('Gst', '1.0')
from gi.repository import GObject, Gst, GstApp
from stream import Stream
from Queue import Queue
import threading
from wsgiref.simple_server import WSGIServer, make_server, WSGIRequestHandler
from SocketServer import ThreadingMixIn

GObject.threads_init()
Gst.init(None)

class MyWSGIServer(ThreadingMixIn, WSGIServer):
     pass

def create_server(host, port, app, server_class=MyWSGIServer,
          handler_class=WSGIRequestHandler):
     return make_server(host, port, app, server_class, handler_class)

INDEX_PAGE = """
<html>
<head>
    <title>Gstreamer testing</title>
</head>
<body>
<h1>Testing a dummy camera with GStreamer</h1>
<img src="/mjpeg_stream"/>
<hr />
</body>
</html>
"""
ERROR_404 = """
<html>
  <head>
    <title>404 - Not Found</title>
  </head>
  <body>
    <h1>404 - Not Found</h1>
  </body>
</html>
"""

class StreamerApp(object):
    queues = []

    def __init__(self, stream):
        self._stream = stream
        self._reading_stream = False

    def __call__(self, environ, start_response):
        if environ['PATH_INFO'] == '/':
            start_response("200 OK", [
                ("Content-Type", "text/html"),
                ("Content-Length", str(len(INDEX_PAGE)))
            ])
            return iter([INDEX_PAGE])
        elif environ['PATH_INFO'] == '/mjpeg_stream':
            return self._start_streaming(start_response)
        else:
            start_response("404 Not Found", [
                ("Content-Type", "text/html"),
                ("Content-Length", str(len(ERROR_404)))
            ])
            return iter([ERROR_404])

    def _start_reading(self):
        self._stream.listen_stream(self._read_stream)

    def _read_stream(self, b):
        for q in self.queues:
            q.put(b)
        return len(self.queues) > 0

    def _start_streaming(self, start_response):
        start_response('200 OK', [('Content-type', 'multipart/x-mixed-replace; boundary=--break')])

        self._start_reading()
        q = Queue()
        self.queues.append(q)
        while True:
            try:
                yield q.get()
            except:
                print 'done'
                if q in self.queues:
                    self.queues.remove(q)
                return

#src = Gst.ElementFactory.make('v4l2src', 'video-source')
src = Gst.ElementFactory.make('videotestsrc', 'video-source')

stream = Stream(src)
stream.start()

app = StreamerApp(stream)
port = 5005
httpd = create_server('', port, app)

thrd = threading.Thread(target=httpd.serve_forever)
thrd.daemon = True
thrd.start()

loop = GObject.MainLoop()
loop.run()
