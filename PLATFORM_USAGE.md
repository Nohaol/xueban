# 小智伴学家长工作台使用说明

## 1. 平台现在是什么

当前项目已经不是微信小程序项目，而是一个电脑端家长工作台。

整体链路：

```text
废旧安卓手机
  运行 IP Webcam，只作为网络摄像头
        ↓
电脑端 FastAPI 后端
  拉取手机视频流，运行专注度分析
        ↓
浏览器家长工作台
  查看画面、专注度、事件、视频源、提醒按钮
        ↓
后续接入小智 MCP
  检测到不专注时让小智语音或动作提醒
```

## 2. 每次使用前准备

### 2.1 手机端

1. 打开安卓手机上的 IP Webcam。
2. 点击启动服务器。
3. 保持手机屏幕上的摄像头服务运行，不要退出应用。
4. 记下手机显示的地址，例如：

```text
http://192.168.137.71:8080
```

电脑浏览器先测试：

```text
http://192.168.137.71:8080/video
```

如果能看到实时画面，说明手机网络摄像头已经正常。

备用截图地址：

```text
http://192.168.137.71:8080/shot.jpg
```

## 3. 启动电脑端后端

在项目根目录打开 PowerShell：

```powershell
cd C:\Users\20245\WeChatProjects\miniprogram-1
```

启动后端：

```powershell
py -3.12 -m uvicorn backend.main:app --host 0.0.0.0 --port 8000
```

看到类似下面的信息，说明启动成功：

```text
Uvicorn running on http://0.0.0.0:8000
```

不要关闭这个 PowerShell 窗口。关闭后，家长工作台也会停止。

## 4. 打开家长工作台

电脑浏览器打开：

```text
http://127.0.0.1:8000/
```

如果打不开，先检查后端是否启动。

也可以测试健康接口：

```text
http://127.0.0.1:8000/health
```

正常会返回类似：

```json
{"ok": true, "status": "normal", "studentLabel": "学生 A"}
```

## 5. 添加手机摄像头视频源

在家长工作台页面找到“视频源”区域。

填写：

```text
名称：IP Webcam 手机摄像头
地址：http://192.168.137.71:8080/video
类型：连续视频流
```

点击：

```text
添加视频源
```

添加后系统会自动切换到该视频源。

如果连续视频流不稳定，可以改用截图地址：

```text
地址：http://192.168.137.71:8080/shot.jpg
类型：截图地址
```

## 6. 视频源管理

视频源列表里：

- “切换”：切换到该摄像头源。
- “已选中”：当前正在使用的视频源。
- “删除”：删除用户添加的视频源。

注意：

- 本机摄像头是系统内置兜底源，不能删除。
- 重复添加同一个 IP Webcam 地址时，系统会复用已有源，不会再堆出多条重复项。

## 7. 页面怎么看

### 7.1 综合专注度

页面上方的大数字是综合专注度，范围 0-100。

常见状态：

```text
心流专注
稳定学习
轻度分心
短暂离座
超时离座
```

### 7.2 主视窗

主视窗显示的是电脑后端处理后的视频画面。

它不是直接显示手机原始网页，而是：

```text
手机视频流 → 电脑 OpenCV 读取 → 专注度分析 → 输出预览画面
```

### 7.3 视觉指标

右侧视觉指标包括：

```text
视线聚焦
坐姿健康
身体稳定
在座覆盖
```

这些指标会共同影响综合专注度。

### 7.4 事件时间线

事件时间线会记录状态变化，例如：

```text
已在当前学习区域内检测并跟踪到人脸。
没有检测到人脸，当前座位视为无人。
人脸位置显示坐姿可能前倾或偏离。
人脸明显偏离学习区域中心，可能出现分心。
```

### 7.5 AI 决策建议

当前页面已有 AI 决策建议区域。

现阶段主要是本地规则建议。DeepSeek API 已经验证可用，后续可以把实时状态发送给 DeepSeek，让它生成提醒建议和话术。

## 8. 提醒控制

右侧“提醒控制”区域包含：

```text
语音对话
姿态提醒
休息提醒
刷新视频
家长留言
```

目前这些按钮会发送到电脑端后端 `/control`。

后续接入小智 MCP 后，链路会变成：

```text
家长工作台按钮
        ↓
电脑端后端
        ↓
小智 MCP Bridge
        ↓
小智机器人执行提醒
```

家长留言示例：

```text
宝贝，我们把注意力放回书本上，再坚持十分钟。
```

## 9. DeepSeek 配置

根目录有 `.env` 文件。

关键配置：

```env
DEEPSEEK_API_KEY=你的 API Key
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_MODEL=deepseek-v4-flash
DEEPSEEK_REASONING_MODEL=deepseek-v4-pro
```

已验证过 `deepseek-v4-flash` 可以正常调用。

测试命令：

```powershell
py -3.12 -c "import json, urllib.request; env={}; [env.update([line.strip().split('=',1)]) for line in open('.env', encoding='utf-8') if line.strip() and not line.startswith('#') and '=' in line]; payload={'model':env.get('DEEPSEEK_MODEL','deepseek-v4-flash'),'messages':[{'role':'user','content':'请只回复：DeepSeek API 连接成功'}],'stream':False}; req=urllib.request.Request(env.get('DEEPSEEK_BASE_URL','https://api.deepseek.com').rstrip('/')+'/chat/completions', data=json.dumps(payload).encode('utf-8'), headers={'Content-Type':'application/json','Authorization':'Bearer '+env['DEEPSEEK_API_KEY']}, method='POST'); print(json.loads(urllib.request.urlopen(req, timeout=30).read().decode('utf-8'))['choices'][0]['message']['content'])"
```

正常输出：

```text
DeepSeek API 连接成功
```

## 10. 日常启动流程

最短流程：

```text
1. 手机打开 IP Webcam，启动服务器
2. 电脑确认能打开 http://手机IP:8080/video
3. PowerShell 进入项目根目录
4. 运行 py -3.12 -m uvicorn backend.main:app --host 0.0.0.0 --port 8000
5. 浏览器打开 http://127.0.0.1:8000/
6. 添加或切换手机摄像头视频源
7. 查看专注度与事件时间线
```

## 11. 常见问题

### 11.1 浏览器提示 127.0.0.1 拒绝连接

说明后端没有启动。

重新运行：

```powershell
py -3.12 -m uvicorn backend.main:app --host 0.0.0.0 --port 8000
```

### 11.2 手机视频网页能打开，但家长工作台没画面

尝试：

```text
1. 点击“刷新视频”
2. 删除旧视频源，重新添加 /video 地址
3. 改用 /shot.jpg 截图地址
4. 确认手机和电脑在同一局域网
```

### 11.3 手机 IP 变了

IP Webcam 每次启动可能显示不同 IP。

如果手机地址变成：

```text
http://192.168.137.88:8080
```

视频源也要改成：

```text
http://192.168.137.88:8080/video
```

### 11.4 页面事件还在快速变化

这是视觉检测正在实时读取帧。后续自动提醒不能直接按单帧触发，必须加入连续时长和冷却时间。

建议后续规则：

```text
连续分心 >= 10 秒才提醒
连续离座 >= 5 秒才提醒
同类提醒冷却 >= 60 秒
每 10 分钟最多自动提醒 3 次
```

### 11.5 画面有点卡顿

常见原因：

```text
1. 后端分析帧率太低
2. 手机 IP Webcam 输出分辨率太高
3. 手机和电脑之间 Wi-Fi 不稳定
4. 浏览器正在显示的是“分析后画面”，不是手机原始视频流
```

当前后端默认帧率已经设置为：

```text
FOCUS_ANALYSIS_FPS=10
```

如果还卡，可以在启动后端前临时设置：

```powershell
$env:FOCUS_ANALYSIS_FPS='12'
py -3.12 -m uvicorn backend.main:app --host 0.0.0.0 --port 8000
```

不建议一开始拉到太高，因为专注度分析也要占用 CPU。

手机 IP Webcam 推荐设置：

```text
分辨率：640x480 或 1280x720
帧率：10-15 fps
视频质量：中等
音频：关闭
```

如果只是为了专注度识别，优先保证稳定，不要追求高清。

## 12. 后续开发入口

当前核心文件：

```text
backend/main.py
backend/engine.py
backend/schemas.py
backend/static/parent-console.html
backend/static/parent-console.css
backend/static/parent-console.js
```

后续建议新增：

```text
backend/deepseek_client.py
backend/reminder_policy.py
backend/xiaozhi_bridge.py
```

对应功能：

```text
DeepSeek 决策建议
自动提醒策略
小智 MCP 调用
```
