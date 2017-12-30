import gi
gi.require_version('Gst', '1.0')
from gi.repository import GObject, Gst, GstApp
from stream import MJPEGSink, SnapshotSink, WebMSink
from Queue import Queue
import threading
from wsgiref.simple_server import WSGIServer, make_server, WSGIRequestHandler
from SocketServer import ThreadingMixIn
import sys

GObject.threads_init()
Gst.init(sys.argv)

class MyWSGIServer(ThreadingMixIn, WSGIServer):
     pass

INDEX_PAGE = """
<html>
<head><title>Gstreamer testing</title></head>
<body><video src="/mjpeg_stream"/></body>
</html>
"""
ERROR_404 = """
<html>
  <head><title>404 - Not Found</title></head>
  <body><h1>404 - Not Found</h1></body>
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
        self._stream.listen(self._read_stream)

    def _read_stream(self, b):
        for q in self.queues:
            q.put(b)
        return len(self.queues) > 0

    def _start_streaming(self, start_response):
        #start_response('200 OK', [('Content-type', 'multipart/x-mixed-replace; boundary=--break')])
        start_response('200 OK', [('Content-type', 'video/webm')])

        self._start_reading()
        q = Queue()
        self.queues.append(q)
        while True:
            try:
                yield q.get()
            except:
                if q in self.queues:
                    self.queues.remove(q)
                return

#src = Gst.ElementFactory.make('v4l2src', 'video-source')
src = Gst.ElementFactory.make('videotestsrc', 'video-source')
#src.props.num_buffers = 250
queue = Gst.ElementFactory.make('queue', 'queue')
tee = Gst.ElementFactory.make('tee', 'tee')

pipeline = Gst.Pipeline()
pipeline.add(src)
pipeline.add(queue)
pipeline.add(tee)
src.link(queue)
queue.link(tee)

#mjpeg_sink = MJPEGSink('stream')
#pipeline.add(mjpeg_sink._bin)
#tee.link(mjpeg_sink._bin)

#snap_sink = SnapshotSink('snap')
#pipeline.add(snap_sink._bin)
#tee.link(snap_sink._bin)

webm_sink = WebMSink('snap')
pipeline.add(webm_sink._bin)
tee.link(webm_sink._bin)

Gst.debug_bin_to_dot_file(pipeline, Gst.DebugGraphDetails.ALL, "hi")

app = StreamerApp(webm_sink)
port = 5005
httpd = make_server('', port, app, MyWSGIServer, WSGIRequestHandler)
thrd = threading.Thread(target=httpd.serve_forever)
thrd.daemon = True
thrd.start()

pipeline.set_state(Gst.State.PLAYING)
loop = GObject.MainLoop()
loop.run()
