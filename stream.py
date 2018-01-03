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
        self.bin = Gst.parse_bin_from_description(desc, False)
        self.pipeline.add(self.bin)
        self.sink = self.pipeline.get_by_name('sink')
        self.sink.connect('client-removed', self.on_client_removed)
        self.add_signal = GObject.signal_lookup('add', self.sink.g_type_instance.g_class.g_type)
        Gst.debug_bin_to_dot_file(self.pipeline, Gst.DebugGraphDetails.ALL, "graph.dot")

        bus = self.pipeline.get_bus()

        self.tee = self.pipeline.get_by_name('t1')

    async def start(self):
        s = self.pipeline.set_state(Gst.State.PLAYING)

    def on_client_removed(self, sink, fd, status):
        event = self.fds.get(fd)
        if event is None:
            print("unknown socket %d" % fd)
        else:
            print("removed %d" % fd)
            event.set()

    async def grab_frame(self):
        print('Grabbing frame')
        bin = Gst.parse_bin_from_description('jpegenc ! appsink name=sink', True)
        queue = asyncio.Queue()
        def on_frame(sink):
            print('Have frame')
            sample = sink.emit("pull-sample")
            sink.set_emit_signals(False)
            buf = sample.get_buffer()
            (result, map_info) = buf.map(Gst.MapFlags.READ)
            try:
                assert result
                queue.put_nowait(map_info.data)
            except asyncio.QueueFull as e:
                pass
            finally:
                buf.unmap(map_info)
            return Gst.FlowReturn.OK

        sink = bin.get_by_name('sink')
        sink.set_emit_signals(True)
        sink.connect('new-sample', on_frame)
        bin.set_state(Gst.State.PLAYING)
        self.bin.add(bin)
        pad = self.tee.get_compatible_pad(bin.pads[0], None)
        self.tee.link(bin)
        frame = await queue.get()
        Gst.debug_bin_to_dot_file(self.pipeline, Gst.DebugGraphDetails.ALL, "graph.dot")
        self.tee.unlink(bin)
        self.tee.release_request_pad(pad)
        bin.set_state(Gst.State.NULL)
        self.bin.remove(bin)
        del bin
        return frame

    async def add_sink(self, fd):
        self.sink.emit('add', fd)
        event = asyncio.Event()
        self.fds[fd] = event
        await event.wait()

    def stop(self):
        self.bin.set_state(Gst.State.NULL)

Gst.init(sys.argv)
#pipeline_desc = "v4l2src device=/dev/video1 ! video/x-raw,format=YUY2,framerate=25/1 ! videoconvert ! vp8enc ! webmmux streamable=true ! multifdsink name=sink"
input_desc = "v4l2src device=/dev/video1 ! video/x-raw,format=BGR,framerate=15/1 ! tee name=t1 ! videoconvert ! vaapipostproc ! tee name=t multiqueue name=q"
tee_desc = " "
stream_desc = "t. ! q.sink_0 q.src_0 ! vaapivp8enc ! webmmux streamable=true ! multifdsink name=sink"
display_desc = "t. ! q.sink_1 q.src_1 ! queue2 ! autovideosink "
pipeline_desc = ' '.join([input_desc, tee_desc, stream_desc, display_desc])
#pipeline_desc = "v4l2src device=/dev/video1 ! video/x-raw,format=BGR,framerate=15/1 ! videoconvert ! vaapipostproc ! vaapivp8enc ! webmmux streamable=true ! multifdsink name=sink"

src = Source(pipeline_desc)

async def handle_webm(request):
    print(request)
    resp = web.StreamResponse()
    resp.content_length = -1
    #resp.content_type = 'multipart/x-mixed-replace: dou'
    resp.content_type = 'video/webm'
    await resp.prepare(request)
    await resp.drain()

    fd = request.transport._sock_fd
    await src.add_sink(fd)
    return resp

async def handle_jpeg(request):
    frame = await src.grab_frame()
    resp = web.Response(body=frame)
    resp.content_type = 'image/jpeg'
    await resp.prepare(request)
    resp.write(frame)
    return resp

app = web.Application()
app.router.add_get('/webm', handle_webm)
app.router.add_get('/jpeg', handle_jpeg)
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
