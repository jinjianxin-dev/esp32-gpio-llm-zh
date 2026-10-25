# esp32-gpio-llm 本机部署报告

**日期**：2026-10-16
**项目路径**：`C:\Users\aaron\WorkBuddy\2026-10-15-18-26-44\esp32-gpio-llm`
**目标**：在一台 Windows 电脑上从零跑通完整训练流水线（造语料 → 训分词器 → 训模型 → 评估 → 导出 → 校验）

---

## 一、结论速览

| 项目 | 结果 |
|---|---|
| 训练语料 | 150,000 条（训练 147,000 / 验证 3,000） |
| 分词器 | 词表 1024，749 条 BPE 合并规则，19 个保留符号 |
| 模型规模 | **312,128 参数**（246,592 主体 + 65,536 共享词嵌入） |
| 训练耗时 | **6,269 秒（约 1 小时 45 分）**，纯 CPU |
| 最终符号准确率 | **99.50%**，验证损失 0.0203 |
| 导出的设备文件 | `model.bin` **1219 KB**，44 个张量 |
| 三道主机校验 | **全部通过** |

### 四项核心指标（在我们自己生成的验证集上，n=1500）

| 指标 | 本次训练 | 作者文档中发布版 |
|---|---|---|
| exact-match（域内精确匹配） | **96.44%** | 84.4% |
| false-accept（域外误接受） | **0.92%** | 13.3% |
| pin copy（引脚复制） | **99.28%** | 91.3% |
| substitution（替换错误，最危险） | **0.52%** | 1.8% |
| 动错引脚率 | 1.03% | 4.5% |

> ⚠️ **这两列不可直接比较**。作者的数字是在「人类手写、作者从未公开」的留出集上测的；我们跑的是程序自己生成的验证集，题目同源、难度更低。作者文档里的数字更有说服力。

---

## 二、环境

| 组件 | 版本 | 说明 |
|---|---|---|
| git | 2.55.0 | 已有 |
| Python | 3.12（uv 管理） | 已通过 `.python-version` 自动选用 |
| uv | 0.12.23 | 已有，负责建隔离虚拟环境 |
| torch | 2.14.1（CPU 版） | 由 `uv sync` 安装 |
| tokenizers / numpy | 0.23.3 / 2.5.4 | 同上 |
| GCC | 16.2.0 | 本机原本没有，**新装**（w64devkit 免安装版） |

新装的 GCC 在 `tools\w64devkit\`，**没有动你的系统环境变量**，只在需要时临时加入 PATH。

---

## 三、执行步骤与实测输出

### 1. 克隆并安装依赖
```sh
git clone https://github.com/manjunathshiva/esp32-gpio-llm.git
cd esp32-gpio-llm && uv sync
```
→ 79 秒装完，含 torch 2.14.1。

### 2. 生成语料
```sh
uv run python data/build_corpus.py --n 150000 --out data/corpus
```
→ `150,000 rows (train 147,000 / val 3,000)`

按动作分布：unknown 30.0%、set 24.3%、blink 15.2%、seq 9.5%、read 9.0%、stop 6.4%、alias 5.6%
按来源分布：模板 70.0%、合成负例 10.2%、MASSIVE 远域 7.8%、MASSIVE 近域 6.9%、截断负例 5.1%

### 3. 训分词器 + 编码
```sh
uv run python data/prepare.py --seq-len 96 --vocab 1024
```
→ 词表 1024；train 保留 146,900 条（**丢弃 100 条**，因为最长 162 超过 seq_len 96）；val 保留 2,998 条

### 4. 训练
```sh
uv run python src/train.py --steps 6000 --tag v1
```
→ 关键节点：

```
step      0  train 6.8944  val 6.8873  symbol-acc 0.0302    19s
step   1000  train 0.4604  val 0.3749  symbol-acc 0.9046  1116s
step   3000  train 0.1086  val 0.0661  symbol-acc 0.9841  3261s
step   5999  train 0.0302  val 0.0203  symbol-acc 0.9950  6269s
```
产物：`runs/cmd-v1-s0.pt`

### 5. 评估
```sh
uv run python src/evaluate.py --run runs/cmd-v1-s0.pt --split val --limit 1500
```
完整报告已存到 `build/eval_report.txt`。

### 6. 导出 + 生成设备头文件
```sh
uv run python src/export.py v1-s0     # firmware/model/model.bin + golden.txt
uv run python src/gen_assets.py       # firmware/generated/{bpe.h, symbols.h}
```
→ `model.bin 1219 KB, 44 tensors`；`golden.txt` 的固定 prompt 是 `blink pin 38 every 300ms`，模型预测首位为 `<blink>`（正确）

### 7. 三道主机校验

| 门禁 | 内容 | 结果 |
|---|---|---|
| 1 | C 前向传播 vs PyTorch | **通过**，最大绝对误差 3.815e-06 |
| 2 | 设备端分词器 vs 训练分词器 | **通过**，3000/3000 行一致 |
| 3 | 整链（含采样循环、停止规则、prompt 截断）vs PyTorch | **通过**，500/500 条一致 |

---

## 四、过程中遇到并修复的问题

### 1. 上游 HuggingFace 数据集改了结构（已修）
`data/massive.py` 原本调用 `load_dataset("mteb/amazon_massive_intent", "en", ...)`，
但这个数据集现在**只有 `default` 一个配置**，把全部 51 种语言装在一起、用 `lang` 列区分，
不再是「一种语言一个配置」。这导致语料生成直接报错中断。

**修复**：在 `_rows()` 里加了回退——先按 `"en"` 取，失败则取默认配置并按 `lang == "en"` 过滤。
只改了 8 行，没有动任何筛选/去重逻辑。

### 2. Windows 下 `/tmp` 路径解析不一致（已绕过）
作者的校验脚本把二进制路径写死成 `/tmp/tok_test`、`/tmp/repl`。
在 Windows 上 Python 会把它解析成「当前盘符根目录」，且可执行文件带 `.exe` 后缀，
所以既过不了 `os.path.exists` 检查、也调不起来。

**修复**：新增 `build/run_gate_win.py` 薄封装，复用仓库原有的测试用例和比较逻辑，
只把二进制路径指向本地编译出来的 `.exe`。**没有修改仓库里任何校验代码。**

### 3. 门禁 3 所需的留出集作者未公开（已用替代方案）
`src/c_check.py` 要求读 `data/eval/*.jsonl`，而这些文件被 gitignore 且作者未发布。
脚本本身会明确报错拒绝运行（而不是「检查了 0 条却报 PASS」），这个设计值得称赞。

**应对**：新增 `build/gate3_chain_check.py`，用**我们自己生成的验证集**跑完全相同的比对
（同样的循环、停止规则、截断逻辑）。它能证明移植正确，但**不能**证明模型的留出集水平——
这是两个不同的问题，报告里已分别标注。

### 4. 少量样本超出长度上限
100 条训练样本（0.07%）因为编码后长度超过 `seq_len=96` 被丢弃。这是设计内的正常损耗。

---

## 五、怎么用（不需要写代码）

**双击 `start-repl.bat`**，然后直接打英文指令。

实测效果：

| 你说 | 它做什么 |
|---|---|
| `turn on pin 4` | `set pin4 high` ✅ 执行 |
| `blink pin 4 every 5 seconds 3 times` | `blink pin4 5000ms x3` ✅ 执行 |
| `chase pins 4 5 6 every 1 second` | `seq pin4 pin5 pin6 1000ms` ✅ 执行 |
| `turn on pin 4 5 and 6` | `set pin4 pin5 pin6 high` ✅ 执行 |
| `switch off pin 100` | ❌ 拒绝：板子上没有 100 号引脚 |
| `blink pin 4 every 60 seconds` | ❌ 拒绝：间隔 60000ms 超出 50–10000ms |
| `call pin 4 the desk lamp` → `turn on the desk lamp` | ✅ 起名并记住，之后能听懂 |
| `turn on the porch lights` | `set pin5 pin6 pin7 pin8 high` ✅ 一组引脚 |
| `switch off the aquarium pump` | ❌ 拒绝：不认识这个名字 |

**注意**：这里跑的是 C 版推理程序，和将来烧进芯片的是同一套代码，所以看到的行为就是芯片上的行为。

---

## 六、烧进开发板（已完成）

**结论：不能图省事烧官方镜像，必须自己编译。**

### 为什么

对照实验——用我们编译的 `repl.exe`（内含我们自己的分词器）去跑**作者发布的 v0.3.0 `model.bin`**：

| 输入 | 作者模型 + 我们的分词器 | 我们的模型 + 我们的分词器 |
|---|---|---|
| `turn on pin 4` | `set pin4 toggle` ❌ | `set pin4 high` ✅ |
| `blink pin 4 every 500ms 3 times` | `blink pin4 2000ms x50` ❌ | `blink pin4 500ms x3` ✅ |

输出**不是乱码，是"看起来合理但全错"**。原因是双方的 BPE 词表编号不同，而官方的程序里**烧死了作者自己的 `bpe.h`**。若只换 `model.bin`，就会得到"能跑、日志干净、动作全错"的状态——正是作者 README 里警告的 `malformed generation`。所以程序端必须用我们自己 `gen_assets.py` 产出的 `bpe.h` / `symbols.h` 重新编译。

### 板子识别（COM7）

| 项目 | 读到的值 |
|---|---|
| 芯片 | **ESP32-S3** (QFN56, rev v0.2) |
| PSRAM | **内置 8 MB** |
| Flash | **16 MB**（四线） |
| USB 模式 | USB-Serial/JTAG（`VID_303A&PID_1001`） |
| MAC | `1c:29:04:24:bd:cc` |

板子有两个 USB 口，**必须插标着 USB 的那个**（直连主芯片），UART 口（CH340，`VID_1A86`）在你这台电脑上驱动还是坏的，而且我们的固件用 `CDCOnBoot=cdc` 走原生 USB，插错口会"程序在跑但串口一片沉默"。

### 烧录参数与产物

```sh
arduino-cli compile --fqbn 'esp32:esp32:esp32s3:PartitionScheme=custom,PSRAM=opi,CDCOnBoot=cdc' \
  --build-path E:/esp32-tools/build/sketch --output-dir E:/esp32-tools/dist/out firmware/device/espcontrol
```

| 项目 | 结果 |
|---|---|
| 固件体积 | 338,008 字节（占 Flash 2%） |
| 模型装入分区 | 1,248,544 / 1,966,080 字节，剩 717,536 字节 |
| 合并镜像 | 3,411,232 字节（3.25 MB，与官方发布包同尺寸） |
| 写入 | 100%，26.9 秒，`Hash of data verified` |

一键脚本：`build/flash.sh COM7`（同步源码 → 编译 → 校验分区 → 合并单镜像 → 烧录）

### 上板实测（真实串口输出）

```
espcontrol
model: V=1024 D=64 L=6 H=8  (1219 KB mapped)
pins: 25 usable (1..48)
aliases: 0 stored
```

| 输入 | 板子回答 | 耗时 |
|---|---|---|
| `turn on pin 4` | `pin 4 high` | 568 ms |
| `blink pin 4 every 500ms 3 times` | `blinking 1 pin every 500ms, 3 times` | 1210 ms |
| `chase pins 2 3 4 every 1 second` | `chasing 3 pins every 1000ms` | 1429 ms |
| `turn on pin 4 5 and 6` | `pin 4, 5, 6 high` | 1046 ms |
| `switch off pin 100` | ❌ `refused: pin 100 is not a GPIO on this board` | 779 ms |
| `blink pin 4 every 60 seconds` | ❌ `refused: interval 60000ms is outside 50-10000ms` | 1101 ms |
| `chase pins 1..9 every 1 second` | ❌ `refused: a chase runs at most 6 pins, got 9` | 2804 ms |
| `turn on the aquarium pump` | ❌ `refused: I don't know "aquarium pump"` | 1101 ms |
| `alias desk lamp = 4` → `turn on the desk lamp` | ✅ `pin 4 high` | 674 ms |
| `TURN OFF 39` | `pin 39 low` | 778 ms |

**注意 `blink ... every 60 seconds` 这一条**：模型把 `60000` 完整抄了出来（没有像作者早期版本那样滑成 `6000`），是校验层而不是模型拒绝了它——这正是这个项目想要的架构。

启动日志里的一行 `E (98) esp_core_dump_flash: No core dump partition found!` 是无害提示，`partitions.csv` 本来就没有 core dump 分区。

### 双击跟板子对话

`talk-to-board.bat` —— 打开串口监视器，直接打英文指令。

---

## 七、踩坑记录（烧录阶段）

1. **C 盘满了（剩余 0 字节）**。装 ESP32 核心时报 `There is not enough space on the disk`。根因是 C 盘本身接近满，加上本次会话把 `uv` 缓存涨到 3.1 GB、用户临时目录涨到 1.8 GB。
   - 处置：把 `arduino15`（7.2 GB）整体搬到 `E:\esp32-tools\arduino15`，改 `arduino-cli.yaml` 的 `directories.*` 指过去；编译的 `--build-path` 也指到 E 盘。
   - **注意**：`uv` 缓存是用**硬链接**接到项目 `.venv` 的，直接截断/删除缓存会连虚拟环境里的 torch 一起毁掉，所以那个缓绝不能碰。
   - 另一个坑：C 盘满的时候**连删除都做不了**——删除机制要先移到回收站，而回收站需要可用空间（`ENOSPC`）。最后是用"截断文件到 0 字节"（不需要可用空间）打破死循环的。
2. **arduino-cli 自带下载器不支持续传**。394 MB 的 Xtensa 编译器下到 43 MB 就 `unexpected EOF`，然后从头再来。
   - 处置：写 `tools/fetch_tools.py`，从 package index 解析出 18 个依赖的 URL + SHA256，用 `curl -L -C - --retry-all-errors` 下到 `staging/packages/`（arduino-cli 认这个缓存并校验 checksum）。
   - 注意 `mkspiffs` 没有 mingw 版且不在该 index 中，需要跳过。
3. **板子两个 USB 口插错了**。插到 UART 口（CH340）时报 `Error` 状态、连串口号都没分到。换到 USB 口立刻正常。
4. **端口枚举有延迟**。刚插上时 `GetPortNames()` 返回空、esptool 报"端口不存在"，等几秒后 `SERIALCOMM` 里出现 `COM7` 就正常了。

---

## 八、新增/修改的文件清单

**修改（上游仓库内）**
- `data/massive.py` — 兼容 HuggingFace 数据集的新配置结构

**新增（自建工具）**
- `build/verify.exe`、`build/tok_test.exe`、`build/repl.exe` — 三个 C 校验程序
- `build/run_gate_win.py` — Windows 下运行门禁 2 的封装
- `build/gate3_chain_check.py` — 门禁 3 的替代实现
- `build/eval_report.txt` — 完整评估报告
- `build/flash.sh` — 一键编译 + 合并 + 烧录
- `build/serial_probe.py` — 上板自动测试脚本
- `build/compare/author-model.bin` — 作者的模型（用于对照实验）
- `start-repl.bat`、`talk-to-board.bat` — 两个双击即用的启动器
- `tools/arduino-cli/` — arduino-cli 1.5.1 + 隔离配置
- `tools/fetch_tools.py` — 断点续传下载器
- `tools/w64devkit/` — 免安装 GCC 16.2.0（工作区级，未进系统）

**外部依赖（已搬到 E 盘，C 盘太满）**
- `E:\esp32-tools\arduino15\` — ESP32 Arduino 核心 3.3.12 + 全部工具链
- `E:\esp32-tools\build\`、`E:\esp32-tools\dist\` — 编译中间产物与成品镜像

**训练产物（已被 gitignore）**
- `data/corpus/`、`data/bpe.json`、`data/meta.json`、`data/*_tok.u16`、`data/*_mask.u8`
- `runs/cmd-v1-s0.pt`、`runs/cmd-v1-s0.json`
- `firmware/model/model.bin`、`firmware/golden.txt`
- `firmware/generated/bpe.h`、`firmware/symbols.h`
