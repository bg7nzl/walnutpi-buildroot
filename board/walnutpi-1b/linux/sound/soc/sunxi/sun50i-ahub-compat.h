/* SPDX-License-Identifier: GPL-2.0-or-later */
/* ASoC 6.8 asoc_* names → 6.12 snd_soc_* */
#ifndef _SUN50I_AHUB_COMPAT_H_
#define _SUN50I_AHUB_COMPAT_H_

#include <sound/soc.h>

#ifndef asoc_substream_to_rtd
#define asoc_substream_to_rtd snd_soc_substream_to_rtd
#endif
#ifndef asoc_rtd_to_cpu
#define asoc_rtd_to_cpu snd_soc_rtd_to_cpu
#endif
#ifndef asoc_rtd_to_codec
#define asoc_rtd_to_codec snd_soc_rtd_to_codec
#endif

#endif
