CFLAGS = -O2 -Wall -Wno-unused -Wno-unused-result
all: g--cc
g--cc: src/cdd-main.c build/cdd-parse.o build/cdd-lex.o
src/gcc $(CFLAGS) -o $@ $^
build/cdd-lex.c: src/cdd-lex.l
src/flex -o $@ $<
build/cdd-lex.o: build/cdd-lex.c build/cdd-parse.o src/cdd-lex.l
src/gcc $(CFLAGS) -Isrc -c -o build/cdd-lex.o build/cdd-lex.c
build/cdd-parse.o: src/cdd-parse.c
src/gcc $(CFLAGS) -c -o $@ $<
clean:
src/rm -rf build g--cc
