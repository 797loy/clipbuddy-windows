<p align="center">
  <img src="docs/img/banner.png" alt="剪贴宝 ClipBuddy" width="820">
</p>

<div align="center">

# 📋 剪贴宝 ClipBuddy

**Windows 剪贴板历史工具 —— 后台常驻，快捷键呼出毛玻璃面板，点一下就直接粘贴到光标处。**

连续粘贴填充不中断，窗口始终停留在桌面。

[![Platform](https://img.shields.io/badge/platform-Windows%2010%2F11-blue)](https://github.com/797loy/clipbuddy-windows)
[![Python](https://img.shields.io/badge/Python-3.9%E2%80%933.13-3776AB?logo=python&logoColor=white)](https://www.python.org)
[![UI](https://img.shields.io/badge/UI-pywebview%20%2B%20WebView2-6f4dff)](https://pywebview.flowrl.com)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

</div>

---

## ✨ 功能特色

- **自动记录**：复制过的文字自动入历史，相同内容去重，默认保留 20 条（可设 10 / 20 / 50 / 100），重启不丢。
- **点击即粘贴**：点卡片（或 `↑↓ + Enter`、`Ctrl+1…9`），内容自动粘贴到你复制前所在窗口的光标处。
- **🔁 连续粘贴填充**：粘贴后**面板不隐藏**，窗口始终停在桌面——在表格、表单里连续点击即可逐条填充，不用反复呼出。
- **常用语**：跨会话保留，可在面板里直接新建，右键卡片即可加入 / 移出。
- **智能识别**：自动标注类型标签 —— 链接 / 邮箱 / 手机号 / 数字 / 代码 / 文本。
- **快速搜索**：按关键词过滤历史与常用语。
- **清空可撤销**：清空历史后 5 秒内可一键「撤销」。
- **深浅主题**：浅色 / 深色 / 跟随系统，就地切换不刷新。
- **宠物图标**：猫、狗、熊、兔、狐、熊猫、混合、无图标。
- **贴心细节**：面板出现在鼠标附近（或屏幕居中），点外部自动收起；系统托盘图标、单实例（重复启动会唤起已运行的面板）。
- **隐私友好**：密码管理器等标记为「不要记录」的复制内容会被自动忽略。

## 🖼️ 界面预览

| 浅色主题 | 深色主题 |
| :---: | :---: |
| <img src="docs/img/panel-light.png" alt="浅色" width="230"> | <img src="docs/img/panel-dark.png" alt="深色" width="230"> |

## 🚀 安装

> 需要 **Windows 10 / 11** 和 **Python 3.9 – 3.13**（Win10/11 已自带 WebView2 运行时）。

### 方法一：一键安装（推荐）

双击运行 `install.bat`：

```bat
install.bat
```

它会自动完成：**安装依赖 → 创建桌面快捷方式 → 设置开机自启**。完成后双击桌面「剪贴宝」即可使用。

### 方法二：手动安装

```bat
pip install -r requirements.txt
pythonw app.py            :: 无控制台启动
pythonw app.py --silent   :: 启动后不弹面板（开机自启用）
```

或使用 `run.bat` 一键启动：

```bat
run.bat
```

### 打包成 exe（可选）

```bat
build_exe.bat
```

产物在 `dist\ClipBuddy\ClipBuddy.exe`。

### 卸载

运行 `uninstall.bat`。历史数据在 `%APPDATA%\ClipBuddy`，不想保留就删掉该文件夹。

## 🎹 快捷键

| 快捷键 | 作用 |
| --- | --- |
| `Ctrl+Shift+V` / `F8` | 呼出 / 隐藏面板（全局，后台常驻也生效） |
| `Ctrl+Shift+C` | 清空全部历史（全局） |
| `↑` `↓` / `Enter` | 选择 / 粘贴 |
| `Ctrl+1…9` | 快速粘贴第 N 条 |
| `Tab` | 切换剪贴板 / 常用语 |
| `Esc` | 关闭菜单 → 清除搜索 → 关闭面板 |

> 💡 `Ctrl+Shift+C` 在 Chrome / Edge 里是「检查元素」，被本工具占用后会失效。
> 可修改 `%APPDATA%\ClipBuddy\config.json` 换键（先退出程序再改）：
> ```json
> { "hotkeys": { "toggle": ["ctrl+shift+v", "f8"], "clear": ["ctrl+alt+x"] } }
> ```

## 🤖 AI 安装话术

> 以下是一段可直接使用的安装引导话术，AI 助手或客服向用户介绍剪贴宝时，照着念即可。

**开场：**
> 「给你推荐一个 Windows 上超好用的剪贴板工具——**剪贴宝 ClipBuddy**。它常驻在后台，你复制过的文字它都会自动记下来，需要的时候一键呼出，点一下就粘贴到光标处，特别适合填表格、填表单、连续粘贴的场景。」

**安装引导（一步一步）：**
> 「安装很简单，分两步：
> 第一步，确保电脑装了 Python（3.9 到 3.13 版本都可以）。没装的话去 python.org 下载安装，安装时记得勾选『Add to PATH』。
> 第二步，进入剪贴宝文件夹，双击运行 `install.bat`。它会自动帮你装好依赖、在桌面创建快捷方式、并设置开机自启。等它跑完，双击桌面的『剪贴宝』图标就能用了。」
>
> 「如果你习惯手动来，也可以打开命令行输入：
> ```
> pip install -r requirements.txt
> pythonw app.py
> ```
> 同样能跑起来。」

**使用演示：**
> 「装好后按 `Ctrl+Shift+V` 或 `F8` 就能呼出面板。它最厉害的地方是**连续粘贴**：点一条内容，它粘贴到目标窗口后，面板不会消失，你可以接着点下一条，一口气把一整张表、一个表单填完，不用反反复复地开关窗口。」

**收尾：**
> 「全程不需要管理员权限，免费开源，MIT 协议。有手机号、邮箱、代码、链接这些内容，它还会自动帮你分好类、标好标签，找起来特别快。快去试试吧！」

## ⚙️ 工作原理

- **界面**：pywebview + WebView2，HTML / CSS / JS（`ui/`）。毛玻璃靠 `backdrop-filter` + 背景色块实现；窗口本身**不使用透明窗口**（部分显卡驱动会渲染成空窗），圆角由系统实现（Win11 用 DWM，Win10 用窗口区域）。
- **剪贴板 / 热键 / 模拟按键**：全部用 `ctypes` 调 Windows 原生 API（`GetClipboardSequenceNumber`、`RegisterHotKey`、`SendInput`），**不依赖 keyboard 库，不需要管理员权限**。
- **粘贴流程**：写入剪贴板 → **面板保持显示**，临时把焦点交给目标窗口 → 确认焦点已回 → `SendInput` 发 `Ctrl+V` → 把面板拉回前台，实现连续粘贴。

## 📁 目录结构

```
app.py              入口：控制器、剪贴板监听、托盘、窗口
core/winapi.py      Windows API 封装（剪贴板 / 热键 / SendInput / 窗口）
core/store.py       历史、常用语、设置的持久化
core/autostart.py   开机自启（HKCU\...\Run，pythonw 启动）
core/icon.py        Pillow 绘制图标
ui/                 index.html / style.css / app.js
scripts/setup.py    创建桌面快捷方式、设置自启
docs/img/           项目介绍演示图
install.bat  uninstall.bat  run.bat  build_exe.bat
```

数据位置：`%APPDATA%\ClipBuddy\`（`data.json` 数据、`config.json` 热键配置、`clipbuddy.log` 日志）。

UI 调试：直接用浏览器打开 `ui/index.html` 会进入带演示数据的预览模式。

## ❓ 常见问题

- **粘贴没反应**：目标程序若以管理员身份运行，普通权限的本工具无法向它发送按键（Windows UIPI 限制）。此时内容仍已写入剪贴板，手动 `Ctrl+V` 即可。
- **快捷键无效**：可能被其他软件占用。查看 `clipbuddy.log` 里的「热键注册失败」，在 `config.json` 里换一个。
- **看不到面板**：看任务栏托盘图标，右键可打开 / 退出；或再次双击桌面快捷方式。
- **只记录文字**：图片、文件等暂不记录。

## 📄 License

[MIT](LICENSE)
