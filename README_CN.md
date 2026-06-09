# Threadcheck

[![Python](https://img.shields.io/badge/python-3.12%2B-blue)](https://www.python.org)
[![License](https://img.shields.io/badge/license-MIT-green)](LICENSE)
[![Platform](https://img.shields.io/badge/platform-linux%20%7C%20windows%20%7C%20macos-lightgrey)]()
[![CI](https://github.com/ChidcGithub/Threadcheck/actions/workflows/test.yml/badge.svg)](https://github.com/ChidcGithub/Threadcheck/actions/workflows/test.yml)
[![Ruff](https://img.shields.io/badge/code%20style-ruff-000000)](https://github.com/astral-sh/ruff)

Python 并发竞态检测器，面向 free-threading（无 GIL）时代。通过静态分析和运行时插桩，检测多线程 Python 程序中对共享可变状态的并发访问。

---

## 背景

Python 3.14（2026）正式支持 free-threading，移除全局解释器锁（GIL），使多线程代码能够真正并行执行。然而 Python 生态中缺少配套的并发调试工具。

| 语言 | 工具 |
|---|---|
| Go | `-race` |
| C++ | ThreadSanitizer |
| Java | SpotBugs |
| Python | 无（需 Clang 重编译 CPython + TSan） |

threadcheck 是一个纯 Python 竞态检测库，`pip install` 即可使用，支持 Linux、Windows、macOS。

---

## 功能

- **AST 静态分析** -- 扫描 `global`、`nonlocal`、类属性、模块级 list/dict 等共享可变状态，检测缺失的锁保护
- **运行时动态检测** -- AST 变换注入追踪代码，向量时钟检测 happens-before 违反（read-write 和 write-write 竞态）
- **锁感知抑制** -- 识别 `threading.Lock`/`RLock` 和 `with` 同步模式；支持嵌套锁 `with lock1, lock2:`，自动按锁追踪向量时钟
- **跨模块分析** -- 两遍扫描收集目录下所有文件的 `Thread(target=...)` 和 `executor.submit/map` 目标
- **置信度评分** -- 基于线程上下文和锁覆盖度标记 HIGH / MEDIUM / LOW
- **配置文件** -- `.threadcheckignore`（gitignore 风格 + `file:line` 行抑制）和 `pyproject.toml` 的 `[tool.threadcheck]` 段
- **多种输出格式** -- 终端（按文件分组、彩色）、JSON、SARIF v2.1.0、自包含 HTML 报告
- **pytest 插件** -- `--threadcheck` 标志在测试执行期间自动检测竞态
- **Free-Threading 兼容检查** -- `threadcheck compat` 扫描已安装包的 C 扩展并检查 FT ABI 标签

---

## 安装

```bash
pip install threadcheck
```

要求 Python 3.12+，推荐 Python 3.14+ 以使用 free-threading 特性。

---

## 快速开始

### 静态分析

扫描文件或目录中的潜在竞态条件，无需执行代码：

```bash
threadcheck scan my_project/
```

输出示例（按文件分组，带严重级别图标和每文件小计）：

```
  [1/2] my_project/counter.py
  ---------------------------------
    [!] HIGH [unsafe_global] line 8:8
          Global variable `counter` modified without lock
          suggestion: Use `threading.Lock()` to protect `counter`
    [i] LOW [thread_usage] line 10:11
          Thread creation detected (target=increment)

  [2/2] my_project/worker.py
  ---------------------------------
    [!] HIGH [shared_mutable] line 15:8
          Module-level mutable object `results.append()` called from multiple threads

Total: 2 issue(s) in 2 file(s) (0 error(s), 2 warning(s), 0 info(s))
```

### 动态检测

执行脚本并在运行时检测实际的 data race：

```bash
threadcheck run my_script.py
```

有竞态时输出：

```
Data races detected:

  [!] `counter`
    |--- Thread-28928 (write) at my_script.py:8
    |--- Thread-9888 (write) at my_script.py:8
    \--- No happens-before relationship between accesses
       (10000 overlapping accesses)
```

加锁保护的脚本输出：

```
No data races detected
```

### Free-Threading 兼容检查

检查项目依赖是否支持 free-threading：

```bash
threadcheck compat
```

输出示例：

```
threadcheck compat - Free-threading compatibility check
Python 3.13.10

  [OK] numpy                 C extension has free-threading tag (cp313t-)
  [??] torch                 C extension without free-threading tag
  [OK] pytest                pure Python, no C extensions

Total: 3 package(s) - 2 compatible, 1 need verification, 0 not installed
```

### HTML 报告

```bash
threadcheck scan my_project/ -o report.html
```

生成自包含 HTML 报告，支持暗色/亮色主题自适应、可排序表格和摘要卡片。

### 安静/详细模式

```bash
threadcheck scan my_project/ -q     # 仅一行摘要
threadcheck scan my_project/ -v     # 显示源码片段
threadcheck scan my_project/        # 默认分组输出
```

---

## 配置

### `.threadcheckignore`

在项目根目录创建 `.threadcheckignore` 文件（gitignore 风格）：

```
# 忽略生成的文件
generated/*.py
build/*.py

# 精确行抑制
src/legacy.py:42          # 抑制第 42 行
src/legacy.py:50-60       # 抑制第 50-60 行

# 否定（不忽略）
*.py
!important.py
```

### `pyproject.toml`

```toml
[tool.threadcheck]
ignore = [
    "build/*",
    "generated/*.py",
]
```

两者自动合并。

---

## 输出格式

| 标志 | 格式 | 用途 |
|---|---|---|
| （默认） | 终端（彩色、按文件分组） | 交互使用 |
| `-q` | 一行摘要 | 快速状态 |
| `-v` | 终端 + 源码片段 | 调试 |
| `--json` | JSON | CI 流水线 |
| `--sarif` | SARIF v2.1.0 | GitHub CodeQL 集成 |
| `-o report.html` | 自包含 HTML | 团队报告 |

---

## 命令列表

| 命令 | 说明 |
|---|---|
| `scan <path>` | 静态分析文件或目录 |
| `run <script>` | 运行时动态检测 |
| `compat [path]` | 检查依赖的 FT 兼容性 |

---

## 作为库使用

```python
from threadcheck import analyze_file, analyze_path

warnings = analyze_file("my_module.py")
warnings = analyze_path("src/")

for w in warnings:
    print(f"{w.file}:{w.line} [{w.confidence.value}] {w.message}")
```

```python
from threadcheck.dynamic.tracker import ThreadCheckTracker
from threadcheck.dynamic.transform import transform_and_compile

code = transform_and_compile(source, "script.py")
ThreadCheckTracker.start()
exec(code, {"_threadcheck_tracker": ThreadCheckTracker})
ThreadCheckTracker.stop()

print(ThreadCheckTracker.format_races())
ThreadCheckTracker.reset()
```

### pytest 集成

```bash
python -m pytest tests/ --threadcheck
```

插件通过 `pytest_runtest_call` 钩子自动检测竞态，违规时报告为测试失败。

---

## 架构

### 静态分析流程

1. 解析源代码为 AST
2. 识别共享可变状态：全局变量、nonlocal 变量、类属性（`self.x`）、模块级可变对象（list/dict/set）
3. 检测线程创建点（`threading.Thread`、`executor.submit/map`）
4. 对照锁使用情况（`with lock:`、嵌套 `with lock1, lock2:`）
5. 分配置信度：HIGH（线程目标函数，无锁）、MEDIUM（有线程上下文，无锁）、LOW（可疑模式，无线程上下文）
6. 输出检测结果及修复建议

### 动态检测流程

1. 解析源代码为 AST
2. 识别每函数作用域内的共享变量（`global`、`nonlocal` 声明）
3. 变换 AST：对共享变量的读操作注入 `read_before()`，写操作注入 `write_before()`；`with` 块前后注入 `lock_acquire()`/`lock_release()`
4. 编译并在追踪器下执行变换后的代码，追踪器维护每线程向量时钟
5. 锁获取时合并锁的时钟到当前线程（happens-before）
6. 锁释放时将当前线程时钟保存到锁
7. 执行结束后扫描访问日志，检测冲突操作（并发的写-写或写-读对，无 happens-before 关系）
8. 报告检测到的竞态，附带线程 ID、源码位置和重叠次数

### Free-Threading 兼容检查

1. 从 `pyproject.toml` 或 `requirements.txt` 解析项目依赖
2. 对每个已安装包，扫描 C 扩展文件（`.pyd`/`.so`）
3. 无 C 扩展 -> COMPATIBLE
4. C 扩展文件名含 free-threading ABI 标签（`cp313t-`/`cpython-313t-`）-> COMPATIBLE
5. 否则 -> NEEDS_VERIFICATION

---

## 项目结构

```
threadcheck/
|--- pyproject.toml
|--- src/threadcheck/
|   |--- __init__.py
|   |--- __main__.py
|   |--- _version.py           # 版本唯一来源
|   |--- _tid.py               # 平台线程 ID（CI 中按平台替换）
|   |--- cli.py                # 参数解析与调度
|   |--- config.py             # .threadcheckignore + pyproject.toml 加载器
|   |--- pytest_plugin.py      # --threadcheck pytest 标志
|   |--- static/
|   |   |--- analyzer.py       # 静态分析入口
|   |   |--- visitors.py       # 5 个 AST 遍历器
|   |   |--- lock_tracker.py   # 锁使用分析
|   |   \--- models.py         # RaceWarning, Severity, Confidence
|   |--- dynamic/
|   |   |--- __main__.py       # 动态检测入口
|   |   |--- transform.py      # AST 变换引擎
|   |   |--- tracker.py        # 运行时追踪器 + 向量时钟
|   |   |--- clock.py          # 向量时钟实现
|   |   \--- hook.py           # sys.meta_path import hook
|   |--- compat/
|   |   |--- checker.py        # C 扩展 FT 标签扫描
|   |   \--- models.py         # FTCompatResult, CompatStatus
|   \--- reporting/
|       |--- formatter.py      # 终端 / JSON 输出
|       |--- sarif.py          # SARIF v2.1.0 输出
|       \--- html.py           # HTML 报告输出
|--- tests/
|   |--- fixtures/             # 11 个含已知 race 的样本
|   |--- test_static_analyzer.py
|   |--- test_dynamic_detector.py
|   |--- test_formatter.py
|   |--- test_sarif.py
|   |--- test_compat.py
|   |--- test_config.py
|   \--- test_pytest_plugin.py
|--- demo/
|   |--- race_example.py       # 含故意 race 的样本
|   \--- run_demo.py           # 演示所有输出格式
\--- README.md / README_CN.md
```

---

## 平台支持

| 平台 | Python | CI |
|---|---|---|
| Linux (x86_64) | 3.12, 3.13, 3.14 | ubuntu-latest |
| Windows (amd64) | 3.12, 3.13, 3.14 | windows-latest |
| macOS (ARM64) | 3.12, 3.13, 3.14 | macos-latest |

线程 ID：Linux/macOS 使用 `native_id`（gettid），Windows 使用 `threading.get_ident()`。

---

## 路线图

- **v0.0.1.2a1**（当前版本）：Round A（核心缺陷修复）+ Round B（开发者体验）— 静态+动态分析、锁追踪、跨模块分析、pytest 插件、FT 兼容检查、HTML 报告、配置文件、增强输出
- **v0.2.0**（下一版本）：Round C — `Thread.join()` happens-before、`threading.Atomic` 支持、函数调用链追踪、死锁检测
- **v1.0.0**（未来）：Round D — GitHub Action、pre-commit hook、VS Code 集成、稳定 API

---

## 已知局限

- 静态分析存在假阳性（报告实际不会发生的竞态）和假阴性（遗漏通过别名或容器间接共享导致的竞态）
- 运行时 AST 变换可能影响自省源代码或栈帧对象的代码行为
- 运行时插桩有性能开销（典型代码约 2-5 倍减速）
- 锁追踪仅支持 `threading.Lock`、`threading.RLock` 及标准 `with` 模式；其他同步原语（`threading.Event`、`threading.Condition`、第三方库）暂不支持
- 跨模块分析处理 `Thread(target=...)` 和 `executor.submit/map`，但不执行完整的函数间数据流分析

---

## 许可证

MIT

---

## 贡献

欢迎贡献代码或提交 Issue。
