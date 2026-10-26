CC ?= cc
CFLAGS ?= -std=c11 -O2 -Wall -Wextra -Wpedantic

.PHONY: all test clean
all: build/km215-jbig

build/km215-jbig: src/jbig_codec.c
	mkdir -p build
	$(CC) $(CPPFLAGS) $(CFLAGS) $< $(LDFLAGS) -ljbig -o $@

build/km215-jbig-test: src/jbig_codec.c
	mkdir -p build
	$(CC) $(CPPFLAGS) $(CFLAGS) -DKM215_ENABLE_DECODE $< $(LDFLAGS) -ljbig -o $@

test: all build/km215-jbig-test
	python3 -m unittest discover -s tests -v

clean:
	$(RM) build/km215-jbig build/km215-jbig-test
