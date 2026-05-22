# backend-python

基于 `uv + FastAPI` 的 Python 服务脚手架，提供了一个可直接启动的 API 服务入口、基础配置和健康检查接口。

## 环境要求

- `uv >= 0.6`
- 首次同步依赖时由 `uv` 自动管理 Python `3.11`

## 快速开始

```bash
copy .env.example .env
uv sync
uv run fastapi dev app/main.py
```

服务默认地址为 `http://127.0.0.1:8000`。

## 常用命令

```bash
uv run pytest
uv run ruff check .
uv run fastapi run app/main.py
```

## 接口说明

- `GET /`: 返回服务名称和运行环境
- `GET /healthz`: 返回健康检查结果

## 目录结构

```text
backend-python/
|-- pyproject.toml
|-- .env.example
|-- app/
|   |-- main.py
|   |-- config.py
|   |-- api/
|   |-- agents/
|   |-- skills/
|   |-- frameworks/
|   |   |-- claude_code_adapter/
|   |   `-- codex_adapter/
|   |-- services/
|   `-- schemas/
`-- tests/
    `-- test_app.py
```
