// SPDX-License-Identifier: GPL-2.0-only
/*
 * X-Powers AC200 / AC300 10/100 EPHY.
 * AC200: I2C MFD SYS_EPHY_CTL.
 * AC300: MDIO 控制 PHY ID 0xc0000000，链路 PHY ID 0x00441400。
 * 寄存器序列来自 Allwinner/X-Powers sunxi-ephy（抽出，不发行 walnutpi/linux）。
 */

#include <linux/delay.h>
#include <linux/kernel.h>
#include <linux/mfd/ac200.h>
#include <linux/module.h>
#include <linux/phy.h>
#include <linux/platform_device.h>

#define EPHY_ID			0x00441400
#define EPHY_ID_MASK		0x0ffffff0
#define AC300_ID		0xc0000000
#define AC300_ID_MASK		0xffffffff

static struct ac200_dev *ac200;
static struct phy_device *ac300_ctl;
static atomic_t ephy_en;
static bool ac300_enabled;

static void ephy_config_default(struct phy_device *phydev)
{
	phy_write(phydev, 0x1f, 0x0100);
	phy_write(phydev, 0x12, 0x4824);
	phy_write(phydev, 0x1f, 0x0200);
	phy_write(phydev, 0x18, 0x0000);
	phy_write(phydev, 0x1f, 0x0600);
	phy_write(phydev, 0x14, 0x708b);
	phy_write(phydev, 0x13, 0xF000);
	phy_write(phydev, 0x15, 0x1530);
	phy_write(phydev, 0x1f, 0x0800);
	phy_write(phydev, 0x18, 0x00bc);
}

static void ephy_config_fixed(struct phy_device *phydev)
{
	phy_write(phydev, 0x1f, 0x0100);
	phy_write(phydev, 0x12, 0x4824);
	phy_write(phydev, 0x1f, 0x0200);
	phy_write(phydev, 0x18, 0x0000);
	phy_write(phydev, 0x1f, 0x0600);
	phy_write(phydev, 0x14, 0x7809);
	phy_write(phydev, 0x13, 0xf000);
	phy_write(phydev, 0x10, 0x5523);
	phy_write(phydev, 0x15, 0x3533);
	phy_write(phydev, 0x1f, 0x0800);
	phy_write(phydev, 0x1d, 0x0844);
	phy_write(phydev, 0x18, 0x00bc);
}

static void ephy_config_cali(struct phy_device *phydev, u16 ephy_cali)
{
	int value;

	value = phy_read(phydev, 0x06);
	if (value < 0)
		return;
	value &= ~(0x0F << 12);
	value |= (0x0F & (0x03 + ephy_cali)) << 12;
	phy_write(phydev, 0x06, value);
}

static void disable_intelligent_ieee(struct phy_device *phydev)
{
	int value;

	phy_write(phydev, 0x1f, 0x0100);
	value = phy_read(phydev, 0x17);
	if (value >= 0) {
		value &= ~BIT(3);
		phy_write(phydev, 0x17, value);
	}
	phy_write(phydev, 0x1f, 0x0000);
}

static void disable_802_3az_ieee(struct phy_device *phydev)
{
	int value;

	phy_write(phydev, 0xd, 0x7);
	phy_write(phydev, 0xe, 0x3c);
	phy_write(phydev, 0xd, BIT(14) | 0x7);
	value = phy_read(phydev, 0xe);
	if (value >= 0) {
		value &= ~BIT(1);
		phy_write(phydev, 0xd, 0x7);
		phy_write(phydev, 0xe, 0x3c);
		phy_write(phydev, 0xd, BIT(14) | 0x7);
		phy_write(phydev, 0xe, value);
	}
	phy_write(phydev, 0x1f, 0x0200);
	phy_write(phydev, 0x18, 0x0000);
}

static int ac300_ephy_enable(struct phy_device *phydev)
{
	if (ac300_enabled)
		return 0;

	/* 官方 ac300_ephy_enable() */
	phy_write(phydev, 0x00, 0x1f83);
	phy_write(phydev, 0x00, 0x1fb7);
	phy_write(phydev, 0x05, 0xa81f);
	phy_write(phydev, 0x06, 0x02);
	msleep(1000);
	ac300_enabled = true;
	atomic_set(&ephy_en, 1);
	dev_info(&phydev->mdio.dev, "AC300 EPHY enabled via MDIO\n");
	return 0;
}

static int ac200_ephy_enable(void)
{
	unsigned int value;
	u16 cali;
	int i;

	if (!ac200 || !ac200->regmap)
		return -ENODEV;

	for (i = 0; i < 200 && !ac200_is_enabled(); i++)
		msleep(10);
	if (!ac200_is_enabled())
		return -EIO;

	regmap_read(ac200->regmap, AC200_SYS_EPHY_CTL0, &value);
	value |= 0x03;
	regmap_write(ac200->regmap, AC200_SYS_EPHY_CTL0, value);

	regmap_read(ac200->regmap, AC200_SYS_EPHY_CTL1, &value);
	value |= 0x0f;
	regmap_write(ac200->regmap, AC200_SYS_EPHY_CTL1, value);

	cali = ac200_ephy_calibrate_value();
	value = 0x06;
	value |= ((0x0f & (0x03 + cali)) << 12);
	regmap_write(ac200->regmap, AC200_EPHY_CTL, value);

	atomic_set(&ephy_en, 1);
	return 0;
}

static void ac200_ephy_disable(void)
{
	unsigned int value;

	if (!ac200 || !ac200->regmap)
		return;
	regmap_read(ac200->regmap, AC200_SYS_EPHY_CTL0, &value);
	value &= ~0x01;
	regmap_write(ac200->regmap, AC200_SYS_EPHY_CTL0, value);
	regmap_read(ac200->regmap, AC200_EPHY_CTL, &value);
	value |= 0x01;
	regmap_write(ac200->regmap, AC200_EPHY_CTL, value);
	atomic_set(&ephy_en, 0);
}

static int ephy_config_init(struct phy_device *phydev)
{
	u16 cali = ac200_ephy_calibrate_value();
	int value;

	if (ac300_ctl) {
		ephy_config_cali(ac300_ctl, cali);
		if (cali & BIT(9))
			ephy_config_fixed(phydev);
		else
			ephy_config_default(phydev);
	} else {
		ephy_config_default(phydev);
	}

	disable_intelligent_ieee(phydev);
	disable_802_3az_ieee(phydev);
	phy_write(phydev, 0x1f, 0x0000);
	__set_bit(PHY_INTERFACE_MODE_MII, phydev->possible_interfaces);
	__set_bit(PHY_INTERFACE_MODE_RMII, phydev->possible_interfaces);
	linkmode_or(phydev->supported, phydev->supported, phy_basic_features);
	linkmode_copy(phydev->advertising, phydev->supported);

	if (ac200 && ac200->regmap) {
		unsigned int v;

		regmap_read(ac200->regmap, AC200_EPHY_CTL, &v);
		if (phydev->interface == PHY_INTERFACE_MODE_RMII)
			v |= BIT(11);
		else
			v &= ~BIT(11);
		regmap_write(ac200->regmap, AC200_EPHY_CTL, v | BIT(11));
	} else if (ac300_ctl) {
		value = phy_read(ac300_ctl, 0x06);
		if (value >= 0) {
			if (phydev->interface == PHY_INTERFACE_MODE_RMII)
				value |= BIT(11);
			else
				value &= ~BIT(11);
			/* LED_POL：低有效 */
			phy_write(ac300_ctl, 0x06, value | BIT(1));
		}
	}
	return 0;
}

static int ac300_config_init(struct phy_device *phydev)
{
	int ret;

	ac300_ctl = phydev;
	ret = ac300_ephy_enable(phydev);
	if (ret)
		return ret;
	/* 控制/链路共用同一 MDIO 地址时，这里补官方页表。 */
	return ephy_config_init(phydev);
}

static int ac300_probe(struct phy_device *phydev)
{
	ac300_ctl = phydev;
	return ac300_ephy_enable(phydev);
}

static struct phy_driver ac200_phy_driver[] = {
	{
		.phy_id		= AC300_ID,
		.phy_id_mask	= AC300_ID_MASK,
		.name		= "X-Powers AC300 EPHY",
		.features	= PHY_BASIC_FEATURES,
		.probe		= ac300_probe,
		.config_init	= ac300_config_init,
		.config_aneg	= genphy_config_aneg,
		.read_status	= genphy_read_status,
		.suspend	= genphy_suspend,
		.resume		= genphy_resume,
	},
	{
		.phy_id		= EPHY_ID,
		.phy_id_mask	= EPHY_ID_MASK,
		.name		= "X-Powers AC200 EPHY",
		.features	= PHY_BASIC_FEATURES,
		.config_init	= ephy_config_init,
		.config_aneg	= genphy_config_aneg,
		.read_status	= genphy_read_status,
		.suspend	= genphy_suspend,
		.resume		= genphy_resume,
	},
};

static int ac200_ephy_probe(struct platform_device *pdev)
{
	ac200 = dev_get_drvdata(pdev->dev.parent);
	if (!ac200)
		return -ENODEV;
	return ac200_ephy_enable();
}

static void ac200_ephy_remove(struct platform_device *pdev)
{
	ac200_ephy_disable();
}

static struct platform_driver ac200_ephy_plat = {
	.driver = {
		.name = "ac200-ephy",
	},
	.probe = ac200_ephy_probe,
	.remove = ac200_ephy_remove,
};

static int __init ac200_ephy_init(void)
{
	int ret;

	ret = platform_driver_register(&ac200_ephy_plat);
	if (ret)
		return ret;
	ret = phy_drivers_register(ac200_phy_driver,
				   ARRAY_SIZE(ac200_phy_driver), THIS_MODULE);
	if (ret)
		platform_driver_unregister(&ac200_ephy_plat);
	return ret;
}

static void __exit ac200_ephy_exit(void)
{
	phy_drivers_unregister(ac200_phy_driver, ARRAY_SIZE(ac200_phy_driver));
	platform_driver_unregister(&ac200_ephy_plat);
}

module_init(ac200_ephy_init);
module_exit(ac200_ephy_exit);

MODULE_DESCRIPTION("X-Powers AC200/AC300 EPHY");
MODULE_LICENSE("GPL");
