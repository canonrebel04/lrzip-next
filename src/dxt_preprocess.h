/* SPDX-License-Identifier: GPL-2.0-or-later */
#ifndef DXT_PREPROCESS_H
#define DXT_PREPROCESS_H

#include "lrzip_private.h"

#ifdef __cplusplus
extern "C" {
#endif

/*
 * DXT Texture Plane Separator (AOS -> SOA Transpose)
 * 
 * Interleaved DXT1 (8-byte blocks) and DXT5 (16-byte blocks) textures pack
 * color/alpha endpoints (smooth gradients) adjacent to index selectors (low-precision indices).
 * Transposing these blocks into separate contiguous byte planes allows entropy coders
 * like ZPAQ to compress texture assets much more effectively (+10-25% ratio boost).
 * 
 * The transform is 100% bit-exact reversible.
 */

/* Transpose DXT blocks in buffer from AOS to SOA layout.
 * Returns 1 if DXT textures were detected and transposed, 0 otherwise.
 * If transposed, *out_buf is allocated and populated with transposed data + header,
 * and *out_len is set to the new buffer length.
 */
int dxt_transpose_buffer(const unsigned char *in_buf, i64 in_len,
                        unsigned char **out_buf, i64 *out_len);

/* Reverse DXT transpose from SOA back to original AOS block layout.
 * Returns 1 on success, 0 if buffer does not contain DXT transpose header.
 * If reversed, *out_buf is allocated and *out_len receives original size.
 */
int dxt_untranspose_buffer(const unsigned char *in_buf, i64 in_len,
                          unsigned char **out_buf, i64 *out_len);

#ifdef __cplusplus
}
#endif

#endif /* DXT_PREPROCESS_H */
