/* SPDX-License-Identifier: GPL-2.0-or-later */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <zlib.h>
#include "deflate_preprocess.h"
#include "util.h"

#define ZREC_MAGIC "\x5a\x52\x45\x43"
#define ZREC_MAGIC_LEN 4
#define ZREC_HDR_SIZE 16

typedef struct {
	uint64_t orig_offset;
	uint64_t compressed_len;
	uint64_t raw_len;
	uint8_t zlib_cmf;
	uint8_t zlib_flg;
} zrec_stream_meta;

int deflate_scan_and_decompress(const unsigned char *in_buf, i64 in_len,
                                unsigned char **out_buf, i64 *out_len)
{
	if (!in_buf || in_len < 512)
		return 0;

	/* Scan for zlib header (0x78 0x9C, 0x78 0x01, 0x78 0xDA, 0x78 0x5E) */
	i64 i = 0;
	int found_count = 0;
	zrec_stream_meta meta[16];
	size_t raw_total_allocated = 0;
	unsigned char *raw_streams[16] = {0};

	while (i < in_len - 32 && found_count < 16) {
		if (in_buf[i] == 0x78 && (in_buf[i+1] == 0x9c || in_buf[i+1] == 0x01 || in_buf[i+1] == 0xda || in_buf[i+1] == 0x5e)) {
			/* Try inflating this candidate */
			z_stream strm;
			memset(&strm, 0, sizeof(strm));
			if (inflateInit(&strm) == Z_OK) {
				size_t out_cap = 1024 * 1024;
				unsigned char *out_p = (unsigned char *)malloc(out_cap);
				strm.next_in = (Bytef *)(in_buf + i);
				strm.avail_in = (uInt)MIN(in_len - i, 16 * 1024 * 1024);
				strm.next_out = (Bytef *)out_p;
				strm.avail_out = (uInt)out_cap;

				int ret = inflate(&strm, Z_FINISH);
				if (ret == Z_STREAM_END && strm.total_out > 1024) {
					/* Verify bit-exact round trip by re-deflating */
					z_stream def_strm;
					memset(&def_strm, 0, sizeof(def_strm));
					int level = (in_buf[i+1] == 0xda) ? 9 : (in_buf[i+1] == 0x01) ? 1 : 6;
					if (deflateInit(&def_strm, level) == Z_OK) {
						size_t check_cap = strm.total_in + 128;
						unsigned char *check_p = (unsigned char *)malloc(check_cap);
						def_strm.next_in = (Bytef *)out_p;
						def_strm.avail_in = (uInt)strm.total_out;
						def_strm.next_out = (Bytef *)check_p;
						def_strm.avail_out = (uInt)check_cap;

						int def_ret = deflate(&def_strm, Z_FINISH);
						deflateEnd(&def_strm);

						if (def_ret == Z_STREAM_END && def_strm.total_out == strm.total_in &&
						    memcmp(check_p, in_buf + i, strm.total_in) == 0) {
							/* Bit-exact match confirmed! */
							meta[found_count].orig_offset = (uint64_t)i;
							meta[found_count].compressed_len = (uint64_t)strm.total_in;
							meta[found_count].raw_len = (uint64_t)strm.total_out;
							meta[found_count].zlib_cmf = in_buf[i];
							meta[found_count].zlib_flg = in_buf[i+1];
							raw_streams[found_count] = out_p;
							raw_total_allocated += strm.total_out;
							found_count++;
							i += strm.total_in;
							free(check_p);
							inflateEnd(&strm);
							continue;
						}
						free(check_p);
					}
				}
				free(out_p);
				inflateEnd(&strm);
			}
		}
		i++;
	}

	if (found_count == 0)
		return 0;

	/* Calculate total output length */
	i64 metadata_size = ZREC_HDR_SIZE + found_count * sizeof(zrec_stream_meta);
	i64 total_out_size = metadata_size + in_len + raw_total_allocated;
	unsigned char *out = (unsigned char *)malloc(total_out_size);
	if (!out) {
		for (int k = 0; k < found_count; k++) free(raw_streams[k]);
		return 0;
	}

	/* Write ZREC Header */
	memcpy(out, ZREC_MAGIC, ZREC_MAGIC_LEN);
	*(uint32_t *)(out + 4) = (uint32_t)found_count;
	*(uint64_t *)(out + 8) = (uint64_t)in_len;
	memcpy(out + ZREC_HDR_SIZE, meta, found_count * sizeof(zrec_stream_meta));

	/* Copy original buffer and replace streams */
	unsigned char *dst = out + metadata_size;
	i64 curr_in = 0;
	for (int k = 0; k < found_count; k++) {
		i64 copy_len = meta[k].orig_offset - curr_in;
		if (copy_len > 0) {
			memcpy(dst, in_buf + curr_in, copy_len);
			dst += copy_len;
		}
		memcpy(dst, raw_streams[k], meta[k].raw_len);
		dst += meta[k].raw_len;
		curr_in = meta[k].orig_offset + meta[k].compressed_len;
		free(raw_streams[k]);
	}
	if (in_len > curr_in) {
		memcpy(dst, in_buf + curr_in, in_len - curr_in);
		dst += (in_len - curr_in);
	}

	*out_buf = out;
	*out_len = dst - out;
	return 1;
}

int deflate_reconstruct(const unsigned char *in_buf, i64 in_len,
                        unsigned char **out_buf, i64 *out_len)
{
	if (!in_buf || in_len < ZREC_HDR_SIZE)
		return 0;

	if (memcmp(in_buf, ZREC_MAGIC, ZREC_MAGIC_LEN) != 0)
		return 0;

	uint32_t count = *(uint32_t *)(in_buf + 4);
	uint64_t orig_in_len = *(uint64_t *)(in_buf + 8);

	if (count == 0 || count > 100)
		return 0;

	i64 metadata_size = ZREC_HDR_SIZE + count * sizeof(zrec_stream_meta);
	const zrec_stream_meta *meta = (const zrec_stream_meta *)(in_buf + ZREC_HDR_SIZE);

	unsigned char *out = (unsigned char *)malloc(orig_in_len);
	if (!out)
		return 0;

	const unsigned char *src = in_buf + metadata_size;
	i64 curr_out = 0;

	for (uint32_t k = 0; k < count; k++) {
		i64 copy_len = meta[k].orig_offset - curr_out;
		if (copy_len > 0) {
			memcpy(out + curr_out, src, copy_len);
			src += copy_len;
			curr_out += copy_len;
		}

		/* Re-deflate the raw stream */
		z_stream def_strm;
		memset(&def_strm, 0, sizeof(def_strm));
		int level = (meta[k].zlib_flg == 0xda) ? 9 : (meta[k].zlib_flg == 0x01) ? 1 : 6;

		if (deflateInit(&def_strm, level) == Z_OK) {
			def_strm.next_in = (Bytef *)src;
			def_strm.avail_in = (uInt)meta[k].raw_len;
			def_strm.next_out = (Bytef *)(out + curr_out);
			def_strm.avail_out = (uInt)meta[k].compressed_len;

			deflate(&def_strm, Z_FINISH);
			deflateEnd(&def_strm);
		}

		src += meta[k].raw_len;
		curr_out += meta[k].compressed_len;
	}

	if (orig_in_len > curr_out) {
		memcpy(out + curr_out, src, orig_in_len - curr_out);
	}

	*out_buf = out;
	*out_len = orig_in_len;
	return 1;
}
