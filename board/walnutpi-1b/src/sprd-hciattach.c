/*
 * sprd-hciattach — Unisoc/Spreadtrum Marlin3 (UWE5622) HCI bring-up
 *
 * ttyBT0 is H4 over SDIO, but the firmware needs vendor PSKEY/RF/enable
 * (0xFCA0 / 0xFCA2 / 0xFCA1) before the kernel HCI UART line discipline.
 * Standard btattach/hciattach H4 skips that; Write Default Link Policy
 * (0x080f) then fails and Linux aborts hci0 setup.
 *
 * Sequence matches the Allwinner/OrangePi sprd protocol, implemented here
 * in-tree so we do not ship their prebuilt hciattach_opi blob.
 */
#define _GNU_SOURCE
#include <errno.h>
#include <fcntl.h>
#include <getopt.h>
#include <linux/tty.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/ioctl.h>
#include <sys/stat.h>
#include <termios.h>
#include <time.h>
#include <unistd.h>
#include <dirent.h>

#ifndef N_HCI
#define N_HCI 15
#endif

#define HCIUARTSETPROTO	_IOW('U', 200, int)
#define HCI_UART_H4	0

#define HCI_COMMAND_PKT	0x01
#define HCI_EVENT_PKT	0x04

#define HCI_OP_PSKEY	0xfca0
#define HCI_OP_ENABLE	0xfca1
#define HCI_OP_RF	0xfca2

#define PSKEY_LEN	160
#define PSKEY_CMD_LEN	176
#define RF_LEN		252

#define ADDR_OFF	20	/* device_addr inside packed pskey */

static const char *pskey_path = "/lib/firmware/bt_configure_pskey.ini";
static const char *rf_path = "/lib/firmware/bt_configure_rf.ini";
static const char *addr_path = "/etc/default/sprd_bt_addr";

struct field {
	const char *name;
	unsigned size;
};

static const struct field pskey_fields[] = {
	{"device_class", 4},
	{"feature_set", 16},
	{"device_addr", 6},
	{"comp_id", 2},
	{"g_sys_uart0_communication_supported", 1},
	{"cp2_log_mode", 1},
	{"LogLevel", 1},
	{"g_central_or_perpheral", 1},
	{"Log_BitMask", 2},
	{"super_ssp_enable", 1},
	{"common_rfu_b3", 1},
	{"common_rfu_w", 8},
	{"le_rfu_w", 8},
	{"lmp_rfu_w", 8},
	{"lc_rfu_w", 8},
	{"g_wbs_nv_117", 2},
	{"g_wbs_nv_118", 2},
	{"g_nbv_nv_117", 2},
	{"g_nbv_nv_118", 2},
	{"g_sys_sco_transmit_mode", 1},
	{"audio_rfu_b1", 1},
	{"audio_rfu_b2", 1},
	{"audio_rfu_b3", 1},
	{"audio_rfu_w", 8},
	{"g_sys_sleep_in_standby_supported", 1},
	{"g_sys_sleep_master_supported", 1},
	{"g_sys_sleep_slave_supported", 1},
	{"power_rfu_b1", 1},
	{"power_rfu_w", 8},
	{"win_ext", 4},
	{"edr_tx_edr_delay", 1},
	{"edr_rx_edr_delay", 1},
	{"tx_delay", 1},
	{"rx_delay", 1},
	{"bb_rfu_w", 8},
	{"agc_mode", 1},
	{"diff_or_eq", 1},
	{"ramp_mode", 1},
	{"modem_rfu_b1", 1},
	{"modem_rfu_w", 8},
	{"BQB_BitMask_1", 4},
	{"BQB_BitMask_2", 4},
	{"bt_coex_threshold", 16},
	{"other_rfu_w", 8},
};

static const struct field rf_fields[] = {
	{"g_GainValue_A", 12},
	{"g_ClassicPowerValue_A", 20},
	{"g_LEPowerValue_A", 32},
	{"g_BRChannelpwrvalue_A", 16},
	{"g_EDRChannelpwrvalue_A", 16},
	{"g_LEChannelpwrvalue_A", 16},
	{"g_GainValue_B", 12},
	{"g_ClassicPowerValue_B", 20},
	{"g_LEPowerValue_B", 32},
	{"g_BRChannelpwrvalue_B", 16},
	{"g_EDRChannelpwrvalue_B", 16},
	{"g_LEChannelpwrvalue_B", 16},
	{"LE_fix_powerword", 2},
	{"Classic_pc_by_channel", 1},
	{"LE_pc_by_channel", 1},
	{"RF_switch_mode", 1},
	{"Data_Capture_Mode", 1},
	{"Analog_IQ_Debug_Mode", 1},
	{"RF_common_rfu_b3", 1},
	{"RF_common_rfu_w", 20},
};

static void put_le(uint8_t *p, unsigned width, unsigned long v)
{
	unsigned i;

	for (i = 0; i < width; i++)
		p[i] = (uint8_t)((v >> (8 * i)) & 0xff);
}

static int parse_nums(const char *s, unsigned long *out, int max)
{
	int n = 0;

	while (*s && n < max) {
		char *end = NULL;
		unsigned long v;

		while (*s == ' ' || *s == '\t' || *s == ',' || *s == '=')
			s++;
		if (*s == '\0' || *s == '#' || *s == '\n' || *s == '\r')
			break;
		v = strtoul(s, &end, 0);
		if (end == s)
			break;
		out[n++] = v;
		s = end;
	}
	return n;
}

static int pack_field(uint8_t *dst, unsigned size, const unsigned long *vals, int n)
{
	int i;
	unsigned unit;

	if (n <= 0)
		return 0;
	if (n * 1u == size)
		unit = 1;
	else if (n * 2u == size)
		unit = 2;
	else if (n * 4u == size)
		unit = 4;
	else
		return -1;
	for (i = 0; i < n; i++)
		put_le(dst + i * (int)unit, unit, vals[i]);
	return 0;
}

static int load_ini(const char *path, uint8_t *buf, unsigned buflen,
		    const struct field *fields, size_t nfields)
{
	char line[512];
	FILE *fp;
	size_t i;
	unsigned off = 0;

	memset(buf, 0, buflen);
	fp = fopen(path, "r");
	if (!fp) {
		fprintf(stderr, "sprd-hciattach: 打不开 %s: %s\n", path, strerror(errno));
		return -1;
	}
	for (i = 0; i < nfields; i++) {
		if (off + fields[i].size > buflen) {
			fclose(fp);
			return -1;
		}
		off += fields[i].size;
	}
	if (off != buflen) {
		fprintf(stderr, "sprd-hciattach: 内部长度 %u != %u\n", off, buflen);
		fclose(fp);
		return -1;
	}

	while (fgets(line, sizeof(line), fp)) {
		char *eq, *name, *p;
		unsigned long vals[32];
		int n;

		p = line;
		while (*p == ' ' || *p == '\t')
			p++;
		if (*p == '#' || *p == '[' || *p == '\0' || *p == '\n')
			continue;
		eq = strchr(p, '=');
		if (!eq)
			continue;
		*eq = '\0';
		name = p;
		while (name[0] && (name[strlen(name) - 1] == ' ' ||
				   name[strlen(name) - 1] == '\t'))
			name[strlen(name) - 1] = '\0';
		n = parse_nums(eq + 1, vals, 32);
		off = 0;
		for (i = 0; i < nfields; i++) {
			if (strcmp(name, fields[i].name) == 0) {
				if (pack_field(buf + off, fields[i].size, vals, n) < 0)
					fprintf(stderr, "sprd-hciattach: %s 装不下\n", name);
				break;
			}
			off += fields[i].size;
		}
	}
	fclose(fp);
	return 0;
}

static int read_sid_mac(uint8_t mac[6])
{
	DIR *d;
	struct dirent *de;
	uint32_t sid[4] = {0};
	int fd, n;

	d = opendir("/sys/bus/nvmem/devices");
	if (!d)
		return -1;
	while ((de = readdir(d))) {
		char path[320];
		if (de->d_name[0] == '.')
			continue;
		if (!strstr(de->d_name, "sid") && !strstr(de->d_name, "sunxi"))
			continue;
		snprintf(path, sizeof(path), "/sys/bus/nvmem/devices/%s/nvmem", de->d_name);
		fd = open(path, O_RDONLY);
		if (fd < 0)
			continue;
		n = (int)read(fd, sid, sizeof(sid));
		close(fd);
		if (n < (int)sizeof(sid) || (!sid[0] && !sid[3]))
			continue;
		mac[0] = 0x02;
		mac[1] = sid[0] & 0xff;
		mac[2] = (sid[3] >> 24) & 0xff;
		mac[3] = (sid[3] >> 16) & 0xff;
		mac[4] = (sid[3] >> 8) & 0xff;
		mac[5] = (sid[3] & 0xff) ^ 0x01;
		closedir(d);
		return 0;
	}
	closedir(d);
	return -1;
}

static int parse_mac(const char *s, uint8_t mac[6])
{
	unsigned a, b, c, d, e, f;

	if (sscanf(s, "%02x:%02x:%02x:%02x:%02x:%02x", &a, &b, &c, &d, &e, &f) != 6)
		return -1;
	mac[0] = (uint8_t)a;
	mac[1] = (uint8_t)b;
	mac[2] = (uint8_t)c;
	mac[3] = (uint8_t)d;
	mac[4] = (uint8_t)e;
	mac[5] = (uint8_t)f;
	return 0;
}

static void load_or_make_mac(uint8_t mac[6])
{
	char line[64];
	FILE *fp;

	fp = fopen(addr_path, "r");
	if (fp) {
		if (fgets(line, sizeof(line), fp) && parse_mac(line, mac) == 0) {
			fclose(fp);
			return;
		}
		fclose(fp);
	}
	if (read_sid_mac(mac) == 0)
		goto save;
	/* locally administered random */
	{
		int fd = open("/dev/urandom", O_RDONLY);
		if (fd >= 0) {
			if (read(fd, mac, 6) != 6)
				memset(mac, 0x11, 6);
			close(fd);
		} else {
			memset(mac, 0x11, 6);
		}
	}
	mac[0] = (uint8_t)((mac[0] & 0xfe) | 0x02);
save:
	fp = fopen(addr_path, "w");
	if (fp) {
		fprintf(fp, "%02X:%02X:%02X:%02X:%02X:%02X\n",
			mac[0], mac[1], mac[2], mac[3], mac[4], mac[5]);
		fclose(fp);
	}
}

static int set_raw_tty(int fd, speed_t speed)
{
	struct termios ti;

	if (tcgetattr(fd, &ti) < 0)
		return -1;
	cfmakeraw(&ti);
	ti.c_cflag |= CLOCAL;
	ti.c_cflag &= ~CRTSCTS;
	cfsetispeed(&ti, speed);
	cfsetospeed(&ti, speed);
	ti.c_cc[VMIN] = 0;
	ti.c_cc[VTIME] = 1;
	return tcsetattr(fd, TCSANOW, &ti);
}

static int timed_read(int fd, void *buf, size_t n, int timeout_ms)
{
	size_t got = 0;
	struct timespec start, now;

	clock_gettime(CLOCK_MONOTONIC, &start);
	while (got < n) {
		ssize_t r;
		long elapsed;

		clock_gettime(CLOCK_MONOTONIC, &now);
		elapsed = (now.tv_sec - start.tv_sec) * 1000 +
			  (now.tv_nsec - start.tv_nsec) / 1000000;
		if (elapsed > timeout_ms)
			return (int)got;
		r = read(fd, (uint8_t *)buf + got, n - got);
		if (r < 0) {
			if (errno == EAGAIN || errno == EINTR)
				continue;
			return -1;
		}
		if (r == 0) {
			usleep(10000);
			continue;
		}
		got += (size_t)r;
	}
	return (int)got;
}

static int hci_cmd(int fd, uint16_t opcode, const uint8_t *pay, uint8_t plen)
{
	uint8_t pkt[4 + 255];
	uint8_t ev[260];
	int n, i;

	pkt[0] = HCI_COMMAND_PKT;
	pkt[1] = (uint8_t)(opcode & 0xff);
	pkt[2] = (uint8_t)(opcode >> 8);
	pkt[3] = plen;
	if (plen)
		memcpy(pkt + 4, pay, plen);
	if (write(fd, pkt, 4 + plen) != 4 + plen) {
		fprintf(stderr, "sprd-hciattach: 写 0x%04x 失败: %s\n", opcode, strerror(errno));
		return -1;
	}

	/* Drain until command complete for this opcode. */
	for (i = 0; i < 32; i++) {
		uint8_t hdr[3];
		uint8_t type;
		unsigned elen;

		if (timed_read(fd, &type, 1, 4000) != 1)
			break;
		if (type != HCI_EVENT_PKT)
			continue;
		if (timed_read(fd, hdr, 2, 1000) != 2)
			break;
		elen = hdr[1];
		if (elen > sizeof(ev) - 3)
			elen = sizeof(ev) - 3;
		n = timed_read(fd, ev, elen, 1000);
		if (n < 0 || (unsigned)n < elen)
			break;
		/* event 0x0e command complete: ncmd, opcode le16, status */
		if (hdr[0] == 0x0e && elen >= 4) {
			uint16_t rop = (uint16_t)ev[1] | ((uint16_t)ev[2] << 8);
			if (rop == opcode) {
				if (ev[3] != 0) {
					fprintf(stderr, "sprd-hciattach: 0x%04x status 0x%02x\n",
						opcode, ev[3]);
					return -1;
				}
				return 0;
			}
		}
	}
	fprintf(stderr, "sprd-hciattach: 等 0x%04x 完成超时\n", opcode);
	return -1;
}

static void daemonize(void)
{
	pid_t pid = fork();

	if (pid < 0)
		exit(1);
	if (pid > 0)
		exit(0);
	if (setsid() < 0)
		exit(1);
	chdir("/");
	close(STDIN_FILENO);
	if (open("/dev/null", O_RDWR) < 0)
		exit(1);
	dup2(STDIN_FILENO, STDOUT_FILENO);
	dup2(STDIN_FILENO, STDERR_FILENO);
}

static void usage(const char *argv0)
{
	fprintf(stderr,
		"用法: %s [-n] [-s 波特率] [tty]\n"
		"  默认 /dev/ttyBT0，1500000，后台挂 H4。\n",
		argv0);
}

int main(int argc, char **argv)
{
	const char *dev = "/dev/ttyBT0";
	int foreground = 0;
	speed_t speed = B1500000;
	int fd, proto, ldisc, opt;
	uint8_t pskey[PSKEY_CMD_LEN];
	uint8_t rf[RF_LEN];
	uint8_t mac[6];
	uint8_t enable[3] = {0x00, 0x00, 0x01};

	while ((opt = getopt(argc, argv, "ns:h")) != -1) {
		switch (opt) {
		case 'n':
			foreground = 1;
			break;
		case 's':
			if (atoi(optarg) != 1500000)
				fprintf(stderr, "sprd-hciattach: 只用 1500000，已忽略 %s\n", optarg);
			break;
		default:
			usage(argv[0]);
			return 1;
		}
	}
	if (optind < argc)
		dev = argv[optind];

	memset(pskey, 0, sizeof(pskey));
	if (load_ini(pskey_path, pskey, PSKEY_LEN, pskey_fields,
		     sizeof(pskey_fields) / sizeof(pskey_fields[0])) < 0)
		return 1;
	if (load_ini(rf_path, rf, RF_LEN, rf_fields,
		     sizeof(rf_fields) / sizeof(rf_fields[0])) < 0)
		return 1;

	load_or_make_mac(mac);
	memcpy(pskey + ADDR_OFF, mac, 6);
	printf("sprd-hciattach: %s  MAC %02X:%02X:%02X:%02X:%02X:%02X\n",
	       dev, mac[0], mac[1], mac[2], mac[3], mac[4], mac[5]);

	fd = open(dev, O_RDWR | O_NOCTTY);
	if (fd < 0) {
		fprintf(stderr, "sprd-hciattach: 打不开 %s: %s\n", dev, strerror(errno));
		return 1;
	}
	if (set_raw_tty(fd, speed) < 0) {
		fprintf(stderr, "sprd-hciattach: 设 tty 失败: %s\n", strerror(errno));
		close(fd);
		return 1;
	}
	tcflush(fd, TCIOFLUSH);

	printf("sprd-hciattach: PSKEY 0xFCA0\n");
	if (hci_cmd(fd, HCI_OP_PSKEY, pskey, PSKEY_CMD_LEN) < 0)
		goto fail;
	printf("sprd-hciattach: RF 0xFCA2\n");
	if (hci_cmd(fd, HCI_OP_RF, rf, RF_LEN) < 0)
		goto fail;
	printf("sprd-hciattach: ENABLE 0xFCA1\n");
	if (hci_cmd(fd, HCI_OP_ENABLE, enable, 3) < 0)
		goto fail;

	ldisc = N_HCI;
	if (ioctl(fd, TIOCSETD, &ldisc) < 0) {
		fprintf(stderr, "sprd-hciattach: N_HCI 失败: %s\n", strerror(errno));
		goto fail;
	}
	proto = HCI_UART_H4;
	if (ioctl(fd, HCIUARTSETPROTO, proto) < 0) {
		fprintf(stderr, "sprd-hciattach: H4 proto 失败: %s\n", strerror(errno));
		goto fail;
	}
	printf("sprd-hciattach: H4 已挂上\n");

	if (!foreground)
		daemonize();
	/* Keep the tty fd so the line discipline stays attached. */
	for (;;)
		pause();
	return 0;
fail:
	close(fd);
	return 1;
}
