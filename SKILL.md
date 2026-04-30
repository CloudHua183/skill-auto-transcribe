---
name: auto-transcribe
description: 批次將目錄下的音訊檔（MP3/WAV/WebM/M4A/OGG/FLAC/AAC）自動轉換為 SRT 中文字幕。輸出「音檔名_draft_v1.srt」至同目錄，並自動維護「已完成字幕檔列表.md」。觸發時機：老闆提供包含聲音檔的目錄並要求生成逐字稿。
---

# auto-transcribe

使用 faster-whisper（Whisper medium model，CPU int8）在本地完成語音辨識，**不需要 API key**。

## 流程

1. 接收老闆指定的**音訊檔**或**目錄**
2. 對每個音訊檔執行：
   - faster-whisper medium 繁中語音辨識（beam_size=5 + VAD）
   - 輸出 SRT：音檔名_draft_v1.srt（同目錄）
   - 附加至 目錄/已完成字幕檔列表.md
3. 回報完成的 SRT 數量與路徑

## 輸出命名

| 項目 | 規則 |
|---|---|
| 字幕檔 | 音檔名_draft_v1.srt（與音訊檔同目錄）|
| 完成列表 | 已完成字幕檔列表.md（同目錄，每次成功後附加）|

## 執行命令

```bash
# 單檔
python3 /Users/cloudhuamacmini/.openclaw/skills/auto-transcribe/auto-transcribe/scripts/transcribe.py "音訊檔路徑"

# 批次（指定目錄）
python3 /Users/cloudhuamacmini/.openclaw/skills/auto-transcribe/auto-transcribe/scripts/transcribe.py "包含音訊檔的目錄"
```

## 支援格式

MP3 / WAV / WebM / M4A / OGG / FLAC / AAC

## 相依套件

```bash
pip3 install faster-whisper --break-system-packages
```

模型自動下載，無需額外設定。

## 1331 專案設定

辨識時使用繁體中文佛教術語強化 prompt（阿彌陀佛、極樂世界、蕅益大師、蓮池大師、智者大師、流通分、信願行、執持名號、一心不亂等）。
