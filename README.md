# Patch-Bay Walk Verifier（临时展馆走线核验 API）

纯后端 JSON 服务：给定一批接头（顶点）和无向测试跳线（边，允许自环与并联），
判断能否从某接头出发、**沿每根跳线恰好走一次**完成整网通断检查（欧拉迹），
并在可行时返回**确定性的、UTF-8 字节序最小的完整走线**。

- Python 3.12 + FastAPI，Pydantic 负责整批 422 校验
- `docker compose up` 启动 `api`
- pytest：图算法单测 + **短图穷举对拍** + HTTP 边界测试
- 算法不枚举任何排列，复杂度 O(E log E)，支持 300 接头 / 3000 跳线上限

## 运行

```bash
docker compose up --build        # http://localhost:8000  (Swagger: /docs)
```

本地开发：

```bash
python3.12 -m venv .venv && . .venv/bin/activate
pip install -r requirements-dev.txt
uvicorn app.main:app --reload
pytest                           # 全部用例，含数百随机短图穷举对拍
```

## 接口

`POST /api/v1/walks/verify`

请求：`connectors` 为 1–300 个**唯一、非空 ASCII** 接头名；`jumpers` 为
1–3000 根跳线，`id` 唯一，`endpoints` 为无向端点对，`[x, x]` 即自环。

```json
{
  "connectors": ["A", "B", "C", "D", "E"],
  "jumpers": [
    {"id": "t1", "endpoints": ["A", "B"]},
    {"id": "t2", "endpoints": ["B", "C"]},
    {"id": "t3", "endpoints": ["C", "A"]},
    {"id": "t4", "endpoints": ["A", "D"]},
    {"id": "t5", "endpoints": ["D", "E"]},
    {"id": "t6", "endpoints": ["E", "A"]}
  ]
}
```

### 200 — 三种判定（拓扑失败同样是 200，不是 HTTP 错误）

可行：

```json
{"status": "OK", "start": "A",
 "connectors": ["A","B","C","A","D","E","A"],
 "jumpers":    ["t1","t2","t3","t4","t5","t6"]}
```

- 起点固定：有 2 个奇度接头时取**最小奇度接头**；全偶时取**最小有边接头**。
- 忽略所有零度接头。
- 走线按 **(接头序列, 跳线 id 序列)** 的 UTF-8 字节序取最小；
  即先比每一步走到的接头，接头序列完全相同再比跳线 id 序列。
  注意是字节序：`"J10" < "J2"`，`"Z" < "a"`。

不连通（**DISCONNECTED 优先于奇度判定**）：`witness` 给出分属两个不同
有边分量的最小接头——各分量最小接头中最小的两个（零度接头不参与）：

```json
{"status": "DISCONNECTED", "components": 2, "witness": ["A", "C"]}
```

连通但奇度接头数不是 0 或 2：

```json
{"status": "ODD_DEGREE", "odd_connectors": ["A", "B", "C", "D"]}
```

### 422 — 整批拒绝（不做部分接受）

重复跳线 id、端点引用未知接头、接头名重复/非 ASCII/为空、数量越界
（0 或 >300、0 或 >3000）、端点不是 2 个、类型错误、多余字段等，
均返回 FastAPI 标准 422，`detail` 中带可直接定位的原因。

## 确定性

判定结果与响应**不依赖跳线录入顺序或接头录入顺序**：邻接表按
`(下一接头 UTF-8 字节, 跳线 id UTF-8 字节)` 排序，分量遍历、奇度列表、
起点选择均按同一字节序。

## 算法（`app/euler.py`）

迭代式 Hierholzer：每一步始终取当前接头**最小的未用跳线**，顶点在边耗尽时
出栈，最终把出栈顺序反转得到走线。

为什么这恰好是字节序最小走线（可归纳证明，见模块文档字符串）：

- 若最小邻边可行（移除后剩余有边图仍连通），反转后的输出第一步就是它，
  问题归约为少一条边的同类问题；
- 若最小邻边是会"把人困在另一侧"的桥（仅可能出现在 2 奇度、且桥通向终点侧
  时），反转机制自动把该桥排到本侧回路走完之后——与 Fleury「非不得已不过桥」
  的最小可行边规则逐条一致。

自环在邻接表中占两个槽（度数 +2），靠 `used` 标记去重；并联线靠
`(邻接接头, 跳线 id)` 双键区分，id 决定同终点时的先后。

**不枚举任何走线/排列**；穷举只存在于测试的参考实现中。
最坏情况 O(E log E) 排序 + O(V+E) 遍历，3000 跳线亚秒返回。

## 测试策略

- `tests/test_euler.py`
  - 独立的朴素参考实现：DFS 判连通、奇度判定、DFS **枚举全部完整走线**取真最小值；
  - 系统穷举：3 个接头、6 种边型（含自环）上 1–4 边的全部 209 个多重图
    （canonical id 与打乱 id/顺序两轮，共 418 个）；
  - 随机对拍：320 个 1–8 边随机短图（名字池刻意含 `J2/J10`、大小写混排、
    零度接头），结果必须与穷举参考逐项一致；
  - 手工临界用例：桥必须后置（领结/棒棒糖结构）、自环、并联 id 字节序、
    零度忽略、判定优先级、300/3000 上限性能冒烟。
- `tests/test_api.py`：三种 200 判定、录入顺序不变性、全部 422 边界、
  上下限批次、OpenAPI/健康检查。

## 目录

```
app/
  euler.py     # 纯图算法（无 Web 依赖）
  schemas.py   # 请求/响应模型与整批校验
  main.py      # FastAPI 路由
tests/         # pytest：对拍 + 接口边界
Dockerfile     # python:3.12-slim
docker-compose.yml
```
