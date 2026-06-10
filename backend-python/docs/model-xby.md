class AgentRunModel(BaseModel):
    run_id: UUID
    agent_id: UUID
    role: str | None = None
    agent_kind: str
    workspace_id: UUID
    parent_run_id: UUID | None = None
    root_run_id: UUID | None = None
    status: str = "created"
    plan_path: str = "PLAN.md"
    context_snapshot: dict[str, Any] = Field(default_factory=dict)
    runtime_snapshot: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class AgentModel(BaseModel):
    agent_id: UUID
    agent_name: str
    role: Literal["orchestrator", "worker"] | None = None
    agent_kind: Literal["orchestrator", "worker"] | None = None
    prompt_policy: dict[str, Any] = Field(default_factory=dict)
    tool_policy: dict[str, Any] = Field(default_factory=dict)
    executor_policy: dict[str, Any] = Field(default_factory=dict)
    status: str = "active"
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class InputEventModel(BaseModel):
    input_id: UUID
    run_id: UUID
    type: InputEventType
    payload: dict[str, Any] = Field(default_factory=dict)
    idempotency_key: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class PlanModel(BaseModel):
    plan_id: UUID
    run_id: UUID
    workspace_id: UUID
    raw_document: str = ""
    file_path: str = ""
    title: str = ""
    goal: str = ""
    status: str = "pending"
    summary: str = ""
    steps: list[dict[str, Any]] = Field(default_factory=list)
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class SubtaskModel(BaseModel):
    subtask_id: UUID
    root_run_id: UUID
    parent_run_id: UUID
    worker_run_id: UUID | None = None
    status: str = "created"
    task_prompt: str = ""
    result_ref: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
