#!/usr/bin/env python

import gi
gi.require_version('Gst', '1.0')
from gi.repository import GObject, Gst, GstApp
import buffer_utils

class StreamSink(object):
    def __init__(self, name='stream-sink'):
        self._listeners = []
        self._bin = Gst.Bin.new(name)
        def make_element(*args):
            ret = Gst.ElementFactory.make(*args)
            if ret is None:
                raise RuntimeError("Couldn't find element %s" % (args[0]))
            else:
                self._bin.add(ret)
                return ret

        self._valve = make_element('valve', 'valve')
        self._rate = make_element('videorate', 'rate')
        self._scale = make_element('videoscale', 'scale')
        self._enc = make_element('jpegenc', 'enc')
        self._mux = make_element('multipartmux', 'mux')
        self._sink = make_element('appsink', 'sink')

        self._mux.props.boundary = 'break'
        self._valve.props.drop = False

        self._sink.props.emit_signals = True
        self._sink.connect('new-sample', self._new_sample)

        caps = Gst.Caps.new_empty_simple('video/x-raw')
        caps.set_value('framerate', '10/1')

        self._bin.add_pad(Gst.GhostPad.new('src', self._valve.get_static_pad('sink')))
        #self._valve.link_filtered(self._rate, caps)
        self._valve.link(self._rate)
        self._rate.link(self._scale)
        self._scale.link(self._enc)
        self._enc.link(self._mux)
        self._mux.link(self._sink)

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
        print 'asdf'
        self._listeners.append(cb)
        self._valve.props.drop = False
