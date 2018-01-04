#!/usr/bin/python3

import os
import sys
import argparse

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

valid_profiles = ['vaapi-webm', 'webm', 'h264', 'vaapi-h264']
# believed to be broken: h264, vaapi-h264

parser = argparse.ArgumentParser()
parser.add_argument('--profile', choices=valid_profiles, default='vaapi-webm',
                    help="Stream encoding format (%s)" % (', '.join(valid_profiles)))
parser.add_argument('--local', action='store_true', help="Show the stream locally")
parser.add_argument('--port', '-p', type=int, default=8080, help="Port number to serve on")
parser.add_argument('--mjpeg-framerate', type=int, default=5, help="Framerate of the MJPEG stream")
parser.add_argument('--mjpeg-width', type=int, default=640, help="Width of the MJPEG stream")
parser.add_argument('--mjpeg-height', type=int, default=480, help="Height of the MJPEG stream")
args = parser.parse_args()
enable_display = args.local

class Source(object):
    def __init__(self, pipeline_desc):
        desc = pipeline_desc.format(fd=1)
        print('pipeline: %s' % desc)
        self.pipeline = Gst.Pipeline()
        self.bin = Gst.parse_bin_from_description(desc, False)
        self.pipeline.add(self.bin)
        self.stream_sink = MultiFdSink(self.pipeline.get_by_name('stream_sink'), name='stream')
        self.tee = self.pipeline.get_by_name('t1')
        self.mjpeg_bin = None
        bus = self.pipeline.get_bus()

        Gst.debug_bin_to_dot_file(self.pipeline, Gst.DebugGraphDetails.ALL, "graph.dot")

    async def start(self):
        s = self.pipeline.set_state(Gst.State.PLAYING)

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

    async def add_mjpeg_sink(self, fd):
        if self.mjpeg_bin is None:
            desc = 'videorate name=in ! video/x-raw,framerate={rate}/1 ! videoscale ! video/x-raw,width={width},height={height} ! queue ! jpegenc ! multifdsink name=sink'.format(rate=args.mjpeg_framerate, width=args.mjpeg_width, height=args.mjpeg_height)
            self.mjpeg_bin = Gst.parse_bin_from_description(desc, False)
            self.mjpeg_sink = MultiFdSink(self.mjpeg_bin.get_by_name('sink'), name='mjpeg')
            self.pipeline.add(self.mjpeg_bin)
            self.tee.link(self.mjpeg_bin.get_by_name('in'))
            self.mjpeg_bin.set_state(Gst.State.PLAYING)
            Gst.debug_bin_to_dot_file(self.pipeline, Gst.DebugGraphDetails.ALL, "graph.dot")

        await self.mjpeg_sink.add_fd(fd)

        if self.mjpeg_sink.active_clients() == 0:
            self.tee.unlink(self.mjpeg_bin)
            self.mjpeg_bin.set_state(Gst.State.NULL)
            self.pipeline.remove(self.mjpeg_bin)
            self.mjpeg_bin = None

    async def add_stream_sink(self, fd):
        await self.stream_sink.add_fd(fd)

    def stop(self):
        self.bin.set_state(Gst.State.NULL)

class MultiFdSink(object):
    def __init__(self, sink, name="unknown"):
        self.sink = sink
        self.name = name
        self.sink.connect('client-removed', self._on_client_removed)
        self.fds = {}

    def active_clients(self):
        return len(self.fds)

    def _on_client_removed(self, sink, fd, status):
        event = self.fds.get(fd)
        if event is None:
            print("unknown socket %d" % fd)
        else:
            print("removed %d" % fd)
            event.set()

    async def add_fd(self, fd):
        print("%s: adding fd %d" % (self.name, fd))
        self.sink.emit('add', fd)
        event = asyncio.Event()
        self.fds[fd] = event
        await event.wait()

Gst.init(sys.argv)
input_desc = "v4l2src device=/dev/video1 ! video/x-raw,format=BGR,framerate=15/1 ! tee name=t1"
if args.profile == 'vaapi-webm':
    encode_desc = "t1. ! videoconvert ! vaapipostproc ! tee name=t"
    stream_desc = "t. ! q.sink_0 q.src_0 ! vaapivp8enc ! webmmux streamable=true ! multifdsink name=stream_sink"
elif args.profile == 'webm':
    encode_desc = "t1. ! videoconvert ! tee name=t"
    stream_desc = "t. ! q.sink_0 q.src_0 ! vp8enc ! webmmux streamable=true ! multifdsink name=stream_sink"
    input_desc = "v4l2src device=/dev/video1 ! video/x-raw,format=BGR,framerate=25/1 ! videoconvert ! vp8enc ! tee name=t"
elif args.profile == 'h264':
    encode_desc = "t1. ! videoconvert ! tee name=t"
    stream_desc = "t. ! q.sink_0 q.src_0 ! x264enc ! mp4mux ! multifdsink name=stream_sink"
elif args.profile == 'vaapi-h264':
    encode_desc = "t1. ! videoconvert ! vaapipostproc ! tee name=t"
    stream_desc = "t. ! q.sink_0 q.src_0 ! vaapih264enc ! mp4mux ! multifdsink name=stream_sink"
else:
    raise RuntimeError("unknown profile")

display_desc = "t. ! q.sink_2 q.src_2 ! queue2 ! autovideosink" if enable_display else ""
pipeline_desc = ' '.join([input_desc, stream_desc, encode_desc, display_desc, "multiqueue name=q"])
#pipeline_desc = "v4l2src device=/dev/video1 ! video/x-raw,format=BGR,framerate=15/1 ! videoconvert ! vaapipostproc ! vaapivp8enc ! webmmux streamable=true ! multifdsink name=sink"

src = Source(pipeline_desc)

async def handle_webm(request):
    print(request)
    resp = web.StreamResponse()
    resp.content_length = -1
    if args.profile != 'h264':
        resp.content_type = 'video/webm'
    else:
        # TODO
        #resp.content_type = 'video/webm'
        pass
    await resp.prepare(request)
    await resp.drain()
    fd = request.transport._sock_fd
    await src.add_stream_sink(fd)
    return resp

async def handle_mjpeg(request):
    print(request)
    resp = web.StreamResponse()
    resp.content_type = 'video/mjpeg'
    resp.content_length = -1
    await resp.prepare(request)
    await resp.drain()
    fd = request.transport._sock_fd
    await src.add_mjpeg_sink(fd)
    return resp

async def handle_jpeg(request):
    frame = await src.grab_frame()
    resp = web.Response(body=frame)
    resp.content_type = 'image/jpeg'
    await resp.prepare(request)
    resp.write(frame)
    return resp

def serve_static(path):
    async def handle(request):
        content = open(path, 'rb').read()
        resp = web.Response(body=content)
        resp.content_type = 'text/html'
        await resp.prepare(request)
        return resp

    return handle

app = web.Application()
app.router.add_get('/stream.webm', handle_webm)
app.router.add_get('/snapshot.jpeg', handle_jpeg)
app.router.add_get('/stream.mjpeg', handle_mjpeg)
app.router.add_get('/mjpeg.html', serve_static('mjpeg.html'))
app.router.add_get('/webm.html', serve_static('webm.html'))
app.router.add_get('/', serve_static('index.html'))

loop = app.loop
app.loop.create_task(src.start())

try:
    print("serving...")
    web.run_app(app, port=args.port)
finally:
    print('done')
    src.stop()
