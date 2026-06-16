# backend

基于 `FastAPI + AgentScope` 的新后端基础骨架。

当前目标是先搭建一个可启动、可扩展的后端壳，后续再把具体业务接口和 Agent 编排能力逐步接入。

## 已包含内容

- FastAPI 应用入口
- 配置管理与 `.env` 支持
- CORS 中间件
- 基础元信息接口与健康检查
- AgentScope 运行状态探测接口
- 最小测试用例

## 目录结构

```text
backend/
|-- pyproject.toml
|-- .env.example
|-- app/
|   |-- main.py
|   |-- config.py
|   |-- api/
|   |   |-- agentscope.py
|   |   |-- meta.py
|   |   `-- router.py
|   `-- services/
|       `-- agentscope_service.py
`-- tests/
    `-- test_app.py
```

## 快速开始

1. 检查环境变量

项目已经补了一个本地 `\.env`，默认走 `DashScope + qwen3.6-plus`。
如果你想切到 OpenAI 兼容模式，可以参考 `.env.example` 里的切换说明。

2. 安装或同步依赖

如果继续使用你当前的 `backend\.venv`，建议补齐 AgentScope 的 service extra 依赖：

```powershell
& ".\.venv\Scripts\pip.exe" install "agentscope[service]>=2.0.1"
```

如果还需要安装开发依赖，可以执行：

```powershell
& ".\.venv\Scripts\pip.exe" install -e ".[dev]"
```

如果后续改成 `uv` 管理，也可以直接基于 `pyproject.toml` 同步依赖。

3. 启动服务

```powershell
& ".\.venv\Scripts\python.exe" -m uvicorn app.main:app --reload
```

默认地址：`http://127.0.0.1:8000`

## 测试

运行当前最小测试集：

```powershell
& ".\.venv\Scripts\python.exe" -m pytest tests/test_app.py -q
```

运行全部测试：

```powershell
& ".\.venv\Scripts\python.exe" -m pytest -q
```

## 常用开发命令

安装开发依赖：

```powershell
& ".\.venv\Scripts\pip.exe" install -e ".[dev]"
```

启动开发服务：

```powershell
& ".\.venv\Scripts\python.exe" -m uvicorn app.main:app --reload
```

运行测试：

```powershell
& ".\.venv\Scripts\python.exe" -m pytest -q
```

运行 Ruff 检查：

```powershell
& ".\.venv\Scripts\python.exe" -m ruff check .
```

## 可用接口

- `GET /`
- `GET /healthz`
- `GET /api/v1/agentscope/status`

## 接口验证示例

检查根接口：

```powershell
Invoke-RestMethod -Uri "http://127.0.0.1:8000/"
```

检查健康状态：

```powershell
Invoke-RestMethod -Uri "http://127.0.0.1:8000/healthz"
```

检查 AgentScope 运行状态：

```powershell
Invoke-RestMethod -Uri "http://127.0.0.1:8000/api/v1/agentscope/status"
```

## 说明

- 你当前安装的 `agentscope==2.0.1` 缺少 `service` extra 依赖时，直接使用其内置 FastAPI service 组件会报缺少 `apscheduler`。
- 这个脚手架先把主应用结构和 AgentScope 适配层拆开，便于后面逐步接入实际 agent、会话、工具和工作区能力。
- 当前测试通过时可能会看到一条 `StarletteDeprecationWarning`，这是 `fastapi/starlette` 测试客户端上游依赖的告警，不影响当前服务启动与测试结果。
