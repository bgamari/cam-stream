#!/usr/bin/python3

import os
import sys
import gi
gi.require_version("Gst", "1.0")
gi.require_version("GstApp", "1.0")
from gi.repository import Gst
from gi.repository import GLib
from gi.repository import Gio
from gi.repository import GstApp
from gi.repository import GObject

import aiohttp
from aiohttp import web
import asyncio


class Source(object):
    def __init__(self, pipeline_desc):
        desc = pipeline_desc.format(fd=1)
        self.fds = {}
        print('pipeline: %s' % desc)
        self.pipeline = Gst.Pipeline()
        self.bin = Gst.parse_bin_from_description(desc, True)
        self.pipeline.add(self.bin)
        self.sink = self.pipeline.get_by_name('sink')
        self.sink.connect('client-removed', self.on_client_removed)
        self.add_signal = GObject.signal_lookup('add', self.sink.g_type_instance.g_class.g_type)
        Gst.debug_bin_to_dot_file(self.pipeline, Gst.DebugGraphDetails.ALL, "graph.dot")

    async def start(self):
        s = self.pipeline.set_state(Gst.State.PLAYING)
        print(s)
        #self.transport, _ = await loop.connect_read_pipe(QueueProtocol, self.f)

    def on_client_removed(self, sink, fd, status):
        event = self.fds.get(fd)
        if event is None:
            print("unknown socket %d" % fd)
        else:
            print("removed %d" % fd)
            event.set()

    async def add_sink(self, fd):
        self.sink.emit('add', fd)
        event = asyncio.Event()
        self.fds[fd] = event
        await event.wait()

    def stop(self):
        self.bin.set_state(Gst.State.NULL)

Gst.init(sys.argv)
#pipeline_desc = "v4l2src device=/dev/video1 ! video/x-raw,format=YUY2,framerate=25/1 ! videoconvert ! vp8enc ! webmmux streamable=true ! multifdsink name=sink"
pipeline_desc = "v4l2src device=/dev/video1 ! video/x-raw,format=BGR,framerate=15/1 ! videoconvert ! vaapipostproc ! tee name=t ! vaapivp8enc ! webmmux streamable=true ! multifdsink name=sink t. ! queue2 ! autovideosink "
#pipeline_desc = "v4l2src device=/dev/video1 ! video/x-raw,format=BGR,framerate=15/1 ! videoconvert ! vaapipostproc ! vaapivp8enc ! webmmux streamable=true ! multifdsink name=sink"

src = Source(pipeline_desc)

async def handle(request):
    print(request)
    resp = web.StreamResponse()
    resp.content_length = -1
    #resp.content_type = 'multipart/x-mixed-replace: dou'
    resp.content_type = 'video/webm'
    await resp.prepare(request)
    await resp.drain()

    fd = request.transport._sock_fd
    print('started')
    await src.add_sink(fd)
    print('done')
    return resp

app = web.Application()
app.router.add_get('/', handle)
loop = app.loop
app.loop.create_task(src.start())

async def glib_loop():
    ctx = GLib.MainContext.default()
    while True:
        while ctx.pending():
            ctx.iteration(False)
        await asyncio.sleep(0.001)

#app.loop.create_task(glib_loop())

try:
    print("serving...")
    web.run_app(app)
finally:
    print('done')
    src.stop()
