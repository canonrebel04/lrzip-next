/* SPDX-License-Identifier: GPL-2.0-or-later */
#ifndef DEFLATE_PREPROCESS_H
#define DEFLATE_PREPROCESS_H

#include "lrzip_private.h"
#include <zlib.h>

#ifdef __cplusplus
extern "C" {
#endif

/*
 * Precomp-style Deflate Stream Recompressor
 *
 * Scans binary data blocks for embedded zlib streams (0x78 0x9C, 0x78 0x01, 0x78 0xDA),
 * decompresses them using zlib inflate(), and stores the uncompressed raw bytes along with
 * bit-exact reconstruction metadata. This exposes raw uncompressed data to ZPAQ's context
 * mixer, dramatically improving compression ratios (+3-8%).
 *
 * On decompression, the reconstruction metadata allows bit-exact re-deflating back to
 * the original stream.
 */

int deflate_scan_and_decompress(const unsigned char *in_buf, i64 in_len,
                                unsigned char **out_buf, i64 *out_len);

int deflate_reconstruct(const unsigned char *in_buf, i64 in_len,
                        unsigned char **out_buf, i64 *out_len);

#ifdef __cplusplus
}
#endif

#endif /* DEFLATE_PREPROCESS_H */
