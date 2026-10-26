/* SPDX-License-Identifier: GPL-2.0-or-later */
/* Native JBIG-KIT bridge; production builds contain only the encoder. */
#include <errno.h>
#include <jbig.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#ifdef KM215_ENABLE_DECODE
#include <stdint.h>
#include <sys/resource.h>
static unsigned long be32(const unsigned char *p) {
    return ((unsigned long)p[0] << 24) | ((unsigned long)p[1] << 16)
           | ((unsigned long)p[2] << 8) | p[3];
}
#endif

#define MAX_DIM 16384UL
#define MAX_BYTES (64UL * 1024 * 1024)

static int failed;
static void emit(unsigned char *data, size_t size, void *unused) {
    (void)unused;
    if (fwrite(data, 1, size, stdout) != size) failed = 1;
}
static unsigned long number(const char *s) {
    char *end;
    errno = 0;
    unsigned long n = strtoul(s, &end, 10);
    if (errno || !*s || *end || n == 0 || n > MAX_DIM) return 0;
    return n;
}
int main(int argc, char **argv) {
    if (argc == 4 && strcmp(argv[1], "encode") == 0) {
        unsigned long w = number(argv[2]), h = number(argv[3]);
        if (!w || !h) { fputs("invalid dimensions\n", stderr); return 2; }
        size_t size = ((w + 7) / 8) * h;
        unsigned char *image = malloc(size);
        if (!image) return 2;
        if (fread(image, 1, size, stdin) != size || getchar() != EOF || ferror(stdin)) {
            fputs("raster length mismatch\n", stderr); free(image); return 2;
        }
        struct jbg_enc_state enc;
        unsigned char *planes[] = {image};
        jbg_enc_init(&enc, w, h, 1, planes, emit, NULL);
        jbg_enc_layers(&enc, 0);
        /* ONG8e.dll BIH: order=03, options=48, MX=MY=0, L0=height. */
        jbg_enc_options(&enc, JBG_ILEAVE | JBG_SMID,
                        JBG_LRLTWO | JBG_TPBON, h, 0, 0);
        jbg_enc_out(&enc);
        jbg_enc_free(&enc);
        free(image);
        return failed || fflush(stdout) != 0 ? 2 : 0;
    }
#ifdef KM215_ENABLE_DECODE
    if (argc == 2 && strcmp(argv[1], "decode") == 0) {
        unsigned char bih[20];
        if (fread(bih, 1, sizeof(bih), stdin) != sizeof(bih)) return 2;
        unsigned long w = be32(bih + 4), h = be32(bih + 8);
        if (bih[0] || bih[1] || bih[2] != 1 || bih[3] ||
            !w || w > MAX_DIM || !h || h > MAX_DIM || be32(bih + 12) != h ||
            bih[16] || bih[17] || bih[18] != 3 || bih[19] != 0x48) {
            fputs("unsupported JBIG profile\n", stderr); return 2;
        }
        struct rlimit memory = {512UL * 1024 * 1024, 512UL * 1024 * 1024};
        struct rlimit cpu = {10, 10}, core = {0, 0};
        if (setrlimit(RLIMIT_AS, &memory) || setrlimit(RLIMIT_CPU, &cpu) ||
            setrlimit(RLIMIT_CORE, &core)) return 2;
        struct jbg_dec_state dec;
        jbg_dec_init(&dec);
        jbg_dec_maxsize(&dec, MAX_DIM, MAX_DIM);
        unsigned char block[8192];
        size_t got, consumed = 0, total = 0;
        int status = jbg_dec_in(&dec, bih, sizeof(bih), &consumed);
        total = sizeof(bih);
        if (status != JBG_EAGAIN || consumed != sizeof(bih)) {
            jbg_dec_free(&dec); return 2;
        }
        while ((got = fread(block, 1, sizeof(block), stdin)) > 0) {
            total += got;
            if (total > MAX_BYTES) { status = JBG_EINVAL; break; }
            status = jbg_dec_in(&dec, block, got, &consumed);
            if (status == JBG_EOK) {
                if (consumed != got || getchar() != EOF) status = JBG_EINVAL;
                break;
            }
            if (status != JBG_EAGAIN) break;
        }
        if (status != JBG_EOK || ferror(stdin) || dec.planes != 1) {
            fprintf(stderr, "JBIG decode failed: %s\n", jbg_strerror(status));
            jbg_dec_free(&dec); return 2;
        }
        fprintf(stderr, "%lu %lu\n", jbg_dec_getwidth(&dec), jbg_dec_getheight(&dec));
        emit(jbg_dec_getimage(&dec, 0), jbg_dec_getsize(&dec), NULL);
        jbg_dec_free(&dec);
        return failed || fflush(stdout) != 0 ? 2 : 0;
    }
#endif
    fputs("usage: km215-jbig encode WIDTH HEIGHT < raster > image.jbg\n"
          , stderr);
    return 2;
}
