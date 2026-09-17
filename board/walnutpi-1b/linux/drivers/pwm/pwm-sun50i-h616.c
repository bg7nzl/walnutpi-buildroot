// SPDX-License-Identifier: GPL-2.0-only
/*
 * Allwinner H616/H618 grouped PWM, enough for AC200 24 MHz bypass on PWM5.
 * Register map from Allwinner pwm-sunxi-enhance.
 */

#include <linux/bits.h>
#include <linux/clk.h>
#include <linux/io.h>
#include <linux/module.h>
#include <linux/of.h>
#include <linux/platform_device.h>
#include <linux/pwm.h>
#include <linux/reset.h>

#define PWM_PCCR45		0x0028
#define PWM_PER			0x0040
#define PWM_PCR_BASE		0x0060
#define PWM_PPR_BASE		0x0064
#define PWM_CH_STRIDE		0x0020

#define PWM_CLK_GATING		BIT(4)
#define PWM_BYPASS		BIT(6)
#define PWM_CLK_SRC_SHIFT	7
#define PWM_CLK_SRC_MASK	(0x3 << PWM_CLK_SRC_SHIFT)

#define H616_NPWM		6

struct sun50i_h616_pwm {
	void __iomem *base;
	struct clk *bus;
	struct clk *mod;
	struct reset_control *rst;
};

static inline u32 pwm_rd(struct sun50i_h616_pwm *p, u32 off)
{
	return readl(p->base + off);
}

static inline void pwm_wr(struct sun50i_h616_pwm *p, u32 off, u32 val)
{
	writel(val, p->base + off);
}

static int sun50i_h616_pwm_apply(struct pwm_chip *chip, struct pwm_device *pwm,
				 const struct pwm_state *state)
{
	struct sun50i_h616_pwm *p = pwmchip_get_drvdata(chip);
	unsigned int ch = pwm->hwpwm;
	u32 pccr, per, pcr, ppr;
	u32 pccr_off = PWM_PCCR45;

	if (ch < 2)
		pccr_off = 0x0020;
	else if (ch < 4)
		pccr_off = 0x0024;
	else
		pccr_off = PWM_PCCR45;

	if (!state->enabled) {
		per = pwm_rd(p, PWM_PER);
		per &= ~BIT(ch);
		pwm_wr(p, PWM_PER, per);
		return 0;
	}

	/* AC200 wants 24 MHz HOSC bypassed to the pin. */
	pccr = pwm_rd(p, pccr_off);
	pccr &= ~PWM_CLK_SRC_MASK;	/* 0 = HOSC 24 MHz */
	pccr |= PWM_BYPASS | PWM_CLK_GATING;
	pwm_wr(p, pccr_off, pccr);

	pcr = pwm_rd(p, PWM_PCR_BASE + ch * PWM_CH_STRIDE);
	pcr |= BIT(8); /* active state high */
	pwm_wr(p, PWM_PCR_BASE + ch * PWM_CH_STRIDE, pcr);

	ppr = (0x1 << 16) | 0x1;
	pwm_wr(p, PWM_PPR_BASE + ch * PWM_CH_STRIDE, ppr);

	per = pwm_rd(p, PWM_PER);
	per |= BIT(ch);
	pwm_wr(p, PWM_PER, per);
	return 0;
}

static const struct pwm_ops sun50i_h616_pwm_ops = {
	.apply = sun50i_h616_pwm_apply,
};

static int sun50i_h616_pwm_probe(struct platform_device *pdev)
{
	struct sun50i_h616_pwm *p;
	struct pwm_chip *chip;
	int ret;

	chip = devm_pwmchip_alloc(&pdev->dev, H616_NPWM, sizeof(*p));
	if (IS_ERR(chip))
		return PTR_ERR(chip);
	p = pwmchip_get_drvdata(chip);

	p->base = devm_platform_ioremap_resource(pdev, 0);
	if (IS_ERR(p->base))
		return PTR_ERR(p->base);

	p->mod = devm_clk_get_optional(&pdev->dev, "hosc");
	if (IS_ERR(p->mod))
		p->mod = devm_clk_get_optional(&pdev->dev, NULL);
	p->bus = devm_clk_get(&pdev->dev, "bus");
	if (IS_ERR(p->bus))
		return PTR_ERR(p->bus);
	p->rst = devm_reset_control_get_optional_shared(&pdev->dev, NULL);
	if (IS_ERR(p->rst))
		return PTR_ERR(p->rst);

	ret = reset_control_deassert(p->rst);
	if (ret)
		return ret;
	ret = clk_prepare_enable(p->bus);
	if (ret)
		goto err_rst;
	if (p->mod) {
		ret = clk_prepare_enable(p->mod);
		if (ret)
			goto err_bus;
	}

	chip->ops = &sun50i_h616_pwm_ops;
	ret = pwmchip_add(chip);
	if (ret)
		goto err_mod;

	platform_set_drvdata(pdev, chip);
	return 0;

err_mod:
	clk_disable_unprepare(p->mod);
err_bus:
	clk_disable_unprepare(p->bus);
err_rst:
	reset_control_assert(p->rst);
	return ret;
}

static void sun50i_h616_pwm_remove(struct platform_device *pdev)
{
	struct pwm_chip *chip = platform_get_drvdata(pdev);
	struct sun50i_h616_pwm *p = pwmchip_get_drvdata(chip);

	pwmchip_remove(chip);
	clk_disable_unprepare(p->mod);
	clk_disable_unprepare(p->bus);
	reset_control_assert(p->rst);
}

static const struct of_device_id sun50i_h616_pwm_dt[] = {
	{ .compatible = "allwinner,sun50i-h616-pwm" },
	{ }
};
MODULE_DEVICE_TABLE(of, sun50i_h616_pwm_dt);

static struct platform_driver sun50i_h616_pwm_driver = {
	.driver = {
		.name = "sun50i-h616-pwm",
		.of_match_table = sun50i_h616_pwm_dt,
	},
	.probe = sun50i_h616_pwm_probe,
	.remove = sun50i_h616_pwm_remove,
};
module_platform_driver(sun50i_h616_pwm_driver);

MODULE_DESCRIPTION("Allwinner H616 PWM (AC200 24MHz bypass)");
MODULE_LICENSE("GPL");
