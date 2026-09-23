# 临时展馆布线核验 API

纯后端服务，用于判断一组无向测试跳线是否存在一条从规定接头出发、经过每根跳线恰好一次的完整检查走线（Euler trail）。服务基于 Python 3.12、FastAPI、Pydantic 与 Uvicorn。

## 规则

- 输入 1 至 300 个唯一 ASCII 接头、1 至 3000 根唯一 id 的无向跳线。
- 允许自环（`u == v`）和相同端点之间的并联线。
- 未知接头、重复接头值、重复跳线 id 等整批请求均返回 `422 Unprocessable Entity`。
- 先忽略零度接头，只检查“有边部分”的连通性；连通性失败优先于奇度失败。
- 连通后，奇度接头数量必须为 0 或 2。
- 可行时：
  - 有 2 个奇度接头：起点固定为 UTF-8 字节序最小的奇度接头；
  - 没有奇度接头：起点固定为 UTF-8 字节序最小的有边接头。
- 走线排序先比较接头序列，再比较跳线 id 序列，均按 UTF-8 字节序。
- 算法采用 Fleury 与动态桥检测，不枚举排列；短图测试使用穷举对拍。

## 启动服务

```bash
docker compose up --build
```

服务默认监听 `http://localhost:8000`。

健康检查：

```bash
curl http://localhost:8000/health
```

## API

### `POST /api/verify`

请求体：

```json
{
  "connectors": ["A", "B", "C"],
  "jumpers": [
    {"id": "j1", "u": "A", "v": "B"},
    {"id": "j2", "u": "B", "v": "C"},
    {"id": "j3", "u": "C", "v": "A"}
  ]
}
```

#### 可行响应 `200`

```json
{
  "status": "FEASIBLE",
  "start": "A",
  "connectors": ["A", "B", "C", "A"],
  "jumper_ids": ["j1", "j2", "j3"]
}
```

`connectors` 比 `jumper_ids` 多一个元素；自环表现为相邻两个接头相同。

#### 有边部分不连通 `200`

```json
{
  "status": "DISCONNECTED",
  "connector": "A",
  "other_connector": "C"
}
```

字段给出两个不同有边连通分量中最小的接头，可直接定位断开的区域。

#### 奇度接头数量不是 0 或 2：`200`

```json
{
  "status": "ODD_DEGREE",
  "connectors": ["A", "C", "E", "F"]
}
```

连通性检查优先；只有有边部分连通时才会返回奇度失败。

#### 请求数据错误：`422`

典型情况包括：

- 接头或跳线数量越界；
- 接头重复、非 ASCII、不是字符串；
- 跳线 id 重复；
- 跳线端点不在 `connectors` 中；
- 必填字段缺失、字段类型错误、存在未知字段、JSON 格式错误。

## 本地开发与测试

```bash
python3.12 -m venv .venv
. .venv/bin/activate
pip install -r requirements-dev.txt
pytest
```

测试覆盖：

- 单跳线、自环、并联线、回路和桥边；
- 零度接头忽略；
- `DISCONNECTED` 与 `ODD_DEGREE` 的优先级和定位字段；
- 输入校验与 FastAPI 422 边界；
- 300 个随机小图对穷举搜索做对拍，验证字节序最小走线。
