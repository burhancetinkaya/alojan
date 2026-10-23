# Carrier greeting with startup padding (v4)

The owner reported that the initial `Merhaba` was not audible on the phone.
The v3 file hash matched its approved manifest; resident CUDA ASR decoded its first
second as `Merhaba ben Burhan`. Its first sample above amplitude 500 occurred at
32 ms. Early handset/carrier media clipping is a plausible explanation, not yet
proven by a carrier capture.

V4 prepends 3200 zero samples (400 ms) to the original 8 kHz mono PCM16 greeting.
All original speech samples are retained byte-for-byte; text, voice, named owner
and AI disclosure are unchanged. The fallback WAV/text are copied unchanged.
The original model/dependency/license provenance remains in `../tr-v3-ema`;
`manifest.json` pins that source manifest and each resulting file hash. This is
PCM padding, not a new model inference or a new listening acceptance claim.

The Netgsm launcher selects this profile. The default local gateway fixture
remains v3. Silence is transmitted as ordinary paced RTP immediately after ACK,
allowing a short media startup interval before the first word. It does not delay
SIP answer, later conversational replies or waiting music. A handset clipping
more than the chosen pad still requires carrier-specific calibration.

Reproduce the greeting from the pinned v3 source (Python standard library):

```python
from pathlib import Path
import wave
source = Path('assets/prompts/tr-v3-ema/greeting.wav')
target = Path('assets/prompts/tr-v4-ema/greeting.wav')
with wave.open(str(source)) as audio:
    params = audio.getparams()
    pcm = audio.readframes(audio.getnframes())
with wave.open(str(target), 'wb') as audio:
    audio.setparams(params)
    audio.writeframes(bytes(6400) + pcm)
```

Regression tests verify the padding, complete source preservation and checksums.
Both-codec loopback carrier tests discard the initial 300 ms and compare the
remaining opening word against v3. Real handset listening remains pending.
