DEPS=glib-2.0 gobject-2.0 python gstreamer-1.0
LDFLAGS=$(shell pkg-config --libs $(DEPS))
CFLAGS=$(shell pkg-config --cflags $(DEPS)) -ggdb -Wall

all : buffer_utils.so

buffer_utils.so : buffer_utils.o
	gcc -shared $+ $(LDFLAGS) -o$@

buffer_utils.o : buffer_utils.c
	gcc -c -fPIC $(CFLAGS) -o$@ $<

clean :
	rm -f buffer_utils.so buffer_utils.o

.PHONY : clean all