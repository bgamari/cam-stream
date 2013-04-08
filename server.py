import gi
gi.require_version('Gst', '1.0')
from gi.repository import GObject, Gst, GstApp
from stream import Stream
import threading

GObject.threads_init()
Gst.init(None)

#src = Gst.ElementFactory.make('v4l2src', 'video-source')
src = Gst.ElementFactory.make('videotestsrc', 'video-source')

stream = Stream(src)
stream.start()

loop = GObject.MainLoop()
loop.run()
