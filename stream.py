#!/usr/bin/env python

import gi
gi.require_version('Gst', '1.0')
from gi.repository import GObject, Gst, GstApp
import buffer_utils

class Stream(object):
    def __init__(self, src):
        self._stream_listeners = []
        self._snapshot_listeners = []

        self._pipeline = Gst.Pipeline()
        self._pipeline.add(src)
        def make_element(*args):
            ret = Gst.ElementFactory.make(*args)
            if ret is None:
                raise RuntimeError("Couldn't find element %s" % (args[0]))
            else:
                self._pipeline.add(ret)
                return ret

        self._tee = make_element('tee', 'tee')

        self._stream_valve = make_element('valve', 'stream-valve')
        self._stream_rate = make_element('videorate', 'stream-rate')
        self._stream_scale = make_element('videoscale', 'stream-scale')
        self._stream_enc = make_element('jpegenc', 'stream-enc')
        self._stream_mux = make_element('multipartmux', 'stream-mux')
        self._stream_sink = make_element('appsink', 'stream-sink')

        #snapshot_valve = make_element('valve', 'snapshot-valve')
        #snapshot_enc = make_element('jpegenc', 'snapshot-enc')
        #snapshot_sink = make_element('appsink', 'snapshot-sink')

        self._stream_mux.props.boundary = 'break'
        self._stream_valve.props.drop = False

        self._stream_sink.props.emit_signals = True
        self._stream_sink.connect('new-sample', self._new_stream_sample)

        src.link(self._tee)

        caps = Gst.Caps.new_empty_simple('video/x-rgb')
        caps.set_value('framerate', 10)

        self._tee.link(self._stream_valve)
        self._stream_valve.link(self._stream_rate)
        self._stream_rate.link(self._stream_scale)
        self._stream_scale.link(self._stream_enc)
        self._stream_enc.link(self._stream_mux)
        self._stream_mux.link(self._stream_sink)

        #tee.link(snapshot_valve)
        #snapshot_valve.link(snapshot_scale)

    def _new_stream_sample(self, appsink):
        sample = appsink.pull_sample()
        buf = sample.get_buffer()
        b = buffer_utils.get_buffer_data(buf)

        for listener in self._stream_listeners:
            ret = listener(b)
            if not ret:
                self._stream_listeners.remove(listener)

        if len(self._stream_listeners) == 0:
            self._stream_valve.props.drop = True

        return Gst.FlowReturn.OK

    def listen_stream(self, cb):
        self._stream_listeners.append(cb)
        self._stream_valve.props.drop = False

    def start(self):
        self._pipeline.set_state(Gst.State.PLAYING)
