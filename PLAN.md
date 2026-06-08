# threadcheck — Python 并发竞态检测器

## 为什么做这个？

Python 3.14 (2026) 正式支持 Free-Threading (无 GIL 模式)，Python 终于能像 Go、Java 一样真正并行执行多线程代码。但生态里完全没有配套的并发调试工具。

- Go 有 `-race`
- C++ 有 ThreadSanitizer
- Java 有 FindBugs/SpotBugs
- Python：目前唯一方案是用 Clang 重编译整个 CPython + C 扩展，再跑 LLVM TSan

目标：**pip install threadcheck** 即用的纯 Python race condition 检测库。

---

## 用法示意

```python
import threadcheck

@threadcheck.monitor
def my_function():
    global counter
    counter += 1  # 警告：无锁修改共享状态！
```

```bash
# CLI 工具
$ threadcheck scan my_project/
⚠️  data race detected in my_module.py:42
    线程 A 写入 `shared_list.append(x)`
    线程 B 同时读取 `len(shared_list)`
```

```bash
# pytest 集成
$ pytest --threadcheck --threadcheck-iterations=200
```

---

## 项目结构

```
threadcheck/
├── pyproject.toml
├── src/
│   └── threadcheck/
│       ├── __init__.py
│       ├── __main__.py              # python -m threadcheck
│       ├── cli.py                   # 参数解析
│       │
│       ├── static/                  # ═══ 静态分析 ═══
│       │   ├── analyzer.py          # 主入口，协调多个 visitor
│       │   ├── visitors.py          # AST 遍历器 (找 global/nonlocal/self/Thread)
│       │   ├── lock_tracker.py      # 锁保护分析
│       │   └── models.py            # RaceWarning 等数据模型
│       │
│       ├── dynamic/                 # ═══ 动态检测 ═══
│       │   ├── transform.py         # AST import hook: 注入追踪代码
│       │   ├── tracker.py           # 线程本地追踪器 + 操作日志
│       │   ├── detector.py          # 冲突判定 (vector clock / HB)
│       │   ├── clock.py             # 向量时钟实现
│       │   └── hook.py              # sys.meta_path 导入钩子
│       │
│       ├── compat/                  # ═══ FT 兼容检查 ═══
│       │   └── checker.py           # 扫描 pyproject.toml / C 扩展
│       │
│       ├── reporting/               # ═══ 报告输出 ═══
│       │   ├── formatter.py         # 终端彩显格式化
│       │   ├── sarif.py             # SARIF 输出 (GitHub CodeQL 格式)
│       │   └── types.py             # Issue, Severity 类型定义
│       │
│       └── pytest_plugin.py         # pytest 插件
│
├── tests/
│   ├── static/
│   ├── dynamic/
│   ├── compat/
│   ├── fixtures/                    # 含已知 race 的 .py 样本
│   └── conftest.py
```

---

## 三大检测管线

### 管线 1：AST 静态分析

**扫描目标：**

| 模式 | 检测方式 | 示例 |
|---|---|---|
| `global` 变量突变 | `ast.Global` + 后续赋值 | `global x; x += 1` |
| `nonlocal` 变量突变 | `ast.Nonlocal` + 后续赋值 | `nonlocal x; x = 1` |
| 类属性写 (`self.x =`) | `ast.Attribute` on `self` | `self.counter += 1` |
| 模块级可变对象 | 模块顶层 list/dict/set 赋值 | `shared = []` |
| 线程启动 | `ast.Call` 匹配 `Thread(target=...)` | `Thread(target=foo)` |
| 锁缺失 | 搜索 acquire/release 配对 | 写共享变量前无锁 |

**输出模型：**

```python
@dataclass
class RaceWarning:
    file: str
    line: int
    col: int
    severity: Severity          # WARNING / ERROR
    category: WarningCategory    # UNSAFE_GLOBAL / UNPROTECTED_ACCESS / ...
    message: str
    suggestion: str | None       # 修复建议
```

**置信度分级：**
- `HIGH` — 确定有竞争 (如：Thread 中写 global 且无任何锁)
- `MEDIUM` — 可能竞争 (如：类方法中写 self.x，类被多线程使用)
- `LOW` — 可疑模式 (如：模块级可遍历出现在多个函数中)

---

### 管线 2：动态检测 (AST import hook)

#### 2a. Import Hook 注册

```python
class ThreadCheckLoader:
    """PEP 302 loader，在模块导入时做 AST 变换"""
    def create_module(self, spec):
        return None

    def exec_module(self, module):
        source = get_source(spec)
        tree = ast.parse(source)
        transformed = TrackInjector().visit(tree)  # AST 变换
        ast.fix_missing_locations(transformed)
        code = compile(transformed, spec.origin, 'exec')
        exec(code, module.__dict__)
```

注册到 `sys.meta_path` 最前面，拦截所有 `.py` 文件导入。

#### 2b. AST 变换规则

**规则 1：写全局变量**
```python
# 变换前
counter = counter + 1

# 变换后
_tracker = _threadcheck_get_tracker()
_tracker.write_before('counter')
counter = counter + 1
_tracker.write_after('counter')
```

**规则 2：读/写类属性**
```python
# 变换前
self.items.append(x)

# 变换后
_tracker = _threadcheck_get_tracker()
_tracker.read_before('self.items')
_tracker.write_before('self.items')
self.items.append(x)
_tracker.write_after('self.items')
_tracker.read_after('self.items')
```

**规则 3：锁操作**
```python
# 变换前
with lock:
    counter += 1

# 变换后
_tracker.lock_acquire(lock)
with lock:
    _tracker.write_before('counter')
    counter += 1
    _tracker.write_after('counter')
_tracker.lock_release(lock)
```

#### 2c. 追踪器 + 冲突检测

**向量时钟：**
```python
class VectorClock:
    def __init__(self, tid):
        self.clock: dict[int, int] = {tid: 0}

    def tick(self):
        self.clock[tid] += 1

    def merge(self, other):
        for k, v in other.clock.items():
            self.clock[k] = max(self.clock.get(k, 0), v)
```

**冲突判定：** 两访问 (tid_a, var, op_a, clock_a) 和 (tid_b, var, op_b, clock_b)
- `clock_a` 和 `clock_b` 不可比较 (既不 ≤ 也不 ≥) → 并行访问
- 至少一个是写操作 → **data race**

#### 2d. 预期性能

| 场景 | 减速比 |
|---|---|
| 密集型共享变量访问 | 10x-100x |
| 正常代码 (大部分不涉及共享) | 2x-5x |
| 仅静态分析 (无运行时) | 1x |

---

### 管线 3：Free-Threading 兼容检查

**检查清单：**
1. `pyproject.toml` → `[tool.freethreading]` 是否存在
2. `setup.cfg` / `setup.py` → 是否声明 free-threading 支持
3. C 扩展 `.pyd` / `.so` → 是否链接 freethreaded ABI 的 Python
4. `sys._is_gil_enabled()` 运行时检查

**输出示例：**
```
📦 numpy          ❌ 未声明 FT 兼容
📦 pandas         ⚠️ 声明兼容，但有 C 扩展需验证
📦 mylib          ✅ 完全兼容
```

---

## 报告输出管道

```
检测结果 (List[RaceWarning / RaceEvent])
    │
    ├── formatter.py → 终端 (colorized, 类似 Go -race 风格)
    │
    ├── json         → threadcheck_report.json
    │
    └── sarif.py     → threadcheck_report.sarif (可上传 GitHub)
```

**终端输出示例：**
```
⚠️  data race detected in counter.py:42
   ├─ Thread-1 (write) `counter += 1` at line 42
   ├─ Thread-2 (write) `counter += 1` at line 18
   └─ No happens-before relationship between accesses
```

---

## pytest 插件集成

```python
def pytest_addoption(parser):
    parser.addoption('--threadcheck', action='store_true')
    parser.addoption('--threadcheck-iterations', default=100)

def pytest_collection_modifyitems(config, items):
    if config.getoption('--threadcheck'):
        for item in items:
            item.obj = wrap_with_detection(item.obj)
```

---

## 实施方案优先级

| Phase | 内容 | 预估时间 |
|---|---|---|
| **Phase 1** | 项目骨架、CLI、静态分析 (global/nonlocal 检测) | 1-2 天 |
| **Phase 2** | 静态分析完善 (类属性、锁追踪、置信度分级) | 1-2 天 |
| **Phase 3** | 动态检测 — import hook + AST 变换引擎 | 3-5 天 |
| **Phase 4** | 动态检测 — vector clock 冲突判定算法 | 2-3 天 |
| **Phase 5** | 报告输出 (终端 + JSON + SARIF) | 1 天 |
| **Phase 6** | pytest 插件 | 1 天 |
| **Phase 7** | FT 兼容检查模块 | 1 天 |
| **Phase 8** | 测试、文档、发布 | 2 天 |

---

## 风险及缓解

| 风险 | 影响 | 缓解 |
|---|---|---|
| AST import hook 破坏正常语义 | 被测代码行为改变 | 严格测试 + 白名单机制 |
| 动态检测性能过慢 | 不可用于大项目 | 默认只启用静态分析，`--deep` 才启用动态 |
| 假阳性过多 | 用户不信任 | 三级置信度 + 抑制文件 (`.threadcheckignore`) |
| 假阴性漏报 | 错过真实 race | 结合多种检测算法互补 |
