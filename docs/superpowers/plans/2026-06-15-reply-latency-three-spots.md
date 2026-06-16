# 优化回复链路三处:连接复用 + SSE 非阻塞 + 收尾延迟

聚焦用户点名的三处:gateway 转发 POST、SessionMessageService.send、gateway SSE 推送。
全部纯代码改动,无 schema 迁移。

## 处③ SSE 并发 bug(最高优先级,是 bug 不是慢)

`gateway_service/app/api/session_stream.py:42`
```python
async def iterator():
    events = client.list_session_events(...)   # 同步阻塞 httpx 在 async 协程里
```
**问题**:async 协程里跑同步阻塞 IO,每次轮询卡死 uvicorn 事件循环,一个 SSE 连接
拖慢所有并发请求。

**修复**:用 `starlette.concurrency.run_in_threadpool` 把同步调用挪到线程池,
不阻塞事件循环:
```python
from starlette.concurrency import run_in_threadpool
events = await run_in_threadpool(client.list_session_events, session_id, since=last_seq)
```
最小改动、复用现有同步 client,彻底解决阻塞。

## 处① gateway → agent_service 连接复用

`gateway_service/app/client/agent_service_client.py:19`
```python
def _client(self): return httpx.Client(...)   # 每次调用新建 TCP 连接
```
**问题**:每个 gateway→agent 请求新建连接 + 握手。SSE 高频轮询尤其浪费
(每 0.3~0.8s 建一次连接)。

**修复**:模块级单例 `httpx.Client`(连接池 + keep-alive),所有 `AgentServiceClient`
实例共享:
```python
_SHARED_CLIENT: httpx.Client | None = None

def _get_shared_client(base_url, timeout) -> httpx.Client:
    global _SHARED_CLIENT
    if _SHARED_CLIENT is None:
        _SHARED_CLIENT = httpx.Client(
            base_url=base_url, timeout=timeout,
            limits=httpx.Limits(max_keepalive_connections=20, max_connections=40),
        )
    return _SHARED_CLIENT
```
- `_get`/`_post` 用共享 client,**不再** `with ... :` 关闭(连接归还连接池而非关闭)。
- 保留构造参数 `base_url`/`timeout` 兼容现有调用;单例按首次配置创建。
- 测试注入:`_client()` 工厂保留,可被替换(现有测试若 mock `_client` 仍可用)。
- app 关闭时不强制关——进程退出即释放;或在 gateway main 加 shutdown 钩子关闭(可选)。

处①②③ 全部受益(send 的转发、SSE 的轮询、所有读代理)。

## 处② SessionMessageService.send 的 run 解析

`agent_run_repository.py:32 list_by_session_id` 全表扫 + 全量反序列化。
`send` → `_resolve_run_id` 每次发消息都走这条。

**这轮的低风险优化**:不动 schema,改为复用连接(随处①一并受益)。
全表扫本身在小数据量下是微秒级,**不是当前主要瓶颈**,暂不加索引列
(避免 ALTER TABLE 迁移风险)。

> 说明:真正的大头是 LLM 调用本身(整段生成,可能多轮工具循环),那是模型/网络
> 决定的,后端链路优化压不动。本轮三处优化解决的是"链路开销"和"SSE 尾延迟+阻塞",
> 不会让 LLM 本身变快。

## 处③补 SSE 收尾延迟

`session_stream.py` idle 间隔 2.0s → 回复产生后最多白等 2s。
**修复**:`STREAM_IDLE_INTERVAL` 2.0 → 0.8s(轮询变密但每次已是连接池+线程池,开销小);
保留空轮退避上限避免长挂。

## 不做(本轮范围外)
- domain_events/agent_runs 加索引列(需 ALTER 迁移;事件量小,收益微秒级,以后再做)
- LLM token 级流式(已确认不做打字机)
- orchestrator 多轮工具循环本身的优化(属 agent 行为,非链路)

## 验证
1. `uv run pytest`(gateway + agent_service),重点确认:
   - SSE 测试(若有)仍通过;client 连接复用不破坏现有 mock。
   - session_message / read_proxy 相关测试绿。
2. 手测:发消息 → POST 快速返回 → 回复经 SSE 到达延迟变小;多开几个会话并发不互相卡。
3. gateway lint 不适用(Python),跑 ruff/现有检查(若配置)。

## 提交
- commit 1: fix(gateway) SSE 用 run_in_threadpool 解除事件循环阻塞
- commit 2: perf(gateway) AgentServiceClient 连接池复用 + SSE idle 间隔下调
