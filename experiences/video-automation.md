# 视频自动化剪辑工作链

> 来源：项目文件 /shared/video_automation_toolkit.md（科技扣子创建 2026-07-26）
> 项目路径：7665755754497933608

## 本地工具链（云电脑已就绪）

| 工具 | 版本 | 用途 |
|------|------|------|
| FFmpeg | 4.4.2 | 编码/转码/切片/场景检测 |
| moviepy | 2.1.2 | Python视频编辑(剪切/拼接/特效/字幕) |
| faster-whisper | 1.2.1 | 语音转文字(CTranslate2,不依赖torch) |
| opencv-headless | 5.0.0.93 | 场景检测/帧分析/图像处理 |
| n8n | 2.31.6 | 工作流编排(端口5678) |

## 常用命令速查

### FFmpeg
```bash
# 转码
ffmpeg -i input.mp4 -c:v libx264 -crf 23 -preset fast -c:a aac output.mp4
# 场景检测
ffmpeg -i input.mp4 -filter:v "select='gt(scene,0.3)',showinfo" -f null - 2>&1 | grep scene
# 截取片段
ffmpeg -i input.mp4 -ss 00:00:30 -t 00:00:15 -c copy clip_01.mp4
# 缩略图
ffmpeg -i input.mp4 -vf "fps=1/10" -frame:v 1 thumb_%03d.jpg
```

### Whisper转文字
```python
from faster_whisper import WhisperModel
model = WhisperModel('base', device='cpu')
segments, info = model.transcribe('input.mp4', language='zh')
for seg in segments: print(f'[{seg.start:.1f}-{seg.end:.1f}] {seg.text}')
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

## 免费CC0素材库
- 国际优先：Pexels(50万+4K)、Pixabay(20万+CC0)、Mixkit(4K+模板+音效)、Coverr(电影级)、Videvo(50万+绿幕)、Dareful(专注4K)
- 国内：光厂CC0(中国元素8K)、潮点视频(每日免费1次)、新CG儿(AE模板+免费视频)
- 搜索技巧：英文搜索结果更多，用情绪词搜索

## AI视频生成（含免费额度）
- 可灵(免费测试中)、即梦AI(每日60积分)、通义万相(每日50灵感值)、智谱清影(免费受限)、PixVerse(有免费额度)、Adobe Firefly(商用安全)
- AI画布：ComfyUI(开源节点)、PixVerse Canvas、Wireflow(50+模型链式)、n8n(本地已装)

## 推荐组合
- 零成本：Pexels素材 + 可灵/即梦生成 + moviepy剪辑 + whisper字幕
- AI主导：通义万相/即梦 + ComfyUI精细控制 + n8n编排全流程

## 无水印下载（仅用于文案解析学习）
- 酷库工具: https://dy.kukutool.com/tiktok-downloader
- MaxHelper: https://www.maxhelper.app/zh/douyin
- 流程：浏览器打开下载站 → 粘贴链接 → whisper提取文案 → opencv检测场景 → 整理结构

## 自动化流水线设计
1. 素材获取层：Pexels/Pixabay API + AI生成 + 无水印下载解析
2. 智能处理层：场景检测(FFmpeg/OpenCV) + 语音转文字(whisper) + 自动剪辑(moviepy) + 质量监控(VMAF)
3. 输出发布层：多格式导出(16:9/9:16/1:1) + 字幕烧录 + 水印叠加 + 平台API发布

## 注意事项
1. CC0可商用；CC-BY必须署名；不明授权不用
2. 无水印下载仅用于学习分析，不得搬运
3. pip用清华镜像，npm用npmmirror
4. faster-whisper CPU模式较慢，长视频分段处理
5. n8n启动: n8n start(端口5678)
6. Pexels/Pixabay有免费API，需注册获取key

---

> 本内容由 Coze AI 生成，请遵循相关法律法规及《人工智能生成合成内容标识办法》使用与传播。
