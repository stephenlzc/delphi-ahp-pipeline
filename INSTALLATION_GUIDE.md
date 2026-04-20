# 安装指南

本工具支持 **macOS**（苹果电脑）和 **Windows** 操作系统。

---

## 第一步：下载项目

打开 GitHub 页面，点击右上角 **Code** → **Download ZIP**，将文件解压到你喜欢的位置（记住这个文件夹路径）。

或者直接点击下载：
[Download Delphi-AHP Pipeline](https://github.com/stephenlzc/delphi-ahp-pipeline/archive/refs/heads/main.zip)

---

## 第二步：安装（自动完成）

### macOS / Linux

1. 打开**终端**（Terminal）：
   - 按 `Command + 空格`，搜索"终端"，回车打开

2. 输入以下命令（注意空格）：
   ```bash
   cd 拖入项目文件夹路径
   ```
   然后按回车。

3. 粘贴以下命令，按回车：
   ```bash
   curl -fsSL https://raw.githubusercontent.com/stephenlzc/DelphiAHPFlow/main/install.sh | bash
   ```

4. 等待出现"Installation Complete"即安装成功。

### Windows

1. 打开 **PowerShell**：
   - 按 `Win + X`，选择"Windows PowerShell"

2. 输入以下命令：
   ```powershell
   cd 拖入项目文件夹路径
   ```
   然后按回车。

3. 粘贴以下命令，按回车：
   ```powershell
   irm https://raw.githubusercontent.com/stephenlzc/DelphiAHPFlow/main/install.ps1 | iex
   ```

4. 等待出现"Installation Complete"即安装成功。

---

## 第三步：启动程序

### macOS / Linux

终端输入：
```bash
bash run.sh
```

### Windows

直接双击文件夹中的 `run.bat` 文件即可。

---

## 常见问题

### Q: 提示"无法运行脚本"？
**Windows**：在 PowerShell 中先运行：
```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```
然后再运行安装命令。

**macOS**：在终端运行：
```bash
chmod +x install.sh run.sh
```

### Q: 提示"找不到 Python"？
安装脚本会自动帮你安装 Python。如果安装失败，请手动下载：
[https://www.python.org/downloads/](https://www.python.org/downloads/)

### Q: 每次都要手动运行命令吗？
不需要。安装完成后，只需双击 `run.bat`（Windows）或运行 `bash run.sh`（macOS）即可启动。

### Q: Xi-API 是什么？
Xi-API 是一个聚合了多个 LLM（大型语言模型）的平台。使用它无需在各个AI官网分别注册，只需一个 API Key 即可调用 DeepSeek、Moonshot、Qwen 等多种模型。

注册地址：[点击注册 Xi-API](https://api.xi-ai.cn/register?aff_code=GXZx)

---

## 手动安装（可选）

如果你熟悉 Python，也可以手动安装：

```bash
# 创建虚拟环境
python3 -m venv .venv

# 安装依赖
source .venv/bin/activate    # macOS/Linux
pip install -r requirements.txt
```

然后运行：
```bash
python3 app.py    # macOS/Linux
python app.py     # Windows
```
