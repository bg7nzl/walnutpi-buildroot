/* SPDX-License-Identifier: GPL-2.0-only */
#ifndef __LINUX_MFD_AC200_H
#define __LINUX_MFD_AC200_H

#include <linux/clk.h>
#include <linux/regmap.h>

#define AC200_TWI_REG_ADDR_H	0xFE
#define AC200_SYS_VERSION	0x0000
#define AC200_SYS_CONTROL	0x0002
#define AC200_SYS_IRQ_ENABLE	0x0004
#define AC200_SYS_IRQ_STATUS	0x0006
#define AC200_SYS_EPHY_CTL0	0x0014
#define AC200_SYS_EPHY_CTL1	0x0016
#define AC200_EPHY_CTL		0x6000
#define AC200_EPHY_BIST		0x6002
#define AC200_IC_CHARA1		0xA1F2

struct ac200_dev {
	struct clk *clk;
	struct regmap *regmap;
};

int ac200_is_enabled(void);
u16 ac200_ephy_calibrate_value(void);

#endif
