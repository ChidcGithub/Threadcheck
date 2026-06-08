# threadcheck

[![Python](https://img.shields.io/badge/python-3.12%2B-blue)](https://www.python.org)
[![License](https://img.shields.io/badge/license-MIT-green)](LICENSE)
[![PyPI](https://img.shields.io/badge/pypi-v0.1.0-orange)](https://pypi.org/project/threadcheck/)
[![Tests](https://img.shields.io/badge/tests-21%2F21-passing-brightgreen)]()

Python 并发竞态检测器，面向 free-threading（无 GIL）时代。通过静态分析和运行时插桩，检测多线程 Python 程序中对共享可变状态的并发访问。

---

## 背景

Python 3.14（2026）正式支持 free-threading，移除全局解释器锁（GIL），使多线程代码能够真正并行执行。然而 Python 生态中缺少配套的并发调试工具。

| 语言 | 工具 |
|---|---|
| Go | `-race` |
| C++ | ThreadSanitizer |
| Java | SpotBugs / FindBugs |
| Python | 无（需 Clang 重编译 CPython + TSan） |

threadcheck 是一个纯 Python 竞态检测库，`pip install` 即可使用。

---

## 功能

- **AST 静态分析** -- 扫描全局变量、nonlocal 变量、类属性、模块级可变对象，检测缺失的锁保护
- **运行时动态检测** -- 在导入时通过 AST 变换注入追踪代码，使用向量时钟追踪内存访问，检测 happens-before 违反
- **锁感知抑制** -- 识别 `threading.Lock`、`RLock` 和 `with` 同步模式，有锁保护时自动抑制告警
- **置信度评分** -- 基于线程上下文和锁覆盖度标记 HIGH / MEDIUM / LOW
- **CLI 工具** -- 一条命令完成静态扫描或带插桩的动态执行
- **JSON / SARIF 输出** -- 适用于 CI/CD 流水线集成

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

输出示例：

```
[WARNING] [HIGH] [unsafe_global] my_project/counter.py:8:8
       全局变量 `counter` 在多线程中无锁修改
       建议: 使用 `threading.Lock()` 保护访问
```

JSON 输出：

```bash
threadcheck scan my_project/ --json -o report.json
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
      Thread-28928 (write) at my_script.py:8
      Thread-9888 (write) at my_script.py:8
```

加锁保护的脚本输出：

```
No data races detected
```

### CI 集成

```bash
pip install threadcheck
threadcheck scan src/ --json -o threadcheck_report.json
```

---

## 命令列表

| 命令 | 说明 | 状态 |
|---|---|---|
| `scan <path>` | 静态分析文件或目录 | 稳定 |
| `run <script>` | 运行时动态检测 | Beta |
| `check-compat <path>` | Free-Threading 兼容检查 | 计划中 |

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

---

## 架构

### 静态分析流程

1. 解析源代码为 AST
2. 识别共享可变状态：全局变量、nonlocal 变量、类属性（`self.x`）、模块级可变对象
3. 检测线程创建点（`threading.Thread`）
4. 对照锁使用情况（`with lock:`、`lock.acquire()`）
5. 分配置信度：HIGH（线程目标函数，无锁）、MEDIUM（有线程上下文，无锁）、LOW（可疑模式，无线程上下文）
6. 输出检测结果及修复建议

### 动态检测流程

1. 解析源代码为 AST
2. 识别每函数作用域内的共享变量
3. 变换 AST：在共享变量访问前后注入 `write_before()`、`lock_acquire()`、`lock_release()` 追踪调用
4. 编译并在追踪器下执行变换后的代码，追踪器维护每线程向量时钟
5. 锁获取时同步时钟（happens-before 合并）
6. 执行结束后扫描访问日志，检测冲突操作（无 happens-before 关系的并发写或写-读对）
7. 报告检测到的竞态，附带线程 ID 和源码位置

---

## 路线图

| 阶段 | 功能 | 状态 |
|---|---|---|
| 1 | 项目骨架、CLI、基础静态分析（全局/nonlocal） | 完成 |
| 2 | 类属性检测、锁抑制、置信度分级 | 完成 |
| 3 | AST import hook、运行时插桩、向量时钟追踪 | 完成 |
| 4 | 报告去重、增强 happens-before 分析 | 计划中 |
| 5 | SARIF 输出、JSON 报告 | 计划中 |
| 6 | pytest 插件 | 计划中 |
| 7 | Free-Threading 兼容检查器 | 计划中 |

---

## 已知局限

- 静态分析存在假阳性（报告实际不会发生的竞态）和假阴性（遗漏通过别名或容器间接共享导致的竞态）
- 运行时 AST 变换可能影响自省源代码或栈帧对象的代码行为
- 运行时插桩有性能开销（典型代码约 2-5 倍减速）
- 锁追踪仅支持 `threading.Lock`、`threading.RLock` 及标准 `with` 模式；其他同步原语（`threading.Event`、`threading.Condition`、第三方库）暂不支持

---

## 许可证

MIT

---

## 贡献

欢迎贡献代码或提交 Issue。
