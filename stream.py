#!/usr/bin/python3

import os
import sys
import gi
gi.require_version("Gst", "1.0")
gi.require_version("GstApp", "1.0")
from gi.repository import Gst
from gi.repository import GLib
from gi.repository import GstApp

import aiohttp
from aiohttp import web
import asyncio


class Source(object):
    def __init__(self, pipeline_desc):
        self.sinks = []
        desc = pipeline_desc.format(fd=1)
        print('pipeline: %s' % desc)
        pipeline = Gst.Pipeline()
        self.bin = Gst.parse_bin_from_description(desc, True)
        pipeline.add(self.bin)
        self.sink = GstApp.AppSink()
        pipeline.add(self.sink)
        self.bin.link(self.sink)
        Gst.debug_bin_to_dot_file(self.bin, Gst.DebugGraphDetails.ALL, "graph.dot")
        self.sink.connect('new-sample', self.have_buffer)
        #self.sink.connect('new-preroll', self.have_buffer)
        self.bin = pipeline

    def have_buffer(self, appsink):
        sample = appsink.try_pull_sample(0)
        buf = sample.get_buffer()
        (result, map_info) = buf.map(Gst.MapFlags.READ)
        assert result
        try:
            for q in self.sinks:
                try:
                    print('@')
                    q.put_nowait(map_info.data)
                except asyncio.queues.QueueFull as e:
                    print("Queue filled, removing")
                    del self.sinks[q]

        finally:
            buf.unmap(map_info)

        return Gst.FlowReturn.OK

    async def start(self):
        class QueueProtocol(asyncio.Protocol):
            def data_received(proto, d):
                print('^')
                for q in self.sinks:
                    try:
                        print('@')
                        q.put_nowait(d)
                    except asyncio.queues.QueueFull as e:
                        print("Queue filled, removing")
                        del self.sinks[d]

            def eof_received(proto):
                print("done")

        self.sink.set_emit_signals(True)
        s = self.bin.set_state(Gst.State.PLAYING)
        print(s)
        #self.transport, _ = await loop.connect_read_pipe(QueueProtocol, self.f)

    def add_sink(self, queue):
        self.sinks.append(queue)

    def stop(self):
        self.bin.set_state(Gst.State.NULL)

Gst.init(sys.argv)
#pipeline_desc = "v4l2src device=/dev/video1 ! video/x-raw,format=YUY2,framerate=25/1 ! videoconvert ! vp8enc ! matroskamux streamable=true ! fdsink fd={fd}"
pipeline_desc = "v4l2src device=/dev/video1 ! video/x-raw,format=YUY2,framerate=25/1 ! videoconvert ! vp8enc ! webmmux streamable=true"
#pipeline_desc = "v4l2src do-timestamp=true device=/dev/video1 ! video/x-raw,format=YUY2,framerate=15/1 ! videoconvert ! queue ! matroskamux streamable=true"
#pipeline_desc = "v4l2src device=/dev/video1 ! video/x-raw,format=YUY2,framerate=25/1 ! videoconvert ! xvimagesink"
src = Source(pipeline_desc)

async def handle(request):
    print(request)
    resp = web.StreamResponse()
    #resp.content_type = 'multipart/x-mixed-replace: dou'
    resp.content_type = 'video/webm'
    await resp.prepare(request)

    q = asyncio.queues.Queue()
    src.add_sink(q)
    while True:
        d = await q.get()
        resp.write(d)
        await resp.drain()
        print('.',)

app = web.Application()
app.router.add_get('/', handle)
loop = app.loop
app.loop.create_task(src.start())

async def glib_loop():
    ctx = GLib.MainContext.default()
    while True:
        while ctx.pending():
            ctx.iteration(False)
        await asyncio.sleep(0.01)

app.loop.create_task(glib_loop())

try:
    print("serving...")
    web.run_app(app)
finally:
    print('done')
    src.stop()
