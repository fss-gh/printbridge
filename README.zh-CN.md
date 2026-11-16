# PrintBridge

> 面向 Web 应用的静默本地打印代理——让任意 Web 应用把 PDF 和热敏标签打印到任意本地打印机。

[English](README.md) · **中文**

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Platform](https://img.shields.io/badge/platform-macOS%20%7C%20Windows%20%7C%20Linux-blue)](#)
[![Python](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)

PrintBridge 是一个运行在系统托盘的轻量本地代理。任意 Web 应用都可以通过 HTTP 向 `localhost` 发送打印任务，PrintBridge 会静默完成打印——没有对话框，不需要用户交互。

## 功能特性

- **静默 PDF/SVG 打印** —— 不弹出对话框即可把 PDF，或自动转换为 PDF 的 SVG 打印到任意系统打印机
- **TSPL 标签打印** —— 原生 TSPL 指令，支持热敏打印机（TSC、Xprinter、Zebra 等）
- **二维码** —— 直接在 TSPL 标签中生成二维码
- **Unicode 支持** —— 自动将非 ASCII 文本（阿拉伯文、中文等）转为位图渲染
- **系统托盘图标** —— 后台运行，提供简洁的操作界面
- **开机自启** —— 系统启动时自动运行（macOS LaunchAgent / Windows 注册表）
- **跨平台** —— 支持 macOS、Windows 和 Linux
- **可配置** —— 通过 `config.json` 自定义端口、CORS 来源、标签默认值和品牌信息
- **原生 TSPL 模式** —— 发送任意 TSPL 指令，完全掌控打印内容

## 快速开始

### 从源码安装

```bash
git clone https://github.com/AnouarSbia/printbridge.git
cd printbridge
pip install -r requirements.txt
python agent.py
```

代理启动后会运行在 `http://127.0.0.1:9120`，并显示在系统托盘中。

### 验证是否运行

```bash
curl http://127.0.0.1:9120/api/status
# {"port":9120,"platform":"Darwin","status":"ok","tspl":true,"version":"1.0.0"}
```

### 下载预编译程序

预编译程序可在 [Releases](../../releases) 页面获取：

- **Windows**：`PrintBridge-Setup.exe`（安装程序）或 `PrintBridge.exe`（独立运行）
- **macOS**：`PrintBridge-Installer.dmg`

使用预编译程序不需要安装 Python。

## API 参考

所有接口均接收和返回 JSON。代理只监听 `127.0.0.1`（不对外网开放）。

### `GET /api/status`

健康检查——用于检测代理是否正在运行。

**响应：**
```json
{
  "status": "ok",
  "version": "1.0.0",
  "platform": "Darwin",
  "port": 9120,
  "tspl": true
}
```

### `GET /api/printers`

列出系统可用的打印机。

**响应：**
```json
{
  "printers": ["HP LaserJet", "Xprinter XP-350"],
  "default": "HP LaserJet"
}
```

### `POST /api/print`

静默打印 PDF 文档，或自动转换为 PDF 的 SVG 文档。

**请求：**
```json
{
  "pdf": "<base64-encoded PDF or SVG bytes>",
  "printer": "HP LaserJet",
  "copies": 1,
  "mediaWidth": 100,
  "mediaHeight": 50
}
```

| 字段 | 类型 | 必填 | 说明 |
|-------|------|----------|-------------|
| `pdf` | 字符串 | 是 | Base64 编码的 PDF 或 SVG 数据 |
| `printer` | 字符串 | 否 | 打印机名称（默认：系统默认打印机） |
| `copies` | 整数 | 否 | 打印份数（1-99，默认：1） |
| `mediaWidth` | 数字 | 否 | 标签宽度，单位 mm（用于热敏打印机） |
| `mediaHeight` | 数字 | 否 | 标签高度，单位 mm（用于热敏打印机） |

### `POST /api/print-labels`

使用 TSPL 指令打印产品标签（热敏打印机）。

**请求：**
```json
{
  "labels": [
    {
      "productName": "Widget A",
      "formuleName": "Standard",
      "width": 100,
      "height": 50,
      "position": "Shelf 3",
      "quantity": 2,
      "orderRef": "#1234",
      "clientName": "John Smith",
      "measurementId": "M001",
      "sig": "abc123"
    }
  ],
  "printer": "Xprinter XP-350",
  "labelWidth": 100,
  "labelHeight": 60,
  "shopName": "My Shop",
  "workOrderId": 42,
  "qrBaseUrl": "https://example.com/label/",
  "copies": 1,
  "displayOptions": {
    "showBarcode": false,
    "showFormule": true,
    "showClient": true,
    "showOrder": true,
    "showQr": true,
    "showPosition": true,
    "showShopHeader": true,
    "fontScale": 2
  }
}
```

### `POST /api/print-cut-labels`

使用 TSPL 打印紧凑型切割/生产标签。

**请求：**
```json
{
  "labels": [
    {
      "position": "Room 1",
      "barInfo": "Bar 1 — Cut 3",
      "profileName": "H",
      "profileRef": "2RF21",
      "cutName": "H",
      "finishing": "RAL 7024",
      "length": 1200,
      "angles": "45/45",
      "binNumber": 3,
      "source": "production"
    }
  ],
  "printer": "Xprinter XP-350",
  "labelWidth": 45,
  "labelHeight": 35,
  "orderRef": "1245",
  "copies": 1
}
```

### `POST /api/print-tspl`

直接将原始 TSPL 指令发送到打印机。可用于完全自定义标签格式。

**请求：**
```json
{
  "tspl": "SIZE 100 mm, 60 mm\r\nGAP 2 mm, 0 mm\r\nDIRECTION 0\r\nCLS\r\nTEXT 10,10,\"4\",0,1,1,\"Hello World\"\r\nQRCODE 400,10,M,6,A,0,\"https://example.com\"\r\nPRINT 1,1\r\n",
  "printer": "Xprinter XP-350"
}
```

也可以把 TSPL 作为字符串数组传入：

```json
{
  "tspl": [
    "SIZE 100 mm, 60 mm",
    "GAP 2 mm, 0 mm",
    "DIRECTION 0",
    "CLS",
    "TEXT 10,10,\"4\",0,1,1,\"Hello World\"",
    "PRINT 1,1"
  ],
  "printer": null
}
```

### `POST /api/test-tspl`

发送一个简单测试标签，用于验证打印机连接是否正常。

**请求：**
```json
{
  "printer": "Xprinter XP-350",
  "labelWidth": 100,
  "labelHeight": 150
}
```

## 配置

编辑与 `agent.py` 同目录的 `config.json`：

```json
{
  "port": 9120,
  "cors_origins": [
    "http://localhost:*",
    "http://127.0.0.1:*",
    "https://your-app.com"
  ],
  "log_dir": "~/.printbridge",
  "label_defaults": {
    "width_mm": 100,
    "height_mm": 150,
    "dpmm": 8,
    "gap_mm": 2
  },
  "footer_text": "PrintBridge",
  "tray_name": "PrintBridge",
  "language": "zh"
}
```

### 环境变量

| 变量 | 默认值 | 说明 |
|----------|---------|-------------|
| `PRINTBRIDGE_PORT` | `9120` | 覆盖端口 |
| `PRINTBRIDGE_FOOTER` | `PrintBridge` | 覆盖标签底部文字 |
| `PRINTBRIDGE_TRAY_NAME` | `PrintBridge` | 覆盖托盘图标名称 |
| `PRINTBRIDGE_LANGUAGE` | `zh` | 覆盖界面语言（`zh` 或 `en`） |

### CORS

默认情况下，PrintBridge 只接受来自 `localhost` 的请求。若要让你的 Web 应用连接，请在 `config.json` 的 `cors_origins` 中添加你的域名：

```json
{
  "cors_origins": [
    "http://localhost:*",
    "https://my-app.example.com",
    "https://*.my-app.example.com"
  ]
}
```

## 从源码构建

### 环境要求

- Python 3.10+（Windows 下使用 `svg2pdf-py` 打印 SVG 需要 Python 3.11+）
- `pip install -r requirements.txt`

### Windows

```cmd
build_windows.bat
```

构建产物：
- `dist\PrintBridge.exe` —— 独立可执行文件
- `PrintBridge-Setup.exe` —— NSIS 安装程序（如果安装了 NSIS）

#### 内置 SumatraPDF.exe（推荐）

Windows 静默 PDF 打印使用 SumatraPDF。为了让构建出的 `.exe` 完全自包含，可以把 SumatraPDF 一起打包，这样目标机器无需安装 SumatraPDF：

1. 从 [SumatraPDF 下载页](https://www.sumatrapdfreader.org/download-free-pdf-viewer) 下载官方便携版/独立版 `SumatraPDF.exe`。
2. 将 `SumatraPDF.exe` 复制到项目根目录，即与 `build_windows.bat`、`PrintBridge.spec` 相同的目录。
3. 重新运行 `build_windows.bat`。

`build_windows.bat` 会自动检测 `SumatraPDF.exe`，并通过 `--add-data "SumatraPDF.exe;."` 传给 PyInstaller。如果文件不存在，构建仍会成功，PrintBridge 会在运行时自动查找系统已安装的 SumatraPDF。

`build_windows.bat` 也会自动打包 `fonts/` 目录（`--add-data "fonts;fonts"`），因此 SVG 转 PDF 使用的字体会被内置到可执行文件中。

> **注意：** SumatraPDF 采用 GPLv3 协议分发。如果重新分发构建出的可执行文件，请确保遵守 GPLv3 许可条款（例如提供对应的源码/许可证信息）。

### macOS

```bash
./build_macos.sh
```

构建产物：
- `dist/PrintBridge.app` —— macOS 应用
- `dist/PrintBridge-Installer.dmg` —— DMG 安装程序（如果安装了 `create-dmg`）

## 工作原理

```
┌──────────────┐     HTTP/JSON      ┌───────────────┐     OS print      ┌────────────┐
│  Your Web App │ ──────────────────▶│  PrintBridge   │ ────────────────▶│  Printer    │
│  (any domain) │  localhost:9120   │  (system tray) │  lp / win32print  │  (any type) │
└──────────────┘                    └───────────────┘                   └────────────┘
```

1. 你的 Web 应用向 `http://127.0.0.1:9120/api/print`（或 `/api/print-labels`、`/api/print-tspl`）发送 POST 请求
2. PrintBridge 解码数据并发送到指定打印机
3. 文档静默打印——没有对话框，不需要用户交互

### PDF 打印

- **macOS/Linux**：使用 `lp` 命令，可附带热敏打印机的介质尺寸
- **Windows**：优先使用打包内置的 `SumatraPDF.exe`（否则自动检测已安装的 SumatraPDF），再回退到 PowerShell `Start-Process -Verb PrintTo`，最后是 `ShellExecute`
- **SVG**：SVG 数据使用 `svg2pdf-py` 转换为 PDF，并加载 `fonts/` 目录中内置的字体（中文使用 Alibaba PuHuiTi 3.0，西文使用 Alibaba Sans，同时保留系统字体作为兜底），因此中文（及其他 Unicode 文本）可以正确渲染

### TSPL 标签打印

- **macOS/Linux**：使用 `lpr -o raw` 发送原始字节
- **Windows**：使用 `win32print.WritePrinter` 以 `RAW` 数据类型发送

## 与 Web 应用集成

### JavaScript 示例

```javascript
// 检查 PrintBridge 是否运行
async function checkAgent() {
  try {
    const res = await fetch('http://127.0.0.1:9120/api/status');
    return res.ok;
  } catch {
    return false;
  }
}

// 打印 PDF
async function printPdf(pdfBase64, printerName) {
  const res = await fetch('http://127.0.0.1:9120/api/print', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      pdf: pdfBase64,
      printer: printerName,
      copies: 1,
    }),
  });
  return res.json();
}

// 打印自定义 TSPL 标签
async function printLabel(tsplCommands, printerName) {
  const res = await fetch('http://127.0.0.1:9120/api/print-tspl', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      tspl: tsplCommands,
      printer: printerName,
    }),
  });
  return res.json();
}
```

## 常见问题排查

| 问题 | 解决方法 |
|---------|----------|
| 代理无法启动 | 查看日志：`~/.printbridge/agent.log` |
| 检测不到打印机 | 确认打印机已在系统设置中安装 |
| 标签为空白 | 检查标签尺寸是否与介质一致 |
| 端口 9120 被占用 | 修改 `config.json` 中的端口，或设置 `PRINTBRIDGE_PORT` 环境变量 |
| CORS 错误 | 在 `config.json` 的 `cors_origins` 中添加你的域名 |
| Windows 下 PDF 无法打印 | 确保已内置 `SumatraPDF.exe`（放到项目根目录后重新构建），或在目标机器上安装 [SumatraPDF](https://www.sumatrapdfreader.org/) |
| 阿拉伯文无法渲染 | 安装 `arabic-reshaper` 和 `python-bidi`（已包含在 requirements.txt） |

## 参与贡献

欢迎提交贡献！请阅读 [CONTRIBUTING.md](CONTRIBUTING.md) 了解规范。

我们希望能得到帮助的领域：
- 新的打印机协议（ZPL、EPL、CPCL）
- 标签模板系统（基于 JSON 或可视化编辑器）
- 配置用的 Web UI
- Linux 打包（deb、rpm、AppImage）
- 单元测试和集成测试

## 许可证

本项目使用 MIT 许可证——详见 [LICENSE](LICENSE)。

## 致谢

- [Flask](https://flask.palletsprojects.com/) —— Web 框架
- [pystray](https://github.com/moses-palmer/pystray) —— 系统托盘图标
- [Pillow](https://python-pillow.org/) —— 位图文字渲染的图像处理
- [pywin32](https://github.com/mhammond/pywin32) —— Windows 打印机访问
- [SumatraPDF](https://www.sumatrapdfreader.org/) —— Windows 静默 PDF 打印
