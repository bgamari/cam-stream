#include <Python.h>
#include <pygobject-3.0/pygobject.h>
#include <gst/gst.h>

static PyObject *get_buffer_data(PyObject *self, PyObject *args)
{
  PyObject *buffer;
  if (!PyArg_ParseTuple(args, "O", &buffer))
    return NULL;

  GObject *obj = pygobject_get(buffer);
  GstBuffer *gstbuf = GST_BUFFER(obj);
  gsize size = gst_buffer_get_size(gstbuf);
  gchar* buf = malloc(size);
  gst_buffer_extract(gstbuf, 0, buf, size);

  PyObject *bytes = PyBytes_FromStringAndSize(buf, size);
  Py_INCREF(bytes);
  return bytes;
}

static PyMethodDef BufferUtilsMethods[] = {
  {"get_buffer_data",   get_buffer_data, METH_VARARGS,
   "Get a bytes object containing the data in a GstBuffer"},
  {NULL, NULL, 0, NULL}
};

PyMODINIT_FUNC initbuffer_utils(void)
{
  PyObject *m;

  m = Py_InitModule("buffer_utils", BufferUtilsMethods);
  if (m == NULL)
    return;
}
