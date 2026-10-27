"""Content-free, bounded timing for one streamed agent turn."""

import time

from agents import RunHooks


class TurnTiming(RunHooks):
    def __init__(self):
        self.started = time.monotonic()
        self.first_delta_ms = -1
        self.first_spoken_delta_ms = -1
        self.db_ready_ms = -1
        self.models = []
        self.tools = []
        self.event_model = -1
        self.decision = None

    def elapsed(self):
        return round((time.monotonic() - self.started) * 1000)

    async def on_llm_start(self, context, agent, system_prompt, input_items):
        self.models.append(
            {
                "start_ms": self.elapsed(),
                "end_ms": -1,
                "first_text_ms": -1,
                "input_tokens": -1,
                "cached_tokens": -1,
                "output_tokens": -1,
            }
        )

    async def on_llm_end(self, context, agent, response):
        self.models[-1]["end_ms"] = self.elapsed()

    async def on_tool_start(self, context, agent, tool):
        # Tool names are application-owned; never retain arguments or returned data.
        self.tools.append(
            {
                "name": tool.name
                if tool.name in {"take_note", "finish_call", "respond"}
                else "unknown",
                "start_ms": self.elapsed(),
                "end_ms": -1,
            }
        )

    async def on_tool_end(self, context, agent, tool, result):
        self.tools[-1]["end_ms"] = self.elapsed()

    def observe(self, data):
        if data.type == "response.created":
            self.event_model += 1
        if data.type == "response.output_text.delta" and data.delta:
            if self.first_delta_ms < 0:
                self.first_delta_ms = self.elapsed()
            if 0 <= self.event_model < len(self.models):
                step = self.models[self.event_model]
                if step["first_text_ms"] < 0:
                    step["first_text_ms"] = self.elapsed()
        if data.type == "response.completed" and 0 <= self.event_model < len(self.models):
            usage = data.response.usage
            if usage is not None:
                step = self.models[self.event_model]
                details = usage.input_tokens_details
                for name, value in {
                    "input_tokens": usage.input_tokens,
                    "output_tokens": usage.output_tokens,
                    "cached_tokens": getattr(details, "cached_tokens", None),
                }.items():
                    step[name] = value if type(value) is int and value >= 0 else -1

    def spoken(self):
        if self.first_spoken_delta_ms < 0:
            self.first_spoken_delta_ms = self.elapsed()

    def snapshot(self):
        return {
            **({"decision_shadow": self.decision} if self.decision is not None else {}),
            "db_ready_ms": self.db_ready_ms,
            "first_delta_ms": self.first_delta_ms,
            "first_spoken_delta_ms": self.first_spoken_delta_ms,
            "model_steps": self.models,
            "tools": self.tools,
        }
