#!/usr/bin/env python

import gi
gi.require_version('Gst', '1.0')
from gi.repository import GObject, Gst, GstApp
import buffer_utils

GObject.threads_init()
Gst.init(None)

pipeline = Gst.Pipeline()

def make_element(*args):
    ret = Gst.ElementFactory.make(*args)
    if ret is None:
        raise RuntimeError("Couldn't find element %s" % (args[0]))
    else:
        pipeline.add(ret)
        return ret

#src = make_element('v4l2src', 'video-source')
src = make_element('videotestsrc', 'video-source')
tee = make_element('tee', 'tee')

stream_valve = make_element('valve', 'stream-valve')
stream_rate = make_element('videorate', 'stream-rate')
stream_scale = make_element('videoscale', 'stream-scale')
stream_enc = make_element('jpegenc', 'stream-enc')
stream_sink = make_element('appsink', 'stream-sink')

#snapshot_valve = make_element('valve', 'snapshot-valve')
#snapshot_enc = make_element('jpegenc', 'snapshot-enc')
#snapshot_sink = make_element('appsink', 'snapshot-sink')

def new_stream_sample(appsink):
    sample = appsink.pull_sample()
    buf = sample.get_buffer()
    b = buffer_utils.get_buffer_data(buf)
    return Gst.FlowReturn.OK

stream_valve.props.drop = False

stream_sink.props.emit_signals = True
stream_sink.connect('new-sample', new_stream_sample)

src.link(tee)
tee.link(stream_valve)
stream_valve.link(stream_rate)
stream_rate.link(stream_scale)
stream_scale.link(stream_enc)
stream_enc.link(stream_sink)

pipeline.set_state(Gst.State.PLAYING)

loop = GObject.MainLoop()
loop.run()

launch = "v4l2src ! 'video/x-raw-rgb,width=640,height=480,framerate= 30/1' ! queue ! videorate ! 'video/x-raw-yuv/framerate=30/1' ! theor aenv ! queue ! oggmux | udp"
