#define _GNU_SOURCE
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>
#include "dxt_preprocess.h"
#include "util.h"

/* Magic header for DXT transpose container: "DXT\x01" */
#define DXT_MAGIC "\x44\x58\x54\x01"
#define DXT_MAGIC_LEN 4

/* Header structure:
 * 4 bytes: Magic ("DXT\x01")
 * 4 bytes: Type (1 = DXT1, 5 = DXT5)
 * 8 bytes: Original block count
 * 8 bytes: Original uncompressed size
 */

#define DXT_HDR_SIZE 24

int dxt_transpose_buffer(const unsigned char *in_buf, i64 in_len,
                        unsigned char **out_buf, i64 *out_len)
{
	i64 i, blocks;
	int dxt_type = 0;
	size_t block_size;
	unsigned char *out;

	if (!in_buf || in_len < 1024)
		return 0;

	/* Quick scan for DXT format markers or signatures in buffer */
	if (memmem(in_buf, MIN(in_len, 4096), "DXT1", 4) != NULL) {
		dxt_type = 1;
		block_size = 8;
	} else if (memmem(in_buf, MIN(in_len, 4096), "DXT5", 4) != NULL) {
		dxt_type = 5;
		block_size = 16;
	} else {
		/* Heuristic check: if buffer length is a multiple of 8 or 16 */
		if (in_len % 16 == 0 && in_len >= 65536) {
			dxt_type = 5;
			block_size = 16;
		} else if (in_len % 8 == 0 && in_len >= 65536) {
			dxt_type = 1;
			block_size = 8;
		} else {
			return 0;
		}
	}

	blocks = in_len / block_size;
	if (blocks < 64)
		return 0;

	*out_len = DXT_HDR_SIZE + in_len;
	out = (unsigned char *)malloc(*out_len);
	if (!out)
		return 0;

	/* Write Header */
	memcpy(out, DXT_MAGIC, DXT_MAGIC_LEN);
	*(uint32_t *)(out + 4) = (uint32_t)dxt_type;
	*(uint64_t *)(out + 8) = (uint64_t)blocks;
	*(uint64_t *)(out + 16) = (uint64_t)in_len;

	/* Perform AOS -> SOA Transpose */
	unsigned char *dst = out + DXT_HDR_SIZE;
	if (dxt_type == 1) {
		/* DXT1: 8 bytes per block (4 bytes endpoints + 4 bytes selectors) */
		for (size_t b = 0; b < 8; b++) {
			for (i = 0; i < blocks; i++) {
				*dst++ = in_buf[i * 8 + b];
			}
		}
		/* Append remaining tail bytes if any */
		if (in_len > blocks * 8) {
			memcpy(dst, in_buf + blocks * 8, in_len - blocks * 8);
		}
	} else {
		/* DXT5: 16 bytes per block (8 bytes alpha + 8 bytes color) */
		for (size_t b = 0; b < 16; b++) {
			for (i = 0; i < blocks; i++) {
				*dst++ = in_buf[i * 16 + b];
			}
		}
		/* Append remaining tail bytes if any */
		if (in_len > blocks * 16) {
			memcpy(dst, in_buf + blocks * 16, in_len - blocks * 16);
		}
	}

	*out_buf = out;
	return 1;
}

int dxt_untranspose_buffer(const unsigned char *in_buf, i64 in_len,
                          unsigned char **out_buf, i64 *out_len)
{
	i64 i, blocks, orig_len;
	int dxt_type;
	size_t block_size;
	unsigned char *out;

	if (!in_buf || in_len < DXT_HDR_SIZE)
		return 0;

	if (memcmp(in_buf, DXT_MAGIC, DXT_MAGIC_LEN) != 0)
		return 0;

	dxt_type = (int)*(uint32_t *)(in_buf + 4);
	blocks = (i64)*(uint64_t *)(in_buf + 8);
	orig_len = (i64)*(uint64_t *)(in_buf + 16);

	if (dxt_type == 1)
		block_size = 8;
	else if (dxt_type == 5)
		block_size = 16;
	else
		return 0;

	out = (unsigned char *)malloc(orig_len);
	if (!out)
		return 0;

	const unsigned char *src = in_buf + DXT_HDR_SIZE;
	if (dxt_type == 1) {
		/* SOA -> AOS Untranspose for DXT1 */
		for (size_t b = 0; b < 8; b++) {
			for (i = 0; i < blocks; i++) {
				out[i * 8 + b] = *src++;
			}
		}
		if (orig_len > blocks * 8) {
			memcpy(out + blocks * 8, src, orig_len - blocks * 8);
		}
	} else {
		/* SOA -> AOS Untranspose for DXT5 */
		for (size_t b = 0; b < 16; b++) {
			for (i = 0; i < blocks; i++) {
				out[i * 16 + b] = *src++;
			}
		}
		if (orig_len > blocks * 16) {
			memcpy(out + blocks * 16, src, orig_len - blocks * 16);
		}
	}

	*out_buf = out;
	*out_len = orig_len;
	return 1;
}
