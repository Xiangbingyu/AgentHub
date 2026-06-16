from __future__ import annotations

from agentscope.event import ConfirmResult, UserConfirmResultEvent


class ConfirmRuntime:
    def build_confirm_event(
        self,
        reply_id: str,
        confirmed: bool,
        tool_call,
    ) -> UserConfirmResultEvent:
        return UserConfirmResultEvent(
            reply_id=reply_id,
            confirm_results=[
                ConfirmResult(
                    confirmed=confirmed,
                    tool_call=tool_call,
                    rules=tool_call.suggested_rules,
                ),
            ],
        )
