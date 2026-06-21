# FULL VERBATIM + TIMESTAMPS — capability demo

> **This is NOT the test submission.** The GoTranscript test requires **clean verbatim, no timestamps** (fillers/false-starts removed) — that's the version staged in the editor.
> This file shows the *opposite* mode so you can see the full ability: **everything kept** — every "umm/えっと", every broken word (`--`), plus a **bold timestamp at every speaker change** (GoTranscript `[HH:MM:SS]` format). Timestamps are real, pulled from Whisper.

---

**[00:00:00]** **Sora:** えっと、じゃあ、そうですね、あー、Hello, nice to meet you. My name is Sora, and I'm honored to--

**[00:00:08]** **Speaker 2:** ちょっと待ってください。ひょっとして、適当に言ってませんか？

**[00:00:14]** **Sora:** え？なんか、そういう人いるんですよね。わからないと思って、適当に言ってしまえばいいと思っている人。

**[00:00:22]** **Speaker 2:** え、でも、本当に普通に話して-- じゃあ、もっと分かりやすく、ちゃんと言ってみてくださいよ。

**[00:00:27]** **Sora:** 分かりやすく？こいつ、何言ってんだ？ You speak English. Right. まさか。 Hello, nice to meet you. My name is Sora.

**[00:00:41]** **Speaker 2:** Oh my God. Your English is good.

**[00:00:45]** **Sora:** あの、ちょっと疑問なんですけど、それ、本気でやってますか？

**[00:00:48]** **Speaker 2:** [shushing] I want to hear you speak English more. Well, I don't know if I'm supposed to say something funny or-- [shushing] I don't understand you.

**[00:00:59]** **Sora:** こいつ、マジか。嘘だろ。 I love this movie called *Mission: Impossible*.

**[00:01:05]** **Speaker 2:** Oh my God. I like *Mission: Impossible* too.

**[00:01:09]** **Sora:** あの、もういいですよね。

**[00:01:12]** **Speaker 2:** [scoffs] Your English is very good, but--

---

## What changed vs the clean-verbatim submission
| Element | Clean (submitted) | Full (this file) |
|---|---|---|
| Fillers (えっと, あー, あの, なんか) | removed | **kept** |
| Broken word / false start (話して--) | smoothed out | **kept with `--`** |
| Timestamps | none | **[HH:MM:SS] at every speaker change** |
| Expressions (Oh my God) | kept | kept |
| Sound events ([shushing], [scoffs]) | kept | kept |

Both modes from the same 4-witness pipeline — the only difference is whether the deterministic finishing pass strips the fillers and whether timestamps are inserted.
