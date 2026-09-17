#!/usr/bin/env python3
"""Patch a mainline kernel tree for WalnutPi 1B/Zero (H616/H618)."""
from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path


def once_replace(text: str, needle: str, extra: str) -> str:
    """Replace the first needle with extra. Keep needle by including it in extra."""
    if extra.strip() in text:
        return text
    if needle not in text:
        raise SystemExit(f"missing context:\n{needle[:120]}")
    return text.replace(needle, extra, 1)


def _expect_count(text: str, token: str, n: int, what: str) -> None:
    got = text.count(token)
    if got != n:
        raise SystemExit(f"{what}: expected {n} x {token!r}, got {got}")


def insert_before(text: str, marker: str, extra: str) -> str:
    if extra.strip() in text:
        return text
    if marker not in text:
        raise SystemExit(f"missing marker:\n{marker[:120]}")
    return text.replace(marker, extra + marker, 1)


def append_line(path: Path, line: str) -> None:
    data = path.read_text(encoding="utf-8", errors="replace")
    if line in data:
        return
    if not data.endswith("\n"):
        data += "\n"
    path.write_text(data + line + "\n", encoding="utf-8")


def fixup_h616_dtsi(text: str) -> str:
    """Idempotent SoC DT fixes that apply even if nodes were injected earlier."""
    if 'clock-names = "apb", "mod";' in text and "codec: codec@5096000" in text:
        text = text.replace(
            '\t\t\tclock-names = "apb", "mod";\n'
            "\t\t\tresets = <&ccu RST_BUS_AUDIO_CODEC>;",
            '\t\t\tclock-names = "apb", "codec";\n'
            "\t\t\tresets = <&ccu RST_BUS_AUDIO_CODEC>;",
            1,
        )
    text = text.replace(
        '\t\t\tcompatible = "allwinner,sun50i-h616-codec",\n'
        '\t\t\t\t     "allwinner,sun8i-h3-codec";\n',
        '\t\t\tcompatible = "allwinner,sun50i-h616-codec";\n',
        1,
    )
    sram_child = """
				de33_sram: sram-section@0 {
					compatible = "allwinner,sun50i-h616-sram-c",
						     "allwinner,sun50i-a64-sram-c";
					reg = <0x0000 0x30000>;
				};
"""
    if "de33_sram:" not in text:
        needle = (
            "\t\t\tsram_c: sram@28000 {\n"
            '\t\t\t\tcompatible = "mmio-sram";\n'
            "\t\t\t\treg = <0x00028000 0x30000>;\n"
            "\t\t\t\t#address-cells = <1>;\n"
            "\t\t\t\t#size-cells = <1>;\n"
            "\t\t\t\tranges = <0 0x00028000 0x30000>;\n"
            "\t\t\t};\n"
        )
        extra = (
            "\t\t\tsram_c: sram@28000 {\n"
            '\t\t\t\tcompatible = "mmio-sram";\n'
            "\t\t\t\treg = <0x00028000 0x30000>;\n"
            "\t\t\t\t#address-cells = <1>;\n"
            "\t\t\t\t#size-cells = <1>;\n"
            "\t\t\t\tranges = <0 0x00028000 0x30000>;\n"
            + sram_child
            + "\t\t\t};\n"
        )
        if needle not in text:
            raise SystemExit("sram_c block not found for DE33 SRAM")
        text = text.replace(needle, extra, 1)
    if "allwinner,sram = <&de33_sram 1>" not in text:
        text = once_replace(
            text,
            "\t\tbus: bus@1000000 {\n"
            '\t\t\tcompatible = "allwinner,sun50i-h616-de33",\n'
            '\t\t\t\t     "allwinner,sun50i-a64-de2";\n'
            "\t\t\treg = <0x01000000 0x400000>;\n",
            "\t\tbus: bus@1000000 {\n"
            '\t\t\tcompatible = "allwinner,sun50i-h616-de33",\n'
            '\t\t\t\t     "allwinner,sun50i-a64-de2";\n'
            "\t\t\treg = <0x01000000 0x400000>;\n"
            "\t\t\tallwinner,sram = <&de33_sram 1>;\n",
        )
    if "#sound-dai-cells = <0>" not in text.split("hdmi: hdmi@6000000")[1][:800]:
        text = once_replace(
            text,
            "\t\t\tphys = <&hdmi_phy>;\n"
            '\t\t\tphy-names = "phy";\n'
            '\t\t\tstatus = "disabled";\n',
            "\t\t\tphys = <&hdmi_phy>;\n"
            '\t\t\tphy-names = "phy";\n'
            "\t\t\t#sound-dai-cells = <0>;\n"
            '\t\t\tstatus = "disabled";\n',
        )
    ahub = """
		ahub: ahub@5097000 {
			compatible = "allwinner,sunxi-ahub";
			reg = <0x05097000 0x1000>;
			clocks = <&ccu CLK_BUS_AUDIO_HUB>,
				 <&ccu CLK_AUDIO_CODEC_1X>,
				 <&ccu CLK_AUDIO_HUB>;
			clock-names = "apb", "audio-codec-1x", "audio-hub";
			resets = <&ccu RST_BUS_AUDIO_HUB>;
			status = "okay";
		};

		ahub_daudio1: ahub-daudio@5097000 {
			compatible = "allwinner,sunxi-ahub-daudio";
			reg = <0x05097000 0x1000>;
			clocks = <&ccu CLK_BUS_AUDIO_HUB>,
				 <&ccu CLK_AUDIO_CODEC_1X>,
				 <&ccu CLK_AUDIO_HUB>;
			clock-names = "apb", "audio-codec-1x", "audio-hub";
			tdm_num = <1>;
			pinconfig = <0>;
			frametype = <0>;
			pcm_lrck_period = <32>;
			slot_width_select = <32>;
			daudio_master = <4>;
			audio_format = <1>;
			signal_inversion = <0>;
			tdm_config = <1>;
			status = "okay";
		};

"""
    if "ahub: ahub@5097000" not in text:
        text = once_replace(text, "\t\tusbotg: usb@5100000 {", ahub + "\t\tusbotg: usb@5100000 {")
    if "ahub-daudio@5097000" in text:
        text = text.replace(
            "\t\t\tsignal_inversion = <1>;\n",
            "\t\t\tsignal_inversion = <0>;\n",
            1,
        )
        if "pinconfig = <0>;" not in text.split("ahub-daudio@5097000")[1][:400]:
            text = text.replace(
                "\t\t\ttdm_num = <1>;\n",
                "\t\t\ttdm_num = <1>;\n"
                "\t\t\tpinconfig = <0>;\n"
                "\t\t\tframetype = <0>;\n",
                1,
            )
    return text


def patch_dtsi(src: Path) -> None:
    text = src.read_text(encoding="utf-8", errors="replace")

    extra_includes = (
        "#include <dt-bindings/clock/sun8i-de2.h>\n"
        "#include <dt-bindings/reset/sun8i-de2.h>\n"
    )
    if "sun8i-de2.h" not in text:
        # After the last existing dt-bindings include block near the top.
        needle = "#include <dt-bindings/reset/sun50i-h616-ccu.h>\n"
        if needle not in text:
            needle = "#include <dt-bindings/clock/sun50i-h616-ccu.h>\n"
        text = once_replace(text, needle, needle + extra_includes)

    de_node = """
	de: display-engine {
		compatible = "allwinner,sun50i-h6-display-engine";
		allwinner,pipelines = <&mixer0>;
		status = "disabled";
	};
"""
    if "de: display-engine" not in text:
        text = insert_before(text, "\treserved-memory {", de_node)

    gpu_node = """
		gpu: gpu@1800000 {
			compatible = "allwinner,sun50i-h616-mali",
				     "arm,mali-bifrost";
			reg = <0x01800000 0x40000>;
			interrupts = <GIC_SPI 95 IRQ_TYPE_LEVEL_HIGH>,
				     <GIC_SPI 96 IRQ_TYPE_LEVEL_HIGH>,
				     <GIC_SPI 97 IRQ_TYPE_LEVEL_HIGH>;
			interrupt-names = "job", "mmu", "gpu";
			clocks = <&ccu CLK_GPU0>, <&ccu CLK_BUS_GPU>;
			clock-names = "core", "bus";
			resets = <&ccu RST_BUS_GPU>;
			status = "disabled";
		};

"""
    if "gpu: gpu@" not in text:
        text = insert_before(text, "sid: efuse@3006000 {", gpu_node)
    if "power-domains = <&prcm_ppu 2>" not in text:
        text = once_replace(
            text,
            "\t\t\tresets = <&ccu RST_BUS_GPU>;\n"
            "\t\t\tstatus = \"disabled\";\n"
            "\t\t};\n",
            "\t\t\tresets = <&ccu RST_BUS_GPU>;\n"
            "\t\t\tpower-domains = <&prcm_ppu 2>;\n"
            "\t\t\tstatus = \"disabled\";\n"
            "\t\t};\n",
        )

    ppu_node = """
		prcm_ppu: power-controller@7010250 {
			compatible = "allwinner,sun50i-h616-prcm-ppu";
			reg = <0x07010250 0x10>;
			#power-domain-cells = <1>;
		};

"""
    if "prcm_ppu: power-controller@" not in text:
        text = insert_before(text, "nmi_intc: interrupt-controller@7010320 {", ppu_node)

    pwm_node = """
		pwm: pwm@300a000 {
			compatible = "allwinner,sun50i-h616-pwm";
			reg = <0x0300a000 0x400>;
			clocks = <&ccu CLK_BUS_PWM>, <&osc24M>;
			clock-names = "bus", "hosc";
			resets = <&ccu RST_BUS_PWM>;
			#pwm-cells = <3>;
			status = "disabled";
		};

"""
    if "pwm: pwm@300a000" not in text:
        text = insert_before(text, "watchdog: watchdog@30090a0 {", pwm_node)

    pins = """
			/omit-if-no-ref/
			rmii_emac1_pins: rmii-emac1-pins {
				pins = "PA0", "PA1", "PA2", "PA3", "PA4",
				       "PA5", "PA6", "PA7", "PA8", "PA9";
				function = "emac1";
				drive-strength = <40>;
			};

			/omit-if-no-ref/
			i2c3_pa_pins: i2c3-pa-pins {
				pins = "PA10", "PA11";
				function = "i2c3";
			};

			/omit-if-no-ref/
			pwm5_pin: pwm5-pin {
				pins = "PA12";
				function = "pwm5";
			};

"""
    if "rmii_emac1_pins" not in text:
        text = once_replace(
            text,
            '\t\t\text_rgmii_pins: rgmii-pins {\n',
            pins + '\t\t\text_rgmii_pins: rgmii-pins {\n',
        )

    emac1 = """
		emac1: ethernet@5030000 {
			compatible = "allwinner,sun50i-h616-emac1";
			reg = <0x05030000 0x10000>;
			interrupts = <GIC_SPI 15 IRQ_TYPE_LEVEL_HIGH>;
			interrupt-names = "macirq";
			clocks = <&ccu CLK_BUS_EMAC1>;
			clock-names = "stmmaceth";
			resets = <&ccu RST_BUS_EMAC1>;
			reset-names = "stmmaceth";
			syscon = <&syscon>;
			phy-mode = "rmii";
			status = "disabled";

			mdio1: mdio {
				compatible = "snps,dwmac-mdio";
				#address-cells = <1>;
				#size-cells = <0>;
			};
		};

"""
    if "emac1: ethernet@5030000" not in text:
        text = once_replace(text, "\t\tspdif: spdif@5093000 {", emac1 + "\t\tspdif: spdif@5093000 {")

    codec = """
		codec: codec@5096000 {
			#sound-dai-cells = <0>;
			compatible = "allwinner,sun50i-h616-codec";
			reg = <0x05096000 0x31c>;
			interrupts = <GIC_SPI 58 IRQ_TYPE_LEVEL_HIGH>;
			clocks = <&ccu CLK_BUS_AUDIO_CODEC>,
				 <&ccu CLK_AUDIO_CODEC_1X>;
			clock-names = "apb", "codec";
			resets = <&ccu RST_BUS_AUDIO_CODEC>;
			dmas = <&dma 6>;
			dma-names = "tx";
			status = "disabled";
		};

"""
    if "codec: codec@5096000" not in text:
        text = once_replace(text, "\t\tusbotg: usb@5100000 {", codec + "\t\tusbotg: usb@5100000 {")

    display = r"""
		bus: bus@1000000 {
			compatible = "allwinner,sun50i-h616-de33",
				     "allwinner,sun50i-a64-de2";
			reg = <0x01000000 0x400000>;
			allwinner,sram = <&de33_sram 1>;
			#address-cells = <1>;
			#size-cells = <1>;
			ranges = <0 0x01000000 0x400000>;

			display_clocks: clock@8000 {
				compatible = "allwinner,sun50i-h616-de33-clk",
					     "allwinner,sun8i-h3-de2-clk";
				reg = <0x8000 0x100>;
				clocks = <&ccu CLK_DE>, <&ccu CLK_BUS_DE>;
				clock-names = "mod", "bus";
				resets = <&ccu RST_BUS_DE>;
				#clock-cells = <1>;
				#reset-cells = <1>;
			};

			mixer0: mixer@100000 {
				compatible = "allwinner,sun50i-h616-de33-mixer-0",
					     "allwinner,sun50i-h6-de3-mixer-0";
				reg = <0x100000 0x100000>,
				      <0x8100 0x40>,
				      <0x280000 0x20000>;
				reg-names = "layers", "top", "display";
				clocks = <&display_clocks CLK_BUS_MIXER0>,
					 <&display_clocks CLK_MIXER0>;
				clock-names = "bus", "mod";
				resets = <&display_clocks RST_MIXER0>;

				ports {
					#address-cells = <1>;
					#size-cells = <0>;

					mixer0_out: port@1 {
						reg = <1>;
						mixer0_out_tcon_top_mixer0: endpoint {
							remote-endpoint = <&tcon_top_mixer0_in_mixer0>;
						};
					};
				};
			};
		};

		tcon_top: tcon-top@6510000 {
			compatible = "allwinner,sun50i-h6-tcon-top";
			reg = <0x06510000 0x1000>;
			clocks = <&ccu CLK_BUS_TCON_TOP>, <&ccu CLK_TCON_TV0>;
			clock-names = "bus", "tcon-tv0";
			clock-output-names = "tcon-top-tv0";
			resets = <&ccu RST_BUS_TCON_TOP>;
			#clock-cells = <1>;

			ports {
				#address-cells = <1>;
				#size-cells = <0>;

				tcon_top_mixer0_in: port@0 {
					#address-cells = <1>;
					#size-cells = <0>;
					reg = <0>;
					tcon_top_mixer0_in_mixer0: endpoint@0 {
						reg = <0>;
						remote-endpoint = <&mixer0_out_tcon_top_mixer0>;
					};
				};

				tcon_top_mixer0_out: port@1 {
					#address-cells = <1>;
					#size-cells = <0>;
					reg = <1>;
					tcon_top_mixer0_out_tcon_tv: endpoint@2 {
						reg = <2>;
						remote-endpoint = <&tcon_tv_in_tcon_top_mixer0>;
					};
				};

				tcon_top_hdmi_in: port@4 {
					#address-cells = <1>;
					#size-cells = <0>;
					reg = <4>;
					tcon_top_hdmi_in_tcon_tv: endpoint@0 {
						reg = <0>;
						remote-endpoint = <&tcon_tv_out_tcon_top_hdmi>;
					};
				};

				tcon_top_hdmi_out: port@5 {
					reg = <5>;
					tcon_top_hdmi_out_hdmi: endpoint {
						remote-endpoint = <&hdmi_in_tcon_top>;
					};
				};
			};
		};

		tcon_tv: lcd-controller@6515000 {
			compatible = "allwinner,sun50i-h6-tcon-tv",
				     "allwinner,sun8i-r40-tcon-tv";
			reg = <0x06515000 0x1000>;
			interrupts = <GIC_SPI 66 IRQ_TYPE_LEVEL_HIGH>;
			clocks = <&ccu CLK_BUS_TCON_TV0>,
				 <&tcon_top 0>;
			clock-names = "ahb", "tcon-ch1";
			resets = <&ccu RST_BUS_TCON_TV0>;
			reset-names = "lcd";

			ports {
				#address-cells = <1>;
				#size-cells = <0>;

				tcon_tv_in: port@0 {
					reg = <0>;
					tcon_tv_in_tcon_top_mixer0: endpoint {
						remote-endpoint = <&tcon_top_mixer0_out_tcon_tv>;
					};
				};

				tcon_tv_out: port@1 {
					reg = <1>;
					tcon_tv_out_tcon_top_hdmi: endpoint {
						remote-endpoint = <&tcon_top_hdmi_in_tcon_tv>;
					};
				};
			};
		};

		hdmi: hdmi@6000000 {
			compatible = "allwinner,sun50i-h616-dw-hdmi",
				     "allwinner,sun50i-h6-dw-hdmi";
			reg = <0x06000000 0x10000>;
			reg-io-width = <1>;
			interrupts = <GIC_SPI 63 IRQ_TYPE_LEVEL_HIGH>;
			clocks = <&ccu CLK_BUS_HDMI>,
				 <&ccu CLK_HDMI_SLOW>,
				 <&ccu CLK_HDMI>,
				 <&ccu CLK_HDMI_CEC>;
			clock-names = "iahb", "isfr", "tmds", "cec";
			resets = <&ccu RST_BUS_HDMI_SUB>;
			reset-names = "ctrl";
			phys = <&hdmi_phy>;
			phy-names = "phy";
			#sound-dai-cells = <0>;
			status = "disabled";

			ports {
				#address-cells = <1>;
				#size-cells = <0>;

				hdmi_in: port@0 {
					reg = <0>;
					hdmi_in_tcon_top: endpoint {
						remote-endpoint = <&tcon_top_hdmi_out_hdmi>;
					};
				};

				hdmi_out: port@1 {
					reg = <1>;
				};
			};
		};

		hdmi_phy: hdmi-phy@6010000 {
			compatible = "allwinner,sun50i-h616-hdmi-phy";
			reg = <0x06010000 0x10000>;
			clocks = <&ccu CLK_BUS_HDMI>, <&ccu CLK_HDMI_SLOW>;
			clock-names = "bus", "mod";
			resets = <&ccu RST_BUS_HDMI>;
			reset-names = "phy";
			#phy-cells = <0>;
		};

"""
    if "hdmi: hdmi@6000000" not in text:
        text = once_replace(text, "\t\trtc: rtc@7000000 {", display + "\t\trtc: rtc@7000000 {")

    text = fixup_h616_dtsi(text)

    if text.count("{") != text.count("}"):
        raise SystemExit(
            f"{src}: brace mismatch {text.count('{')} '{{' vs {text.count('}')} '}}'"
        )
    for token in (
        "ext_rgmii_pins: rgmii-pins",
        "emac1: ethernet@5030000",
        "spdif: spdif@5093000",
        "usbotg: usb@5100000",
        "rtc: rtc@7000000",
        "hdmi: hdmi@6000000",
        "rmii_emac1_pins: rmii-emac1-pins",
        "gpu: gpu@1800000",
        "pwm: pwm@300a000",
        "codec: codec@5096000",
    ):
        _expect_count(text, token, 1, str(src))

    src.write_text(text, encoding="utf-8")
    print("patched", src)


def patch_dwmac(src: Path) -> None:
    text = src.read_text(encoding="utf-8", errors="replace")
    variant = """
static const struct emac_variant emac_variant_h616_emac1 = {
	.syscon_field = &sun8i_syscon_reg_field_emac1,
	.soc_has_internal_phy = false,
	.support_rmii = true,
	.rx_delay_max = 31,
	.tx_delay_max = 7,
};
"""
    field = """
static const struct reg_field sun8i_syscon_reg_field_emac1 = {
	.reg = 0x34,
	.lsb = 0,
	.msb = 31,
};
"""
    if "sun8i_syscon_reg_field_emac1" not in text:
        text = once_replace(
            text,
            "static const struct reg_field sun8i_syscon_reg_field = {\n"
            "	.reg = 0x30,\n"
            "	.lsb = 0,\n"
            "	.msb = 31,\n"
            "};\n",
            "static const struct reg_field sun8i_syscon_reg_field = {\n"
            "	.reg = 0x30,\n"
            "	.lsb = 0,\n"
            "	.msb = 31,\n"
            "};\n"
            + field,
        )
    if "emac_variant_h616_emac1" not in text:
        text = insert_before(text, "#define EMAC_BASIC_CTL0", variant + "\n")
    match = """
	{ .compatible = "allwinner,sun50i-h616-emac1",
		.data = &emac_variant_h616_emac1 },
"""
    if "sun50i-h616-emac1" not in text:
        text = insert_before(text, "\t{ }\n};\nMODULE_DEVICE_TABLE(of, sun8i_dwmac_match);", match)
    if "linux/nvmem-consumer.h" not in text:
        text = once_replace(
            text,
            "#include <linux/of.h>\n",
            "#include <linux/etherdevice.h>\n"
            "#include <linux/nvmem-consumer.h>\n"
            "#include <linux/string.h>\n"
            "#include <linux/of.h>\n",
        )
    if "linux/device.h" not in text:
        text = once_replace(
            text,
            "#include <linux/etherdevice.h>\n",
            "#include <linux/device.h>\n"
            "#include <linux/etherdevice.h>\n",
        )
        if "linux/device.h" not in text:
            text = once_replace(
                text,
                "#include <linux/of.h>\n",
                "#include <linux/device.h>\n"
                "#include <linux/of.h>\n",
            )
    sid_fn = """
static int sun8i_dwmac_sid_mac(struct device *dev, u8 *mac)
{
	static const u8 usb_ether_dummy[] = {0xde, 0xad, 0xbe, 0xef, 0x00, 0x01};
	struct device_node *np;
	struct nvmem_device *nvmem;
	u32 sid[4] = {0};
	int ret;

	if (is_valid_ether_addr(mac) && memcmp(mac, usb_ether_dummy, ETH_ALEN))
		return 0;

	np = of_find_compatible_node(NULL, NULL, "allwinner,sun50i-h616-sid");
	if (!np)
		np = of_find_compatible_node(NULL, NULL, "allwinner,sun50i-a64-sid");
	if (!np)
		return 0;
	/* 找 SID 这个 provider，不是消费者节点上的 nvmem phandle。 */
	nvmem = nvmem_device_find(np, device_match_of_node);
	of_node_put(np);
	if (IS_ERR(nvmem))
		return PTR_ERR(nvmem);
	ret = nvmem_device_read(nvmem, 0, sizeof(sid), sid);
	nvmem_device_put(nvmem);
	if (ret < 0)
		return ret;
	if (!sid[0] && !sid[3])
		return 0;
	mac[0] = 0x02;
	mac[1] = sid[0] & 0xff;
	mac[2] = (sid[3] >> 24) & 0xff;
	mac[3] = (sid[3] >> 16) & 0xff;
	mac[4] = (sid[3] >> 8) & 0xff;
	mac[5] = sid[3] & 0xff;
	if (!is_valid_ether_addr(mac))
		mac[0] |= 0x02;
	dev_info(dev, "MAC from SID %pM\\n", mac);
	return 0;
}

"""
    if "static void sun8i_dwmac_sid_mac" in text:
        start = text.find("static void sun8i_dwmac_sid_mac")
        end = text.find("static int sun8i_dwmac_probe", start)
        if start < 0 or end < 0:
            raise SystemExit("cannot replace old SID MAC helper")
        text = text[:start] + sid_fn + text[end:]
    elif "static int sun8i_dwmac_sid_mac" not in text:
        text = insert_before(text, "static int sun8i_dwmac_probe(struct platform_device *pdev)\n", sid_fn)
    # of_get_mac_address 会盖掉提前写入的地址，必须放在 probe_config_dt 之后。
    text = text.replace(
        "\tsun8i_dwmac_sid_mac(&pdev->dev, stmmac_res.mac);\n"
        "\tplat_dat = devm_stmmac_probe_config_dt(pdev, stmmac_res.mac);\n"
        "\tif (IS_ERR(plat_dat))\n"
        "\t\treturn PTR_ERR(plat_dat);\n",
        "\tplat_dat = devm_stmmac_probe_config_dt(pdev, stmmac_res.mac);\n"
        "\tif (IS_ERR(plat_dat))\n"
        "\t\treturn PTR_ERR(plat_dat);\n"
        "\tret = sun8i_dwmac_sid_mac(&pdev->dev, stmmac_res.mac);\n"
        "\tif (ret)\n"
        "\t\treturn ret;\n",
        1,
    )
    if "ret = sun8i_dwmac_sid_mac" not in text:
        text = once_replace(
            text,
            "\tplat_dat = devm_stmmac_probe_config_dt(pdev, stmmac_res.mac);\n"
            "\tif (IS_ERR(plat_dat))\n"
            "\t\treturn PTR_ERR(plat_dat);\n",
            "\tplat_dat = devm_stmmac_probe_config_dt(pdev, stmmac_res.mac);\n"
            "\tif (IS_ERR(plat_dat))\n"
            "\t\treturn PTR_ERR(plat_dat);\n"
            "\tret = sun8i_dwmac_sid_mac(&pdev->dev, stmmac_res.mac);\n"
            "\tif (ret)\n"
            "\t\treturn ret;\n",
        )
    wait_fn = """
static int sun8i_dwmac_ac300_mdio(struct stmmac_priv *priv)
{
	struct mii_bus *bus = priv->mii;
	int addr, found = 0;

	if (!bus)
		return 0;

	for (addr = 0; addr < PHY_MAX_ADDR; addr++) {
		int id1, id2;
		u32 id;

		id1 = mdiobus_read(bus, addr, MII_PHYSID1);
		id2 = mdiobus_read(bus, addr, MII_PHYSID2);
		if (id1 < 0 || id2 < 0)
			continue;
		id = ((u32)id1 << 16) | (id2 & 0xffff);
		if (id != 0xc0000000)
			continue;
		dev_info(priv->device,
			 "AC300 control PHY at MDIO %d, enabling EPHY\\n",
			 addr);
		mdiobus_write(bus, addr, 0x00, 0x1f83);
		mdiobus_write(bus, addr, 0x00, 0x1fb7);
		mdiobus_write(bus, addr, 0x05, 0xa81f);
		/* 0x02 官方复位值；bit11=RMII，bit1=LED_POL */
		mdiobus_write(bus, addr, 0x06, 0x02 | BIT(11) | BIT(1));
		found++;
	}
	if (found)
		msleep(1000);
	else
		dev_info(priv->device, "no AC300 PHY id 0xc0000000 on MDIO\\n");
	return 0;
}

static int sun8i_dwmac_wait_ac200(struct device *dev)
{
	struct clk *clk_ephy;

	/* AC300 要 PWM 24 MHz。官方 EXT_PHY 不开 CCU 25m。 */
	clk_ephy = of_clk_get_by_name(dev->of_node, "ephy24m");
	if (!IS_ERR(clk_ephy))
		clk_prepare_enable(clk_ephy);
	return 0;
}

"""
    old_wait = """static int sun8i_dwmac_wait_ac200(struct device *dev)
{
	struct device_node *np;
	struct clk *clk_25m;

	np = of_parse_phandle(dev->of_node, "allwinner,ac200-ephy", 0);
	if (!np)
		return 0;
	of_node_put(np);
	if (!ac200_is_enabled())
		return -EPROBE_DEFER;
	clk_25m = of_clk_get_by_name(dev->of_node, "25m");
	if (!IS_ERR(clk_25m))
		clk_prepare_enable(clk_25m);
	return 0;
}
"""
    if old_wait in text:
        text = text.replace(old_wait, wait_fn.lstrip("\n"), 1)
    elif "of_clk_get_by_name(dev->of_node, \"25m\")" in text and "sun8i_dwmac_wait_ac200" in text:
        text = text.replace(
            "\tclk_ephy = of_clk_get_by_name(dev->of_node, \"ephy24m\");\n"
            "\tif (!IS_ERR(clk_ephy))\n"
            "\t\tclk_prepare_enable(clk_ephy);\n"
            "\tclk_ephy = of_clk_get_by_name(dev->of_node, \"25m\");\n"
            "\tif (!IS_ERR(clk_ephy))\n"
            "\t\tclk_prepare_enable(clk_ephy);\n",
            "\tclk_ephy = of_clk_get_by_name(dev->of_node, \"ephy24m\");\n"
            "\tif (!IS_ERR(clk_ephy))\n"
            "\t\tclk_prepare_enable(clk_ephy);\n",
            1,
        )
    elif "sun8i_dwmac_ac300_mdio" not in text:
        text = once_replace(
            text,
            "static int sun8i_dwmac_probe(struct platform_device *pdev)\n",
            wait_fn + "static int sun8i_dwmac_probe(struct platform_device *pdev)\n",
        )
        text = once_replace(
            text,
            "\tret = stmmac_get_platform_resources(pdev, &stmmac_res);\n"
            "\tif (ret)\n"
            "\t\treturn ret;\n",
            "\tret = sun8i_dwmac_wait_ac200(&pdev->dev);\n"
            "\tif (ret)\n"
            "\t\treturn ret;\n"
            "\n"
            "\tret = stmmac_get_platform_resources(pdev, &stmmac_res);\n"
            "\tif (ret)\n"
            "\t\treturn ret;\n",
        )
    if "#include <linux/mfd/ac200.h>" not in text:
        text = once_replace(
            text,
            "#include <linux/module.h>\n",
            "#include <linux/module.h>\n"
            "#include <linux/mfd/ac200.h>\n",
        )
    if "#include <linux/delay.h>" not in text:
        text = once_replace(
            text,
            "#include <linux/clk.h>\n",
            "#include <linux/clk.h>\n#include <linux/delay.h>\n",
        )
    if "#include <linux/mii.h>" not in text:
        text = once_replace(
            text,
            "#include <linux/module.h>\n",
            "#include <linux/module.h>\n#include <linux/mii.h>\n",
        )
    if "#include <linux/reset.h>" not in text:
        text = once_replace(
            text,
            "#include <linux/phy.h>\n",
            "#include <linux/phy.h>\n#include <linux/reset.h>\n",
        )

    old_rst = (
        "\tif (err) {\n"
        "\t\tdev_err(priv->device, \"EMAC reset timeout\\n\");\n"
        "\t\treturn err;\n"
        "\t}"
    )
    new_rst = (
        "\tif (err) {\n"
        "\t\tdev_warn(priv->device, \"EMAC reset timeout, continue for AC300 MDIO\\n\");\n"
        "\t\treturn 0;\n"
        "\t}"
    )
    if "continue for AC300 MDIO" not in text:
        if old_rst not in text:
            raise SystemExit(f"{src}: missing EMAC reset timeout block")
        text = text.replace(old_rst, new_rst, 1)

    old_call = (
        "\t} else {\n"
        "\t\tret = sun8i_dwmac_reset(priv);\n"
        "\t\tif (ret)\n"
        "\t\t\tgoto dwmac_remove;\n"
        "\t}"
    )
    new_call = (
        "\t} else {\n"
        "\t\tret = sun8i_dwmac_reset(priv);\n"
        "\t\tif (ret)\n"
        "\t\t\tdev_warn(&pdev->dev, \"EMAC reset before AC300\\n\");\n"
        "\t\tsun8i_dwmac_ac300_mdio(priv);\n"
        "\t\tsun8i_dwmac_reset(priv);\n"
        "\t}"
    )
    if "sun8i_dwmac_ac300_mdio(priv)" not in text:
        if old_call not in text:
            raise SystemExit(f"{src}: missing EMAC reset call site")
        text = text.replace(old_call, new_call, 1)

    # 已注入过的树上补 RMII，避免第二次 inject 跳过。
    if "0x06, 0x02 | BIT(11) | BIT(1)" not in text:
        text = text.replace(
            "\t\tmdiobus_write(bus, addr, 0x06, 0x02);\n",
            "\t\tmdiobus_write(bus, addr, 0x06, 0x02 | BIT(11) | BIT(1));\n",
            1,
        )

    early_fn = """
static int sun8i_raw_mdio_read(void __iomem *io, int addr, int reg)
{
	u32 v;
	int err;

	v = (3 << 20) | ((addr << 12) & GENMASK(16, 12)) |
	    ((reg << 4) & GENMASK(8, 4)) | 0x1;
	writel(v, io + EMAC_MDIO_CMD);
	err = readl_poll_timeout(io + EMAC_MDIO_CMD, v, !(v & 0x1), 10, 10000);
	if (err)
		return err;
	return readl(io + EMAC_MDIO_DATA) & 0xffff;
}

static int sun8i_raw_mdio_write(void __iomem *io, int addr, int reg, u16 data)
{
	u32 v;

	writel(data, io + EMAC_MDIO_DATA);
	v = (3 << 20) | ((addr << 12) & GENMASK(16, 12)) |
	    ((reg << 4) & GENMASK(8, 4)) | 0x2 | 0x1;
	writel(v, io + EMAC_MDIO_CMD);
	return readl_poll_timeout(io + EMAC_MDIO_CMD, v, !(v & 0x1), 10, 10000);
}

static void sun8i_dwmac_ac300_early(void __iomem *io, struct device *dev)
{
	struct clk *bus;
	int addr, found = 0;

	/* init 已 deassert stmmaceth；再 get 同一条 reset 会 WARN。 */
	bus = of_clk_get_by_name(dev->of_node, "stmmaceth");
	if (!IS_ERR(bus))
		clk_prepare_enable(bus);
	writel(3 << 20, io + EMAC_MDIO_CMD);

	for (addr = 0; addr < PHY_MAX_ADDR; addr++) {
		int id1, id2;
		u32 id;

		id1 = sun8i_raw_mdio_read(io, addr, MII_PHYSID1);
		id2 = sun8i_raw_mdio_read(io, addr, MII_PHYSID2);
		if (id1 < 0 || id2 < 0)
			continue;
		id = ((u32)id1 << 16) | (id2 & 0xffff);
		if (id == 0xffffffff || id == 0x00000000)
			continue;
		dev_info(dev, "MDIO dump %d id %08x\\n", addr, id);
		if (id != 0xc0000000)
			continue;
		dev_info(dev, "AC300 early at MDIO %d, enable EPHY\\n", addr);
		sun8i_raw_mdio_write(io, addr, 0x00, 0x1f83);
		sun8i_raw_mdio_write(io, addr, 0x00, 0x1fb7);
		sun8i_raw_mdio_write(io, addr, 0x05, 0xa81f);
		sun8i_raw_mdio_write(io, addr, 0x06, 0x02 | BIT(11) | BIT(1));
		found++;
	}
	if (found)
		msleep(1000);
	else
		dev_info(dev, "AC300 early: no id 0xc0000000\\n");
	for (addr = 0; addr < PHY_MAX_ADDR; addr++) {
		int id1, id2;
		u32 id;

		id1 = sun8i_raw_mdio_read(io, addr, MII_PHYSID1);
		id2 = sun8i_raw_mdio_read(io, addr, MII_PHYSID2);
		if (id1 < 0 || id2 < 0)
			continue;
		id = ((u32)id1 << 16) | (id2 & 0xffff);
		if (id == 0xffffffff || id == 0x00000000)
			continue;
		dev_info(dev, "MDIO after %d id %08x\\n", addr, id);
	}
}

"""
    if "sun8i_dwmac_ac300_early" not in text:
        if "static int sun8i_dwmac_ac300_mdio(" not in text:
            raise SystemExit(f"{src}: missing ac300_mdio to prepend early enable")
        text = text.replace(
            "static int sun8i_dwmac_ac300_mdio(",
            early_fn.lstrip("\n") + "static int sun8i_dwmac_ac300_mdio(",
            1,
        )
    if "MDIO dump" not in text:
        old_early_loop = (
            "\t\tid = ((u32)id1 << 16) | (id2 & 0xffff);\n"
            "\t\tif (id != 0xc0000000)\n"
            "\t\t\tcontinue;\n"
            "\t\tdev_info(dev, \"AC300 early at MDIO %d, enable EPHY\\n\", addr);\n"
        )
        new_early_loop = (
            "\t\tid = ((u32)id1 << 16) | (id2 & 0xffff);\n"
            "\t\tif (id == 0xffffffff || id == 0x00000000)\n"
            "\t\t\tcontinue;\n"
            "\t\tdev_info(dev, \"MDIO dump %d id %08x\\n\", addr, id);\n"
            "\t\tif (id != 0xc0000000)\n"
            "\t\t\tcontinue;\n"
            "\t\tdev_info(dev, \"AC300 early at MDIO %d, enable EPHY\\n\", addr);\n"
        )
        if old_early_loop not in text:
            raise SystemExit(f"{src}: missing AC300 early ID loop")
        text = text.replace(old_early_loop, new_early_loop, 1)
        after_enable = (
            "\telse\n"
            "\t\tdev_info(dev, \"AC300 early: no id 0xc0000000\\n\");\n"
            "}\n"
        )
        after_enable_new = (
            "\telse\n"
            "\t\tdev_info(dev, \"AC300 early: no id 0xc0000000\\n\");\n"
            "\tfor (addr = 0; addr < PHY_MAX_ADDR; addr++) {\n"
            "\t\tint id1, id2;\n"
            "\t\tu32 id;\n"
            "\n"
            "\t\tid1 = sun8i_raw_mdio_read(io, addr, MII_PHYSID1);\n"
            "\t\tid2 = sun8i_raw_mdio_read(io, addr, MII_PHYSID2);\n"
            "\t\tif (id1 < 0 || id2 < 0)\n"
            "\t\t\tcontinue;\n"
            "\t\tid = ((u32)id1 << 16) | (id2 & 0xffff);\n"
            "\t\tif (id == 0xffffffff || id == 0x00000000)\n"
            "\t\t\tcontinue;\n"
            "\t\tdev_info(dev, \"MDIO after %d id %08x\\n\", addr, id);\n"
            "\t}\n"
            "}\n"
        )
        if after_enable not in text:
            raise SystemExit(f"{src}: missing AC300 early end")
        text = text.replace(after_enable, after_enable_new, 1)

    if "EPHY scanned at MDIO" not in text:
        old_bind_skip = (
            "\t\tif (!phydev)\n"
            "\t\t\tcontinue;\n"
            "\t\tid1 = phy_read(phydev, MII_PHYSID1);\n"
            "\t\tid2 = phy_read(phydev, MII_PHYSID2);\n"
            "\t\tif (id1 < 0 || id2 < 0)\n"
            "\t\t\tcontinue;\n"
            "\t\tid = ((u32)id1 << 16) | (id2 & 0xffff);\n"
            "\t\tif ((id & 0x0ffffff0) != 0x00441400)\n"
            "\t\t\tcontinue;\n"
        )
        new_bind_skip = (
            "\t\tid1 = phydev ? phy_read(phydev, MII_PHYSID1) :\n"
            "\t\t      mdiobus_read(bus, addr, MII_PHYSID1);\n"
            "\t\tid2 = phydev ? phy_read(phydev, MII_PHYSID2) :\n"
            "\t\t      mdiobus_read(bus, addr, MII_PHYSID2);\n"
            "\t\tif (id1 < 0 || id2 < 0)\n"
            "\t\t\tcontinue;\n"
            "\t\tid = ((u32)id1 << 16) | (id2 & 0xffff);\n"
            "\t\tif ((id & 0x0ffffff0) != 0x00441400)\n"
            "\t\t\tcontinue;\n"
            "\t\tif (!phydev) {\n"
            "\t\t\tphydev = mdiobus_scan_c22(bus, addr);\n"
            "\t\t\tif (IS_ERR_OR_NULL(phydev))\n"
            "\t\t\t\tcontinue;\n"
            "\t\t\tdev_info(priv->device, \"EPHY scanned at MDIO %d id %08x\\n\",\n"
            "\t\t\t\t addr, id);\n"
            "\t\t\tcontinue;\n"
            "\t\t}\n"
        )
        if old_bind_skip not in text:
            raise SystemExit(f"{src}: missing bind_ephy skip")
        text = text.replace(old_bind_skip, new_bind_skip, 1)

    old_dvr = (
        "\tret = stmmac_dvr_probe(&pdev->dev, plat_dat, &stmmac_res);\n"
        "\tif (ret)\n"
        "\t\tgoto dwmac_exit;\n"
    )
    new_dvr = (
        "\tplat_dat->clk_csr = 3;\n"
        "\tsun8i_dwmac_ac300_early(stmmac_res.addr, &pdev->dev);\n"
        "\tret = stmmac_dvr_probe(&pdev->dev, plat_dat, &stmmac_res);\n"
        "\tif (ret)\n"
        "\t\tgoto dwmac_exit;\n"
    )
    if "sun8i_dwmac_ac300_early(stmmac_res.addr" not in text:
        if old_dvr not in text:
            raise SystemExit(f"{src}: missing stmmac_dvr_probe site")
        text = text.replace(old_dvr, new_dvr, 1)

    old_syscon_base = (
        "\treg = gmac->variant->default_syscon_value;\n"
        "\tif (reg != val)\n"
        "\t\tdev_warn(dev,\n"
        "\t\t\t \"Current syscon value is not the default %x (expect %x)\\n\",\n"
        "\t\t\t val, reg);\n"
    )
    new_syscon_base = (
        "\treg = gmac->variant->default_syscon_value;\n"
        "\tif (gmac->variant == &emac_variant_h616_emac1)\n"
        "\t\treg = val;\n"
        "\telse if (reg != val)\n"
        "\t\tdev_warn(dev,\n"
        "\t\t\t \"Current syscon value is not the default %x (expect %x)\\n\",\n"
        "\t\t\t val, reg);\n"
    )
    if "variant == &emac_variant_h616_emac1" not in text:
        if old_syscon_base not in text:
            raise SystemExit(f"{src}: missing set_syscon default block")
        text = text.replace(old_syscon_base, new_syscon_base, 1)

    bind_fn = """
static void sun8i_dwmac_bind_ephy(struct stmmac_priv *priv)
{
	struct mii_bus *bus = priv->mii;
	int addr;

	if (!bus)
		return;
	for (addr = 0; addr < PHY_MAX_ADDR; addr++) {
		struct phy_device *phydev = mdiobus_get_phy(bus, addr);
		int id1, id2;
		u32 id;

		id1 = phydev ? phy_read(phydev, MII_PHYSID1) :
		      mdiobus_read(bus, addr, MII_PHYSID1);
		id2 = phydev ? phy_read(phydev, MII_PHYSID2) :
		      mdiobus_read(bus, addr, MII_PHYSID2);
		if (id1 < 0 || id2 < 0)
			continue;
		id = ((u32)id1 << 16) | (id2 & 0xffff);
		if ((id & 0x0ffffff0) != 0x00441400)
			continue;
		if (!phydev) {
			phydev = mdiobus_scan_c22(bus, addr);
			if (IS_ERR_OR_NULL(phydev))
				continue;
			dev_info(priv->device, "EPHY scanned at MDIO %d id %08x\\n",
				 addr, id);
		} else {
			phydev->phy_id = id;
			device_release_driver(&phydev->mdio.dev);
			if (device_attach(&phydev->mdio.dev) < 0)
				dev_warn(priv->device, "EPHY rebind MDIO %d failed\\n",
					 addr);
			else
				dev_info(priv->device, "EPHY id %08x at MDIO %d\\n",
					 id, addr);
		}
		priv->plat->phy_addr = addr;
	}
}

"""
    if "sun8i_dwmac_bind_ephy" not in text:
        text = text.replace(
            "static int sun8i_dwmac_ac300_mdio(",
            bind_fn.lstrip("\n") + "static int sun8i_dwmac_ac300_mdio(",
            1,
        )
        text = text.replace(
            "\t\tsun8i_dwmac_ac300_mdio(priv);\n"
            "\t\tsun8i_dwmac_reset(priv);\n",
            "\t\tsun8i_dwmac_ac300_mdio(priv);\n"
            "\t\tsun8i_dwmac_bind_ephy(priv);\n"
            "\t\tsun8i_dwmac_reset(priv);\n",
            1,
        )
    else:
        start = text.find("static void sun8i_dwmac_bind_ephy(")
        end = text.find("static int sun8i_dwmac_ac300_mdio(", start)
        if start >= 0 and end > start:
            text = text[:start] + bind_fn.lstrip("\n") + text[end:]

    old_early_rst = (
        "\tstruct clk *bus;\n"
        "\tstruct reset_control *rst;\n"
        "\tint addr, found = 0;\n\n"
        "\t/* 官方 sunxi-gmac：先开 AHB/MDC，再扫 AC300，后复位 MAC。 */\n"
        "\tbus = of_clk_get_by_name(dev->of_node, \"stmmaceth\");\n"
        "\tif (!IS_ERR(bus))\n"
        "\t\tclk_prepare_enable(bus);\n"
        "\trst = reset_control_get_optional_shared(dev, \"stmmaceth\");\n"
        "\tif (!IS_ERR_OR_NULL(rst)) {\n"
        "\t\treset_control_deassert(rst);\n"
        "\t\treset_control_put(rst);\n"
        "\t}\n"
    )
    new_early_rst = (
        "\tstruct clk *bus;\n"
        "\tint addr, found = 0;\n\n"
        "\t/* init 已 deassert stmmaceth；再 get 同一条 reset 会 WARN。 */\n"
        "\tbus = of_clk_get_by_name(dev->of_node, \"stmmaceth\");\n"
        "\tif (!IS_ERR(bus))\n"
        "\t\tclk_prepare_enable(bus);\n"
    )
    if old_early_rst in text:
        text = text.replace(old_early_rst, new_early_rst, 1)

    _expect_count(text, "static const struct reg_field sun8i_syscon_reg_field =", 1, str(src))
    _expect_count(text, "emac_variant_h616_emac1", 3, str(src))
    _expect_count(text, "sun8i_dwmac_wait_ac200", 2, str(src))
    _expect_count(text, "sun8i_dwmac_ac300_mdio", 2, str(src))
    _expect_count(text, "sun8i_dwmac_ac300_early", 2, str(src))
    _expect_count(text, "sun8i_dwmac_bind_ephy", 2, str(src))
    src.write_text(text, encoding="utf-8")
    print("patched", src)


def patch_hdmi_phy(src: Path) -> None:
    text = src.read_text(encoding="utf-8", errors="replace")
    tables = r"""
static const struct dw_hdmi_mpll_config sun50i_h616_mpll_cfg[] = {
	{ 27000000, { {0x00b3, 0x0003}, {0x2153, 0x0003}, {0x40f3, 0x0003}, }, },
	{ 74250000, { {0x0072, 0x0003}, {0x2145, 0x0003}, {0x4061, 0x0003}, }, },
	{ 148500000, { {0x0051, 0x0003}, {0x214c, 0x0003}, {0x4064, 0x0003}, }, },
	{ 297000000, { {0x0040, 0x0003}, {0x3b4c, 0x0003}, {0x5a64, 0x0003}, }, },
	{ 594000000, { {0x1a40, 0x0003}, {0x3b4c, 0x0003}, {0x5a64, 0x0003}, }, },
	{ ~0UL, { {0x0000, 0x0000}, {0x0000, 0x0000}, {0x0000, 0x0000}, }, }
};

static const struct dw_hdmi_curr_ctrl sun50i_h616_cur_ctr[] = {
	{ 27000000, { 0x0012, 0x0000, 0x0000 }, },
	{ 74250000, { 0x0013, 0x0013, 0x0013 }, },
	{ 148500000, { 0x0019, 0x0019, 0x0019 }, },
	{ 297000000, { 0x0019, 0x001b, 0x0019 }, },
	{ 594000000, { 0x0010, 0x0010, 0x0010 }, },
	{ ~0UL, { 0x0000, 0x0000, 0x0000 }, }
};

static const struct dw_hdmi_phy_config sun50i_h616_phy_config[] = {
	{27000000, 0x8009, 0x0007, 0x02b0},
	{74250000, 0x8019, 0x0004, 0x0290},
	{148500000, 0x8019, 0x0004, 0x0290},
	{297000000, 0x8039, 0x0004, 0x022b},
	{594000000, 0x8029, 0x0000, 0x008a},
	{~0UL, 0x0000, 0x0000, 0x0000}
};

"""
    if "sun50i_h616_hdmi_phy" not in text:
        text = once_replace(
            text,
            "static const struct sun8i_hdmi_phy_variant sun50i_h6_hdmi_phy = {",
            tables
            + "static const struct sun8i_hdmi_phy_variant sun50i_h616_hdmi_phy = {\n"
            "	.cur_ctr = sun50i_h616_cur_ctr,\n"
            "	.mpll_cfg = sun50i_h616_mpll_cfg,\n"
            "	.phy_cfg = sun50i_h616_phy_config,\n"
            "	.phy_init = &sun50i_hdmi_phy_init_h6,\n"
            "};\n\n"
            "static const struct sun8i_hdmi_phy_variant sun50i_h6_hdmi_phy = {",
        )
        text = insert_before(
            text,
            '\t{\n\t\t.compatible = "allwinner,sun50i-h6-hdmi-phy",\n',
            '\t{\n'
            '\t\t.compatible = "allwinner,sun50i-h616-hdmi-phy",\n'
            "\t\t.data = &sun50i_h616_hdmi_phy,\n"
            "\t},\n",
        )
    if "static const struct sun8i_hdmi_phy_variant sun50i_h6_hdmi_phy = {\nstatic const" in text:
        raise SystemExit(f"{src}: nested h6 phy variant (once_replace bug)")
    _expect_count(text, "static const struct sun8i_hdmi_phy_variant sun50i_h6_hdmi_phy", 1, str(src))
    _expect_count(text, "sun50i_h616_hdmi_phy", 2, str(src))
    src.write_text(text, encoding="utf-8")
    print("patched", src)


def patch_tcon(h_path: Path, c_path: Path) -> None:
    h = h_path.read_text(encoding="utf-8", errors="replace")
    if "SUN4I_TCON_GCTL_PAD_SEL" not in h:
        if "SUN4I_TCON_GCTL_TCON_ENABLE" not in h:
            raise SystemExit("missing SUN4I_TCON_GCTL_TCON_ENABLE")
        lines = h.splitlines(keepends=True)
        out = []
        done = False
        for line in lines:
            out.append(line)
            if (not done) and "SUN4I_TCON_GCTL_TCON_ENABLE" in line:
                out.append("#define SUN4I_TCON_GCTL_PAD_SEL			BIT(1)\n")
                done = True
        h_path.write_text("".join(out), encoding="utf-8")
        print("patched", h_path)
    c = c_path.read_text(encoding="utf-8", errors="replace")
    snippet = """
	regmap_update_bits(tcon->regs, SUN4I_TCON_GCTL_REG,
			   SUN4I_TCON_GCTL_PAD_SEL,
			   SUN4I_TCON_GCTL_PAD_SEL);
"""
    marker = (
        "\tret = sun4i_tcon_init_regmap(dev, tcon);\n"
        "\tif (ret) {\n"
        '\t\tdev_err(dev, "Couldn\'t init our TCON regmap\\n");\n'
        "\t\tgoto err_assert_reset;\n"
        "\t}\n"
    )
    if "SUN4I_TCON_GCTL_PAD_SEL" not in c:
        c = once_replace(c, marker, marker + snippet)
        if c.count(marker) != 1:
            raise SystemExit(f"{c_path}: TCON regmap init duplicated")
        c_path.write_text(c, encoding="utf-8")
        print("patched", c_path)


def patch_ccu_audio(src: Path) -> None:
    text = src.read_text(encoding="utf-8", errors="replace")
    old_pll = """/*
 * TODO: Determine SDM settings for the audio PLL. The manual suggests
 * PLL_FACTOR_N=16, PLL_POST_DIV_P=2, OUTPUT_DIV=2, pattern=0xe000c49b
 * for 24.576 MHz, and PLL_FACTOR_N=22, PLL_POST_DIV_P=3, OUTPUT_DIV=2,
 * pattern=0xe001288c for 22.5792 MHz.
 * This clashes with our fixed PLL_POST_DIV_P.
 */
#define SUN50I_H616_PLL_AUDIO_REG	0x078
static struct ccu_nm pll_audio_hs_clk = {
	.enable		= BIT(31),
	.lock		= BIT(28),
	.n		= _SUNXI_CCU_MULT_MIN(8, 8, 12),
	.m		= _SUNXI_CCU_DIV(1, 1), /* input divider */
	.common		= {
		.reg		= 0x078,
		.hw.init	= CLK_HW_INIT("pll-audio-hs", "osc24M",
					      &ccu_nm_ops,
					      CLK_SET_RATE_UNGATE),
	},
};
"""
    new_pll = """static struct ccu_sdm_setting pll_audio_sdm_table[] = {
	{ .rate = 90316800, .pattern = 0xc001288d, .m = 3, .n = 22 },
	{ .rate = 98304000, .pattern = 0xc001eb85, .m = 5, .n = 40 },
};

#define SUN50I_H616_PLL_AUDIO_REG	0x078
static struct ccu_nm pll_audio_hs_clk = {
	.enable		= BIT(31),
	.lock		= BIT(28),
	.n		= _SUNXI_CCU_MULT_MIN(8, 8, 12),
	.m		= _SUNXI_CCU_DIV(16, 6),
	.sdm		= _SUNXI_CCU_SDM(pll_audio_sdm_table,
					 BIT(24), 0x178, BIT(31)),
	.fixed_post_div	= 2,
	.common		= {
		.features	= CCU_FEATURE_FIXED_POSTDIV |
				  CCU_FEATURE_SIGMA_DELTA_MOD,
		.reg		= 0x078,
		.hw.init	= CLK_HW_INIT("pll-audio-hs", "osc24M",
					      &ccu_nm_ops,
					      CLK_SET_RATE_UNGATE),
	},
};
"""
    if "pll_audio_sdm_table" not in text:
        if old_pll not in text:
            raise SystemExit(f"{src}: audio PLL block not found")
        text = text.replace(old_pll, new_pll, 1)
        text = text.replace(
            "\t\t    96, 1, CLK_SET_RATE_PARENT);\n"
            "static CLK_FIXED_FACTOR_HWS(pll_audio_2x_clk, \"pll-audio-2x\",\n"
            "\t\t    clk_parent_pll_audio,\n"
            "\t\t    48, 1, CLK_SET_RATE_PARENT);\n"
            "static CLK_FIXED_FACTOR_HWS(pll_audio_4x_clk, \"pll-audio-4x\",\n"
            "\t\t    clk_parent_pll_audio,\n"
            "\t\t    24, 1, CLK_SET_RATE_PARENT);\n",
            "\t\t    4, 1, CLK_SET_RATE_PARENT);\n"
            "static CLK_FIXED_FACTOR_HWS(pll_audio_2x_clk, \"pll-audio-2x\",\n"
            "\t\t    clk_parent_pll_audio,\n"
            "\t\t    2, 1, CLK_SET_RATE_PARENT);\n"
            "static CLK_FIXED_FACTOR_HWS(pll_audio_4x_clk, \"pll-audio-4x\",\n"
            "\t\t    clk_parent_pll_audio,\n"
            "\t\t    1, 1, CLK_SET_RATE_PARENT);\n",
            1,
        )
        old_div = """	/*
	 * Force the post-divider of pll-audio to 12 and the output divider
	 * of it to 2, so 24576000 and 22579200 rates can be set exactly.
	 */
	val = readl(reg + SUN50I_H616_PLL_AUDIO_REG);
	val &= ~(GENMASK(21, 16) | BIT(0));
	writel(val | (11 << 16) | BIT(0), reg + SUN50I_H616_PLL_AUDIO_REG);
"""
        new_div = """	/*
	 * SDM: M0 output-divider = 2, M1 input-divider = 1 (H616 manual).
	 */
	val = readl(reg + SUN50I_H616_PLL_AUDIO_REG);
	val &= ~BIT(1);
	val |= BIT(0);
	writel(val, reg + SUN50I_H616_PLL_AUDIO_REG);
"""
        if old_div not in text:
            raise SystemExit(f"{src}: audio PLL probe divider not found")
        text = text.replace(old_div, new_div, 1)
        src.write_text(text, encoding="utf-8")
        print("patched", src)


def install_regdb_firmware(linux: Path, here: Path) -> None:
    dest = linux / "firmware"
    dest.mkdir(parents=True, exist_ok=True)
    src = here / "firmware"
    for name in ("regulatory.db", "regulatory.db.p7s"):
        shutil.copy2(src / name, dest / name)
    print("installed regulatory.db into kernel firmware/")


def install_de33(linux: Path, here: Path) -> None:
    drm = linux / "drivers/gpu/drm/sun4i"
    src = here / "drivers/gpu/drm/sun4i"
    for name in (
        "sun8i_mixer.c",
        "sun8i_mixer.h",
        "sun8i_ui_layer.c",
        "sun8i_vi_layer.c",
        "sun8i_ui_scaler.c",
        "sun8i_vi_scaler.c",
        "sun8i_csc.c",
    ):
        shutil.copy2(src / name, drm / name)
    print("installed DE33 mixer from 6.17")


def install_codec(linux: Path, here: Path) -> None:
    shutil.copy2(
        here / "sound/soc/sunxi/sun4i-codec.c",
        linux / "sound/soc/sunxi/sun4i-codec.c",
    )
    print("installed H616 sun4i-codec")


def install_ahub(linux: Path, here: Path) -> None:
    dest = linux / "sound/soc/sunxi"
    src = here / "sound/soc/sunxi"
    for name in (
        "sun50i-ahub.c",
        "sun50i-ahub-cpudai.c",
        "sun50i-ahub-daudio.c",
        "sun50i-sndahub.c",
        "sun50i-sndhdmi.c",
        "sun50i_ahub.h",
        "sun50i-ahub-compat.h",
    ):
        shutil.copy2(src / name, dest / name)
    kcfg = dest / "Kconfig"
    kd = kcfg.read_text(encoding="utf-8", errors="replace")
    block = """
config SND_SOC_SUN50I_AHUB
	tristate "Allwinner H616 audio hub"
	depends on ARCH_SUNXI || COMPILE_TEST
	select REGMAP_MMIO
	select SND_SOC_GENERIC_DMAENGINE_PCM
	help
	  H616 AHUB. HDMI 音频走这条通路，3.5mm 仍用 sun4i-codec。

config SND_SOC_SUN50I_HDMI
	tristate "Allwinner H616 HDMI audio machine"
	depends on SND_SOC_SUN50I_AHUB
	help
	  ALSA 卡名 ahubhdmi。
"""
    if "config SND_SOC_SUN50I_AHUB" not in kd:
        kcfg.write_text(kd.rstrip() + "\n" + block + "\n", encoding="utf-8")
    mk = dest / "Makefile"
    for line in (
        "obj-$(CONFIG_SND_SOC_SUN50I_AHUB) += sun50i-ahub.o",
        "obj-$(CONFIG_SND_SOC_SUN50I_AHUB) += sun50i-ahub-cpudai.o",
        "obj-$(CONFIG_SND_SOC_SUN50I_AHUB) += sun50i-ahub-daudio.o",
        "obj-$(CONFIG_SND_SOC_SUN50I_AHUB) += sun50i-sndahub.o",
        "obj-$(CONFIG_SND_SOC_SUN50I_HDMI) += sun50i-sndhdmi.o",
    ):
        append_line(mk, line)
    print("installed H616 AHUB")


def install_prcm_ppu(linux: Path, here: Path) -> None:
    src = here / "drivers/pmdomain/sunxi/sun50i-h6-prcm-ppu.c"
    dest_dir = linux / "drivers/pmdomain/sunxi"
    dest_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dest_dir / "sun50i-h6-prcm-ppu.c")
    kcfg = dest_dir / "Kconfig"
    kd = kcfg.read_text(encoding="utf-8", errors="replace")
    block = """
config SUN50I_H6_PRCM_PPU
	tristate "Allwinner H6/H616 PRCM power domain"
	depends on ARCH_SUNXI || COMPILE_TEST
	depends on PM
	select PM_GENERIC_DOMAINS
	help
	  PRCM power bits for H616 Mali G31. Required to probe Panfrost.
"""
    if "config SUN50I_H6_PRCM_PPU" not in kd:
        kcfg.write_text(kd + block, encoding="utf-8")
    append_line(dest_dir / "Makefile", "obj-$(CONFIG_SUN50I_H6_PRCM_PPU) += sun50i-h6-prcm-ppu.o")
    print("installed H616 PRCM PPU")


def install_pwm(linux: Path, here: Path) -> None:
    src = here / "drivers/pwm/pwm-sun50i-h616.c"
    shutil.copy2(src, linux / "drivers/pwm/pwm-sun50i-h616.c")
    kcfg = linux / "drivers/pwm/Kconfig"
    kd = kcfg.read_text(encoding="utf-8", errors="replace")
    block = """
config PWM_SUN50I_H616
	tristate "Allwinner H616 PWM"
	depends on ARCH_SUNXI || COMPILE_TEST
	help
	  PWM controller on Allwinner H616/H618, used for AC200 24MHz clock.
"""
    if "config PWM_SUN50I_H616" not in kd:
        kcfg.write_text(kd + block, encoding="utf-8")
    append_line(linux / "drivers/pwm/Makefile", "obj-$(CONFIG_PWM_SUN50I_H616) += pwm-sun50i-h616.o")
    print("installed H616 PWM")


def install_ac200(linux: Path, here: Path) -> None:
    mfd_h = here / "include/linux/mfd/ac200.h"
    mfd_c = here / "drivers/mfd/ac200.c"
    phy_c = here / "drivers/net/phy/ac200-ephy.c"
    (linux / "include/linux/mfd").mkdir(parents=True, exist_ok=True)
    shutil.copy2(mfd_h, linux / "include/linux/mfd/ac200.h")
    shutil.copy2(mfd_c, linux / "drivers/mfd/ac200.c")
    shutil.copy2(phy_c, linux / "drivers/net/phy/ac200-ephy.c")

    mfd_k = linux / "drivers/mfd/Kconfig"
    mk = mfd_k.read_text(encoding="utf-8", errors="replace")
    block = """
config MFD_AC200
	tristate "X-Powers AC200"
	depends on I2C
	select MFD_CORE
	select REGMAP_I2C
	select REGMAP_IRQ
	help
	  MFD core for the X-Powers AC200 companion (EPHY + analog).
"""
    if "config MFD_AC200" not in mk:
        mfd_k.write_text(mk + block, encoding="utf-8")
    append_line(linux / "drivers/mfd/Makefile", "obj-$(CONFIG_MFD_AC200) += ac200.o")

    phy_k = linux / "drivers/net/phy/Kconfig"
    pk = phy_k.read_text(encoding="utf-8", errors="replace")
    pblock = """
config AC200_PHY
	tristate "X-Powers AC200 Ethernet PHY"
	depends on PHYLIB && MFD_AC200
	help
	  Driver for the 100Mbit EPHY inside the X-Powers AC200.
"""
    if "config AC200_PHY" not in pk:
        phy_k.write_text(pk + pblock, encoding="utf-8")
    append_line(linux / "drivers/net/phy/Makefile", "obj-$(CONFIG_AC200_PHY) += ac200-ephy.o")
    print("installed AC200 MFD+PHY")


def patch_uwe_aw_wake_flags(dest: Path) -> None:
    """AW UWE5622 enables BT/WL wake-host which looks up allwinner,sunxi-btlpm.

    WalnutPi DTS has no such node. Probe then returns -EINVAL and the BSP
    never comes up cleanly. WiFi reset is mmc-pwrseq PG18, not those GPIOs.
    """
    mk = dest / "unisocwcn" / "Makefile"
    text = mk.read_text(encoding="utf-8", errors="replace")
    needle = (
        "ccflags-y += -DCONFIG_BT_WAKE_HOST_EN\n"
        "ccflags-y += -DCONFIG_WL_WAKE_HOST_EN\n"
    )
    extra = (
        "# WalnutPi: no allwinner,sunxi-btlpm node; keep mmc-pwrseq only.\n"
        "# ccflags-y += -DCONFIG_BT_WAKE_HOST_EN\n"
        "# ccflags-y += -DCONFIG_WL_WAKE_HOST_EN\n"
    )
    # Only the Allwinner block has both flags on consecutive lines after
    # CONFIG_WCN_POWER_UP_DOWN. Replace the last occurrence (AW section).
    idx = text.rfind(needle)
    if idx < 0:
        print("WARNING: AW BT/WL wake flags not found in", mk)
        return
    text = text[:idx] + extra + text[idx + len(needle) :]
    mk.write_text(text, encoding="utf-8")
    print("patched AW wake-host flags in", mk)


def install_uwe5622(linux: Path) -> None:
    src = Path(os.environ.get("UWE5622_SRC", "/uwe5622"))
    if not src.is_dir():
        alt = Path("/factory") / ".."  # unused
        print("WARNING: UWE5622_SRC not found at", src)
        return
    dest = linux / "drivers/net/wireless/uwe5622"
    if dest.exists():
        shutil.rmtree(dest)
    shutil.copytree(
        src,
        dest,
        ignore=shutil.ignore_patterns(".git", "reference", "workflow_files", "*.orig"),
    )
    patch_uwe_aw_wake_flags(dest)
    kcfg = linux / "drivers/net/wireless/Kconfig"
    kd = kcfg.read_text(encoding="utf-8", errors="replace")
    line = 'source "drivers/net/wireless/uwe5622/Kconfig"'
    if line not in kd:
        kcfg.write_text(kd.rstrip() + "\n\n" + line + "\n", encoding="utf-8")
    append_line(
        linux / "drivers/net/wireless/Makefile",
        "obj-$(CONFIG_SPARD_WLAN_SUPPORT) += uwe5622/",
    )
    print("installed UWE5622 from", src)


def patch_hci_link_policy(linux: Path) -> None:
    """Unisoc rejects HCI_OP_WRITE_DEF_LINK_POLICY (0x080f); do not abort init."""
    path = linux / "net/bluetooth/hci_sync.c"
    text = path.read_text(encoding="utf-8", errors="replace")
    if "Write Default Link Policy ignored" in text:
        print("hci_sync: Unisoc 0x080f ignore already present")
        return
    needle = (
        "\tcp.policy = cpu_to_le16(link_policy);\n"
        "\n"
        "\treturn __hci_cmd_sync_status(hdev, HCI_OP_WRITE_DEF_LINK_POLICY,\n"
        "\t\t\t\t     sizeof(cp), &cp, HCI_CMD_TIMEOUT);\n"
        "}\n"
    )
    extra = (
        "\tcp.policy = cpu_to_le16(link_policy);\n"
        "\n"
        "\terr = __hci_cmd_sync_status(hdev, HCI_OP_WRITE_DEF_LINK_POLICY,\n"
        "\t\t\t\t     sizeof(cp), &cp, HCI_CMD_TIMEOUT);\n"
        "\t/* UWE5622/Marlin3: 0x080f often returns Invalid Parameters.\n"
        "\t * Keep going so hci0 can finish setup.\n"
        "\t */\n"
        "\tif (err)\n"
        '\t\tbt_dev_warn(hdev, "Write Default Link Policy ignored (%d)", err);\n'
        "\treturn 0;\n"
        "}\n"
    )
    if needle not in text:
        raise SystemExit("hci_setup_link_policy_sync return not found")
    text = text.replace(needle, extra, 1)
    old_decl = (
        "static int hci_setup_link_policy_sync(struct hci_dev *hdev)\n"
        "{\n"
        "\tstruct hci_cp_write_def_link_policy cp;\n"
        "\tu16 link_policy = 0;\n"
    )
    new_decl = (
        "static int hci_setup_link_policy_sync(struct hci_dev *hdev)\n"
        "{\n"
        "\tstruct hci_cp_write_def_link_policy cp;\n"
        "\tu16 link_policy = 0;\n"
        "\tint err;\n"
    )
    if old_decl not in text:
        raise SystemExit("hci_setup_link_policy_sync decl not found")
    text = text.replace(old_decl, new_decl, 1)
    path.write_text(text, encoding="utf-8")
    print("patched", path, "ignore 0x080f")


def patch_dts_makefile(linux: Path) -> None:
    mk = linux / "arch/arm64/boot/dts/allwinner/Makefile"
    append_line(mk, "dtb-$(CONFIG_ARCH_SUNXI) += sun50i-h616-walnutpi-1b.dtb")
    print("patched", mk)


def main() -> None:
    linux = Path(sys.argv[1])
    here = Path(sys.argv[2])
    dtsi = linux / "arch/arm64/boot/dts/allwinner/sun50i-h616.dtsi"
    patch_dtsi(dtsi)
    patch_dwmac(linux / "drivers/net/ethernet/stmicro/stmmac/dwmac-sun8i.c")
    patch_hdmi_phy(linux / "drivers/gpu/drm/sun4i/sun8i_hdmi_phy.c")
    patch_tcon(
        linux / "drivers/gpu/drm/sun4i/sun4i_tcon.h",
        linux / "drivers/gpu/drm/sun4i/sun4i_tcon.c",
    )
    patch_ccu_audio(linux / "drivers/clk/sunxi-ng/ccu-sun50i-h616.c")
    install_regdb_firmware(linux, here)
    install_de33(linux, here)
    install_codec(linux, here)
    install_ahub(linux, here)
    install_pwm(linux, here)
    install_prcm_ppu(linux, here)
    install_ac200(linux, here)
    install_uwe5622(linux)
    patch_hci_link_policy(linux)
    patch_dts_makefile(linux)


if __name__ == "__main__":
    main()
