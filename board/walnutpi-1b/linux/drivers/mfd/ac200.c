// SPDX-License-Identifier: GPL-2.0-only
/*
 * MFD core for X-Powers AC200 (Allwinner H6/H616 companion).
 * Based on Jernej Skrabec's driver, adapted for Linux 6.12.
 */

#include <linux/bits.h>
#include <linux/clk.h>
#include <linux/delay.h>
#include <linux/i2c.h>
#include <linux/kernel.h>
#include <linux/mfd/ac200.h>
#include <linux/mfd/core.h>
#include <linux/module.h>
#include <linux/nvmem-consumer.h>
#include <linux/regmap.h>
#include <linux/slab.h>

static const struct regmap_range_cfg ac200_range_cfg[] = {
	{
		.range_min = AC200_SYS_VERSION,
		.range_max = AC200_IC_CHARA1,
		.selector_reg = AC200_TWI_REG_ADDR_H,
		.selector_mask = 0xff,
		.selector_shift = 0,
		.window_start = 0,
		.window_len = 256,
	}
};

static const struct regmap_config ac200_regmap_config = {
	.name = "ac200",
	.reg_bits = 8,
	.val_bits = 16,
	.ranges = ac200_range_cfg,
	.num_ranges = ARRAY_SIZE(ac200_range_cfg),
	.max_register = AC200_IC_CHARA1,
};

static const struct mfd_cell ac200_cells[] = {
	{
		.name = "ac200-ephy",
		.of_compatible = "x-powers,ac200-ephy",
	},
};

static atomic_t ac200_en = ATOMIC_INIT(0);
static u16 ephy_caldata;

int ac200_is_enabled(void)
{
	return atomic_read(&ac200_en);
}
EXPORT_SYMBOL_GPL(ac200_is_enabled);

u16 ac200_ephy_calibrate_value(void)
{
	return ephy_caldata;
}
EXPORT_SYMBOL_GPL(ac200_ephy_calibrate_value);

static int ac200_read_calibrate(struct device *dev)
{
	struct nvmem_cell *calcell;
	size_t callen;
	u16 *caldata;

	calcell = nvmem_cell_get(dev, "calibration");
	if (IS_ERR(calcell)) {
		if (PTR_ERR(calcell) == -EPROBE_DEFER)
			return -EPROBE_DEFER;
		dev_warn(dev, "no ephy calibration cell, using 0\n");
		return 0;
	}
	caldata = nvmem_cell_read(calcell, &callen);
	nvmem_cell_put(calcell);
	if (IS_ERR(caldata))
		return PTR_ERR(caldata);
	if (callen >= 2)
		ephy_caldata = *caldata;
	kfree(caldata);
	return 0;
}

static int ac200_i2c_probe(struct i2c_client *client)
{
	struct device *dev = &client->dev;
	struct ac200_dev *ac200;
	int ret;

	ret = ac200_read_calibrate(dev);
	if (ret)
		return ret;

	/*
	 * SID bit8 = AC300 合封。官方 EPHY 上电走 MDIO 控制 PHY
	 *（ID 0xc0000000），不是 I2C AC200。对 0x10 做 I2C 会锁死总线。
	 */
	if (ephy_caldata & BIT(8)) {
		dev_info(dev, "AC300 package: skip I2C AC200, EPHY via MDIO (cal=0x%04x)\n",
			 ephy_caldata);
		ac200 = devm_kzalloc(dev, sizeof(*ac200), GFP_KERNEL);
		if (!ac200)
			return -ENOMEM;
		i2c_set_clientdata(client, ac200);
		return 0;
	}

	ac200 = devm_kzalloc(dev, sizeof(*ac200), GFP_KERNEL);
	if (!ac200)
		return -ENOMEM;

	ac200->clk = devm_clk_get(dev, NULL);
	if (IS_ERR(ac200->clk))
		return dev_err_probe(dev, PTR_ERR(ac200->clk), "clock\n");

	ret = clk_prepare_enable(ac200->clk);
	if (ret)
		return ret;

	ac200->regmap = devm_regmap_init_i2c(client, &ac200_regmap_config);
	if (IS_ERR(ac200->regmap)) {
		ret = PTR_ERR(ac200->regmap);
		goto err_clk;
	}

	ret = regmap_write(ac200->regmap, AC200_SYS_CONTROL, 0);
	if (ret)
		goto err_clk;
	atomic_set(&ac200_en, 0);
	usleep_range(1000, 2000);
	ret = regmap_write(ac200->regmap, AC200_SYS_CONTROL, 1);
	if (ret)
		goto err_clk;

	atomic_set(&ac200_en, 1);

	i2c_set_clientdata(client, ac200);
	ret = devm_mfd_add_devices(dev, PLATFORM_DEVID_NONE, ac200_cells,
				   ARRAY_SIZE(ac200_cells), NULL, 0, NULL);
	if (ret)
		goto err_clk;

	dev_info(dev, "AC200 MFD ready (cal=0x%04x)\n", ephy_caldata);
	return 0;

err_clk:
	clk_disable_unprepare(ac200->clk);
	return ret;
}

static void ac200_i2c_remove(struct i2c_client *client)
{
	struct ac200_dev *ac200 = i2c_get_clientdata(client);

	if (ac200->regmap)
		regmap_write(ac200->regmap, AC200_SYS_CONTROL, 0);
	atomic_set(&ac200_en, 0);
	if (ac200->clk)
		clk_disable_unprepare(ac200->clk);
}

static int ac200_suspend(struct device *dev)
{
	struct ac200_dev *ac200 = dev_get_drvdata(dev);

	if (!ac200 || !ac200->clk)
		return 0;
	clk_disable_unprepare(ac200->clk);
	atomic_set(&ac200_en, 0);
	return 0;
}

static int ac200_resume(struct device *dev)
{
	struct ac200_dev *ac200 = dev_get_drvdata(dev);

	if (!ac200 || !ac200->clk)
		return 0;
	clk_prepare_enable(ac200->clk);
	msleep(40);
	if (ac200->regmap)
		regmap_write(ac200->regmap, AC200_SYS_CONTROL, 1);
	atomic_set(&ac200_en, 1);
	return 0;
}

static DEFINE_SIMPLE_DEV_PM_OPS(ac200_pm_ops, ac200_suspend, ac200_resume);

static const struct of_device_id ac200_of_match[] = {
	{ .compatible = "x-powers,ac200" },
	{ }
};
MODULE_DEVICE_TABLE(of, ac200_of_match);

static struct i2c_driver ac200_driver = {
	.driver = {
		.name = "ac200",
		.of_match_table = ac200_of_match,
		.pm = pm_sleep_ptr(&ac200_pm_ops),
	},
	.probe = ac200_i2c_probe,
	.remove = ac200_i2c_remove,
};
module_i2c_driver(ac200_driver);

MODULE_DESCRIPTION("X-Powers AC200 MFD");
MODULE_LICENSE("GPL");
