/* SPDX-License-Identifier: GPL-2.0-or-later */
#include <stdio.h>
#include <string.h>

static int enc(const char *path)
{
	FILE *f = fopen(path, "rb");
	int c;

	if (!f)
		return 1;
	while ((c = fgetc(f)) != EOF)
		printf("%02x", c);
	fclose(f);
	return 0;
}

static int dec(const char *hex, const char *path)
{
	FILE *f;
	size_t n = strlen(hex);
	size_t i;

	if (n < 2 || (n % 2) != 0)
		return 1;
	f = fopen(path, "wb");
	if (!f)
		return 1;
	for (i = 0; i < n; i += 2) {
		unsigned int b;
		char tmp[3] = { hex[i], hex[i + 1], 0 };

		if (sscanf(tmp, "%2x", &b) != 1) {
			fclose(f);
			return 1;
		}
		fputc((int)b, f);
	}
	fclose(f);
	return 0;
}

int main(int argc, char **argv)
{
	if (argc == 3 && strcmp(argv[1], "enc") == 0)
		return enc(argv[2]);
	if (argc == 4 && strcmp(argv[1], "dec") == 0)
		return dec(argv[2], argv[3]);
	fprintf(stderr, "usage: walnutpi-hex enc FILE | dec HEX FILE\n");
	return 1;
}
