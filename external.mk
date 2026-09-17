include $(sort $(wildcard $(BR2_EXTERNAL_WALNUTPI_PATH)/package/*/*.mk))

# Inject H616 EMAC1/HDMI/PWM/AC200 and Unisoc UWE5622 after the
# kernel tarball is extracted. linux.mk is included before this file.
define WALNUTPI_LINUX_INJECT_H616
	$(BR2_EXTERNAL_WALNUTPI_PATH)/board/walnutpi-1b/linux/inject-h616.sh $(LINUX_DIR)
endef
LINUX_POST_PATCH_HOOKS += WALNUTPI_LINUX_INJECT_H616

define WALNUTPI_UBOOT_INJECT
	sh $(BR2_EXTERNAL_WALNUTPI_PATH)/board/walnutpi-1b/uboot/inject.sh $(UBOOT_DIR)
endef
UBOOT_POST_PATCH_HOOKS += WALNUTPI_UBOOT_INJECT
