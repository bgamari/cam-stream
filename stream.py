#!/usr/bin/env python

import gi
gi.require_version('Gst', '1.0')
from gi.repository import GObject, Gst, GstApp
import buffer_utils

class Stream(object):
    def __init__(self, src):
        self.stream_listeners = []
        self.snapshot_listeners = []

        self.pipeline = Gst.Pipeline()
        self.pipeline.add(src)
        def make_element(*args):
            ret = Gst.ElementFactory.make(*args)
            if ret is None:
                raise RuntimeError("Couldn't find element %s" % (args[0]))
            else:
                self.pipeline.add(ret)
                return ret

        self.tee = make_element('tee', 'tee')

        self.stream_valve = make_element('valve', 'stream-valve')
        self.stream_rate = make_element('videorate', 'stream-rate')
        self.stream_scale = make_element('videoscale', 'stream-scale')
        self.stream_enc = make_element('jpegenc', 'stream-enc')
        self.stream_sink = make_element('appsink', 'stream-sink')

        #snapshot_valve = make_element('valve', 'snapshot-valve')
        #snapshot_enc = make_element('jpegenc', 'snapshot-enc')
        #snapshot_sink = make_element('appsink', 'snapshot-sink')

        self.stream_valve.props.drop = False

        self.stream_sink.props.emit_signals = True
        self.stream_sink.connect('new-sample', self.new_stream_sample)

        src.link(self.tee)

        self.tee.link(self.stream_valve)
        self.stream_valve.link(self.stream_rate)
        self.stream_rate.link(self.stream_scale)
        self.stream_scale.link(self.stream_enc)
        self.stream_enc.link(self.stream_sink)

        #tee.link(snapshot_valve)
        #snapshot_valve.link(snapshot_scale)

    def new_stream_sample(self, appsink):
        sample = appsink.pull_sample()
        buf = sample.get_buffer()
        b = buffer_utils.get_buffer_data(buf)

        if len(self.stream_listeners) == 0:
            self.stream_valve.props.drop = True
        else:
            for listener in self.stream_listeners:
                ret = listener(b)
                if not ret:
                    self.stream_listeners.remove(listener)

        return Gst.FlowReturn.OK

    def listen_stream(self, cb):
        self.stream_listeners.append(cb)
        self.stream_valve.props.drop = False

    def start(self):
        self.pipeline.set_state(Gst.State.PLAYING)
