#!/usr/bin/env python

import gi
gi.require_version('Gst', '1.0')
from gi.repository import GObject, Gst, GstApp
import buffer_utils

class ValvedSink(object):
    def _make_element(self, *args):
        ret = Gst.ElementFactory.make(*args)
        if ret is None:
            raise RuntimeError("Couldn't find element %s" % (args[0]))
        else:
            self._bin.add(ret)
            return ret

    def __init__(self, name='stream-sink', *args, **kwargs):
        self._listeners = []
        self._bin = Gst.Bin.new(name)

        self._valve = self._make_element('valve', 'valve')
        self._queue = self._make_element('queue', 'queue')
        self._sink = self._make_element('appsink', 'sink')
        self._create_filter(self._valve, self._queue, *args, **kwargs)

        self._sink.props.emit_signals = True
        self._sink.connect('new-sample', self._new_sample)

        self._queue.link(self._sink)

        self._bin.add_pad(Gst.GhostPad.new('src', self._valve.get_static_pad('sink')))

    def _new_sample(self, appsink):
        sample = appsink.pull_sample()
        buf = sample.get_buffer()
        b = buffer_utils.get_buffer_data(buf)

        for listener in self._listeners:
            ret = listener(b)
            if not ret:
                self._listeners.remove(listener)

        if len(self._listeners) == 0:
            self._valve.props.drop = True

        return Gst.FlowReturn.OK

    def listen(self, cb):
        self._listeners.append(cb)
        self._valve.props.drop = False

class MJPEGSink(ValvedSink):
    def _create_filter(self, src, sink):
        self._rate = self._make_element('videorate', 'rate')
        self._scale = self._make_element('videoscale', 'scale')
        self._enc = self._make_element('jpegenc', 'enc')
        self._mux = self._make_element('multipartmux', 'mux')

        self._mux.props.boundary = 'break'
        self._valve.props.drop = True

        src.link(self._rate)
        self._rate.link_filtered(self._scale,
                                 Gst.caps_from_string('video/x-raw, framerate=8/1')
                                 )
        self._scale.link(self._enc)
        self._enc.link(self._mux)
        self._mux.link(sink)

class SnapshotSink(ValvedSink):
    def _create_filter(self, src, sink):
        self._rate = self._make_element('videorate', 'rate')
        self._scale = self._make_element('videoscale', 'scale')
        self._enc = self._make_element('jpegenc', 'enc')

        self._valve.props.drop = True

        src.link(self._rate)
        self._rate.link_filtered(self._scale,
                                 Gst.caps_from_string('video/x-raw, framerate=8/1')
                                 )
        self._scale.link(self._enc)
        self._enc.link(sink)

class WebMSink(ValvedSink):
    def _create_filter(self, src, sink):
        self._rate = self._make_element('videorate', 'rate')
        self._scale = self._make_element('videoscale', 'scale')
        self._enc = self._make_element('vp8enc', 'enc')
        self._mux = self._make_element('webmmux', 'mux')

        self._valve.props.drop = True
        self._mux.props.streamable = True

        src.link(self._rate)
        self._rate.link_filtered(self._scale,
                                 Gst.caps_from_string('video/x-raw, framerate=30/1')
                                 )
        self._scale.link(self._enc)
        self._enc.link(self._mux)
        self._mux.link(sink)
