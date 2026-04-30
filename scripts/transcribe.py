#!/usr/bin/env python3
"""
auto-transcribe — 批次將聲音檔轉文字並輸出 SRT 字幕。
用法：
  python3 transcribe.py "<音檔路徑>"
  python3 transcribe.py "<目錄路徑>"    # 批次處理目錄下所有音訊檔

輸出：
  <音檔同目錄>/<音檔名>_draft_v1.srt
  <音檔同目錄>/已完成字幕檔列表.md      （每次成功後附加）
"""

import sys, os, json, time
from pathlib import Path
from faster_whisper import WhisperModel

# ── 1331 專屬 prompt（用於語音辨識品質）───────────────────────────────
INITIAL_PROMPT = (
    "這是一三三一人文講堂的讀書會錄音，主題是《佛說阿彌陀經要解》，"
    "常見詞彙：阿彌陀佛、極樂世界、蕅益大師、印光大師、智者大師、"
    "蓮池大師、《彌陀要解》、信願行、執持名號、一心不亂、流通分、五重玄義。 "
    "請使用繁體中文、佛教正規譯名、全形標點。"
)

# ── SRT 時間軸格式化 ───────────────────────────────────────────────
def fmt_ts(s: float) -> str:
    h = int(s // 3600); s -= h * 3600
    m = int(s // 60); s -= m * 60
    sec = int(s); ms = int((s - sec) * 1000)
    return f"{h:02d}:{m:02d}:{sec:02d},{ms:03d}"

# ── 助詞 / 連接詞列表（不在這些詞後面斷行）───────────────────────
PARTICLES = {"的","了","在","和","與","及","為","於","是","有","我","你","他","這","那","過","來","去","說","看","從","但","而","卻","還","也","都","又","只","要","會","可","讓","被","使","曾","已","把","跟","用","以","或","如","若","因","所","故","個","些","本","此","其","並","且","於是","所以","因為","但是","然而","雖然"}

# ── SRT 字幕格式化（每行最多15字、助詞不斷行、標點優先斷行）─────────
def format_srt_text(text: str) -> str:
    """將長文字斷行為 SRT 顯示行，遵守三規則："""
    # 1. 先以全形標點分句
    sentences = []
    for chunk in text.split("。"):
        if chunk.strip():
            sentences.append(chunk.strip() + ("。" if chunk else ""))
    for chunk in text.split("，"):
        if chunk.strip() and "。" not in chunk:
            sentences.append(chunk.strip() + "，")
    for chunk in text.split("、"):
        if chunk.strip():
            sentences.append(chunk.strip() + "、")
    for chunk in text.split("；"):
        if chunk.strip():
            sentences.append(chunk.strip() + "；")
    for chunk in text.split("："):
        if chunk.strip():
            sentences.append(chunk.strip() + "：")
    for chunk in text.split("！"):
        if chunk.strip():
            sentences.append(chunk.strip() + "！")
    for chunk in text.split("？"):
        if chunk.strip():
            sentences.append(chunk.strip() + "？")
    # 去除空白字元
    raw = list(text)
    result = []
    current_line = ""
    current_len = 0

    for ch in text:
        # 遇到標點：優先在標點處截斷
        if ch in "。，、；：！？":
            current_line += ch
            current_len += 1
            result.append(current_line)
            current_line = ""
            current_len = 0
        elif current_len >= 15:
            # 已經滿15字，找最後一個助詞位置截斷
            line_to_check = current_line.rstrip()
            cut_pos = -1
            # 由後往前找助詞
            for i in range(len(line_to_check) - 1, -1, -1):
                w = line_to_check[i:]
                if w in PARTICLES or line_to_check[i] in "的的你了在和與及為於是有我你他這那過來去說看從但而卻還也都又把跟用以或如若因所故個些本此其並且於是所以因為但是然而雖然":
                    cut_pos = i
                    break
            if cut_pos > 0:
                result.append(line_to_check[:cut_pos])
                remainder = line_to_check[cut_pos:]
                current_line = remainder
                current_len = len(remainder)
            else:
                result.append(line_to_check)
                current_line = ""
                current_len = 0
        else:
            current_line += ch
            current_len += 1

    if current_line.strip():
        result.append(current_line)

    # 合併：每個 subtitle block 最多 2 行
    lines = [l for l in result if l.strip()]
    if len(lines) > 2:
        # 超出時合併成長句再截斷
        merged = "".join(lines)
        lines = []
        i = 0
        while i < len(merged):
            end = min(i + 15, len(merged))
            if end < len(merged) and merged[end-1] not in "。，、；：！？":
                # 嘗試往前找標點
                for bp in range(end-1, i-1, -1):
                    if merged[bp] in "。，、；：！？":
                        end = bp + 1
                        break
            lines.append(merged[i:end])
            i = end
        lines = lines[:2]  # 強迫最多2行

    return "\n".join(lines)

# ── 寫入 SRT ───────────────────────────────────────────────────────
def write_srt(segments, output_path):
    lines = []
    for i, seg in enumerate(segments, 1):
        start = fmt_ts(seg.start)
        end = fmt_ts(seg.end)
        raw_text = seg.text.strip()
        text = format_srt_text(raw_text)
        lines.append(f"{i}\n{start} --> {end}\n{text}\n")
    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

# ── 寫入 完成列表.md ────────────────────────────────────────────────
def append_done_list(audio_path, srt_path, done_list_path):
    audio_name = os.path.basename(audio_path)
    srt_name = os.path.basename(srt_path)
    entry = f"- `{srt_name}`  ← source: `{audio_name}`\n"
    with open(done_list_path, "a", encoding="utf-8") as f:
        f.write(entry)

# ── 單檔處理 ────────────────────────────────────────────────────────
def transcribe_single(audio_path):
    audio_path = Path(audio_path).resolve()
    if not audio_path.exists():
        raise FileNotFoundError(f"音檔不存在：{audio_path}")

    directory = audio_path.parent
    stem = audio_path.stem                    # 無副檔名的檔名
    srt_path = directory / f"{stem}_draft_v1.srt"
    done_list_path = directory / "已完成字幕檔列表.md"

    print(f"[▶] 開始處理：{audio_path.name}", flush=True)

    # 模型載入（首次較慢，之後使用快取）
    t0 = time.time()
    model = WhisperModel("medium", device="cpu", compute_type="int8")
    print(f"[load] medium/int8 OK ({time.time()-t0:.1f}s)", flush=True)

    # 語音辨識
    t0 = time.time()
    segments, info = model.transcribe(
        str(audio_path),
        language="zh",
        beam_size=5,
        vad_filter=True,
        vad_parameters={"min_silence_duration_ms": 500},
        word_timestamps=True,
        initial_prompt=INITIAL_PROMPT,
        condition_on_previous_text=True,
    )
    seg_list = list(segments)
    print(f"[transcribe] {info.language} prob={info.language_probability:.3f} "
          f"dur={info.duration:.1f}s ({time.time()-t0:.1f}s)", flush=True)

    # 寫 SRT
    write_srt(seg_list, srt_path)
    print(f"[OK] SRT → {srt_path}", flush=True)

    # 更新完成列表
    append_done_list(audio_path, srt_path, done_list_path)
    print(f"[OK] 完成列表已更新：{done_list_path.name}", flush=True)

    return srt_path

# ── 主程式 ──────────────────────────────────────────────────────────
SUPPORTED_EXTENSIONS = {".mp3", ".wav", ".m4a", ".webm", ".ogg", ".flac", ".aac"}

def main():
    if len(sys.argv) < 2:
        print("用法：transcribe.py <音訊檔案或目錄>")
        sys.exit(1)

    target = Path(sys.argv[1]).resolve()

    if target.is_file():
        transcribe_single(target)
        print("\n✅ 完成！")
    elif target.is_dir():
        mp3_files = [
            f for f in target.iterdir()
            if f.suffix.lower() in SUPPORTED_EXTENSIONS
        ]
        if not mp3_files:
            print(f"目錄中找不到音訊檔：{target}")
            sys.exit(1)
        print(f"找到 {len(mp3_files)} 個音訊檔，開始批次處理...\n")
        for f in mp3_files:
            try:
                transcribe_single(f)
            except Exception as e:
                print(f"[ERROR] {f.name}：{e}")
        print("\n✅ 批次完成！")
    else:
        print(f"無效路徑：{target}")
        sys.exit(1)

if __name__ == "__main__":
    main()
