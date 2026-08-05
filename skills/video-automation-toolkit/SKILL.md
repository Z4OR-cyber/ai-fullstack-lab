---
name: video-automation-toolkit
description: 视频自动化剪辑全流程工具链技能。整合FFmpeg场景检测、moviepy剪辑、faster-whisper语音转文字、OpenCV帧分析，配合CC0免费素材库（Pexels/Pixabay/Mixkit等12+平台）和AI视频生成工具（可灵/即梦/通义万相），实现从素材获取到多格式输出的完整自动化流水线。当用户提到视频剪辑、自动剪辑、视频制作、短视频制作、素材搜索、视频文案解析、无水印下载、场景检测、语音转字幕等需求时使用此技能。
---

# 视频自动化剪辑工作链

整合本地工具链+免费素材库+AI生成平台，实现从素材获取到多格式输出的完整视频自动化流水线。

## 工具链（云电脑已就绪）

| 工具 | 用途 | 关键命令 |
|------|------|---------|
| FFmpeg 4.4.2 | 编码/转码/切片/场景检测 | `ffmpeg -i input.mp4 -filter:v "select='gt(scene,0.3)',showinfo" -f null -` |
| moviepy 2.1.2 | Python视频编辑 | 剪切/拼接/特效/字幕/水印 |
| faster-whisper 1.2.1 | 语音转文字(CTranslate2) | `model.transcribe('input.mp4', language='zh')` |
| opencv-headless 5.0.0.93 | 场景检测/帧分析 | 运动估计/人脸检测/质量评分 |
| n8n 2.31.6 | 工作流编排(可选) | 端口5678 |

## 免费CC0素材库

### 国际（优先，无署名要求）
- **Pexels**: https://www.pexels.com/videos/ — 50万+4K视频，有免费API
- **Pixabay**: https://pixabay.com/zh/videos/ — 20万+，CC0，中文搜索
- **Mixkit**: https://mixkit.co/ — 4K+模板+音效
- **Coverr**: https://coverr.co/ — 电影级，每周更新
- **Videvo**: https://www.videvo.net/ — 50万+，绿幕特效
- **Dareful**: https://dareful.com/ — 专注4K，CC0

### 国内
- **光厂CC0**: https://www.vjshi.com/cc0/ — 中国元素，8K
- **潮点视频**: https://shipin520.com/ — 4K/8K，每日免费1次
- **新CG儿**: https://www.newcger.com/ — AE模板+免费视频

### 搜索技巧
- 英文搜索结果更多更好；用情绪词搜索（如"focused work"而非"office"）
- 优先CC0；CC-BY素材在片尾标注来源；二次创作避免直接用原片

## AI视频生成（含免费额度）
| 平台 | 网址 | 免费额度 |
|------|------|---------|
| 可灵 | https://kling.kuaishou.com/ | 免费测试中 |
| 即梦AI | https://jimeng.jianying.com/ | 每日60积分 |
| 通义万相 | https://tongyi.aliyun.com/wanxiang/ | 每日50灵感值 |
| 智谱清影 | https://chatglm.cn/ | 免费(受限) |
| PixVerse | https://pixverse.ai/ | 有免费额度,Canvas工作流 |
| Adobe Firefly | https://firefly.adobe.com/ | 有免费额度,商用安全 |

### AI画布/可视化平台
- **ComfyUI**: 开源节点编辑器，SD/Flux
- **PixVerse Canvas**: 可视化AI视频工作流
- **Wireflow**: 50+模型链式调用+API
- **n8n(本地已装)**: 工作流自动化编排

## 无水印视频下载（仅用于文案解析学习）
- **酷库工具**: https://dy.kukutool.com/tiktok-downloader
- **MaxHelper**: https://www.maxhelper.app/zh/douyin

### 文案解析流程
1. 用浏览器技能打开下载网站，粘贴视频链接获取下载地址
2. faster-whisper提取语音转文字（生成SRT字幕+时间戳）
3. opencv检测场景切换点（分析剪辑节奏）
4. 整理文案结构（开头钩子→主体内容→结尾引导）供创作参考

## 自动化流水线设计

```
素材获取层 → 智能处理层 → 输出发布层
Pexels/Pixabay API下载    场景检测(FFmpeg/OpenCV)    多格式导出(16:9/9:16/1:1)
AI生成(可灵/即梦)         语音转文字(whisper→SRT)    字幕烧录
无水印下载→文案解析        自动剪辑(moviepy拼接)       水印/Logo叠加
                          质量监控(VMAF)              平台API发布
```

### 推荐组合
**零成本快速出片**: Pexels素材 + 可灵/即梦生成 + moviepy剪辑 + whisper字幕
**AI生成主导**: 通义万相/即梦 + ComfyUI精细控制 + n8n编排全流程

## 使用方式

用户描述视频制作需求后，根据场景选择流水线：

1. **素材获取**：确认用户需要实拍素材还是AI生成，推荐对应平台
2. **智能处理**：根据素材类型选择处理工具组合
3. **输出格式**：根据发布平台选择导出规格

## 常用命令速查

### 场景检测
```bash
ffmpeg -i input.mp4 -filter:v "select='gt(scene,0.3)',showinfo" -f null - 2>&1 | grep scene
```

### 切片
```bash
ffmpeg -i input.mp4 -ss 00:00:30 -t 00:00:15 -c copy clip_01.mp4
```

### Whisper转文字
```python
from faster_whisper import WhisperModel
model = WhisperModel('base', device='cpu')
segments, info = model.transcribe('input.mp4', language='zh')
for seg in segments:
    print(f'[{seg.start:.1f}-{seg.end:.1f}] {seg.text}')
```

### moviepy剪辑
```python
from moviepy import VideoFileClip, concatenate_videoclips, TextClip, CompositeVideoClip
clip = VideoFileClip("input.mp4").subclipped(10, 25)
final = concatenate_videoclips([clip1, clip2, clip3])
text = TextClip(text="@火火出品", font_size=36, color="white")
text = text.with_position(("right","bottom")).with_duration(final.duration)
final = CompositeVideoClip([final, text])
final.write_videofile("output.mp4", codec="libx264", fps=30)
```

## 注意事项
1. **版权红线**：CC0可商用；CC-BY必须署名；不明授权不用
2. **无水印下载仅用于学习分析**，不得搬运他人内容
3. **pip安装用清华镜像**：`-i https://pypi.tuna.tsinghua.edu.cn/simple`
4. **npm用npmmirror**：`--registry=https://registry.npmmirror.com`
5. **faster-whisper CPU模式较慢**，长视频分段处理
6. **n8n启动**：`n8n start`（端口5678）
7. Pexels/Pixabay有免费API，需注册获取key
