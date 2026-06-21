"""Run the GoTranscript Japanese quiz through the system: Qwen (Japanese-fluent worker)
answers each question; compare to the guideline-verified deterministic answers. Where
the two INDEPENDENT reads agree -> confident. Where they disagree -> the catch to check.
Nothing is submitted."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from transcript_truth.worker import qwen

Q = [
 (1, "次の文の「」の部分に入れる言葉として最も適切なものは？ 文）お足元にお気をつけて「」。",
     "a. ください\nb. 下さい\nc. ろ\nd. て", "a"),
 (2, "テキストフォーマットがFull Verbatimのとき、次の文を訂正した結果として最も適切なものは？ 文）国賓である総理、いや大統領を冷偶するのは当然で、当然である。",
     "a. 国賓である大統領を冷遇するのは当然である。\nb. 国賓である総理-いや大統領を冷偶するのは当然で-当然である。\nc. 国賓である総理--いや大統領を礼遇するのは当然で--当然である。\nd. 国賓である総理--いや大統領を礼偶するのは当然で--当然である。", "c"),
 (3, "Speaker 1の声のように思えるが確信が持てないときのスピーカーラベルとして正しいものは？",
     "a. ?Speaker 1:\nb. Speaker 1?:\nc. Speaker 1:?\nd. Speaker? 1:", "a"),
 (4, "次の対話を訂正するとき正しいものは？ Speaker 1: あなたはいつも意義を唱えるだけで全く、 Speaker 2: うるさい馬鹿。議長こいつを黙らせて。 Speaker 1: 建設的ではない。論理的に思考できないのか。",
     "a. 意義/単ダッシュ/[crosstalk]を継続行に\nb. 異議/うるさい(馬鹿削除)/単ダッシュ/crosstalkなし\nc. 意義/全角ダッシュ/[crosstalk]\nd. 異議/うるさい馬鹿(保持)/[crosstalk]+単ダッシュ", "d"),
 (5, "音声全体55分、11パートに分割、自分は3パート目、現在のパート内時間は2分。打つべきタイムスタンプは？",
     "a. [00:12:00]\nb. [00:17:00]\nc. [00:22:00]\nd. [00:02:00]", "a"),
 (6, "次の文の「」に入れる最も適切なものは？ 文）私がそう「」丁度その時、彼がやってきた。",
     "a. いった\nb. 言う\nc. 言った\nd. だった", "c"),
 (7, "Full Verbatimで、話者Aが話し始め、話者Bが話し始めて遮り、Aがその後話を続けなかった場合、遮られたAの行末はどう打つ？",
     "a. 。\nb. -\nc. …\nd. --", "d"),
 (8, "コメントに'Please use the embedded time'。全体25分、5パート、3パート目、ツール表示20秒、動画表示9分25秒。打つべきタイムスタンプは？",
     "a. [00:15:20]\nb. [00:10:20]\nc. [00:19:25]\nd. [00:09:25]", "d"),
 (9, "Clean Verbatimで、次を訂正するとき最も適切なものは？ 文）Speaker 1: わっ！ビックリした。[laughter] 動機がすごいよ。辞めてよ。 Speaker 2: 以外にビビりだね。[laughs]",
     "a. 動機/やめて/意外(わっ！保持)\nb. 動悸/止めて/以外([laughter]改行)\nc. わっ。動悸/やめて/意外([laughter]改行)\nd. 動機/辞めて/以外([laughter]改行)", "c"),
 (10, "話者が笑った部分に入れる注として正しいものは？",
      "a. [smile]\nb. [laughter]\nc. [laughs]\nd. [silence]", "c"),
]

print("Q  | Qwen | mine | agree?")
agree = 0
rows = []
for n, q, opts, mine in Q:
    prompt = ("あなたはGoTranscriptの日本語書き起こしルールに精通した校正者です。次の選択問題の正しい選択肢を、アルファベット一文字だけで答えてください（説明不要）。\n\n"
              f"問題：{q}\n\n選択肢：\n{opts}")
    ans = qwen([{"role": "user", "content": prompt}], max_tokens=20).strip().lower()
    # extract first letter a-d
    letter = next((c for c in ans if c in "abcd"), "?")
    ok = letter == mine
    agree += ok
    rows.append((n, letter, mine, ok))
    print(f"{n:<2} |  {letter}   |  {mine}   | {'AGREE' if ok else 'DISAGREE <-- check'}")

print("\n" + "=" * 50)
print(f"Qwen vs guideline-verified: {agree}/10 agree")
dis = [r[0] for r in rows if not r[3]]
print(f"Disagreements to check: {dis if dis else 'none — both reads match on all 10'}")
