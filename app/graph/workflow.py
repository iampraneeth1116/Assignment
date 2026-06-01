"""
workflow.py
-----------
Pipeline Orchestrator for the Maverick multi-agent workflow.

Design Pattern: Pipeline Orchestrator with shared state dict passed through
each agent stage.

AgentScope (v0.1.5) is used for its SequentialPipeline orchestration
primitive. Each Maverick agent is wrapped into an AgentScope-compatible
callable that:
  1. Deserialises the shared state from ``Msg.metadata``
  2. Calls the corresponding Pydantic agent (email / memory / logistics /
     council), which mutates the state in-place
  3. Serialises the updated state back into a new ``Msg.metadata`` and
     returns it to the pipeline

AgentScope is initialised at module import time with a dummy placeholder
model config (Maverick agents call Groq directly; AgentScope is **not**
used as a model gateway here — only as a pipeline orchestrator).
"""

from __future__ import annotations

import warnings

# ── Suppress agentscope's google-generativeai deprecation warning ──────────
warnings.filterwarnings("ignore", category=FutureWarning, module="agentscope")

import agentscope
from agentscope.message import Msg
from agentscope.pipelines import SequentialPipeline

from app.agents import email_agent, memory_agent, logistics_agent, council_agent
from app.audit.audit_log import AuditLog

# ---------------------------------------------------------------------------
# Initialise AgentScope at module level
# ---------------------------------------------------------------------------
# We supply a dummy OpenAI-compatible config so AgentScope can initialise
# without errors.  Maverick agents bypass AgentScope's model layer entirely
# and hit Groq directly via the groq SDK.
agentscope.init(
    model_configs=[
        {
            "model_type": "openai_chat",
            "config_name": "maverick_placeholder",
            "model_name": "gpt-4o-mini",          # never actually called
            "api_key": "placeholder_not_used",
        }
    ],
    project="maverick",
    disable_saving=True,       # don't write run logs to disk
    use_monitor=False,         # no token-usage monitor needed
    logger_level="WARNING",    # suppress verbose AgentScope INFO logs
)

_ORCHESTRATOR_NAME = "workflow_orchestrator"


# ---------------------------------------------------------------------------
# AgentScope-compatible stage wrappers
# ---------------------------------------------------------------------------
# Each wrapper receives a Msg whose `metadata` carries the shared state dict.
# It calls the underlying Pydantic agent, appends to stages_completed, and
# returns a new Msg with the updated state in metadata.

def _stage_email(msg: Msg) -> Msg:
    """Stage 1 — email_agent: parse the raw caregiving email."""
    state: dict = dict(msg.metadata)  # shallow copy
    email_agent.run(state)
    state["stages_completed"].append("email_analysis complete")
    return Msg(
        name="email_agent",
        content="email_analysis complete",
        role="assistant",
        metadata=state,
    )


def _stage_memory(msg: Msg) -> Msg:
    """Stage 2 — memory_agent: retrieve and synthesise stored context."""
    state: dict = dict(msg.metadata)
    memory_agent.run(state)
    state["stages_completed"].append("memory_context complete")
    return Msg(
        name="memory_agent",
        content="memory_context complete",
        role="assistant",
        metadata=state,
    )


def _stage_logistics(msg: Msg) -> Msg:
    """Stage 3 — logistics_agent: analyse scheduling conflicts & transport."""
    state: dict = dict(msg.metadata)
    logistics_agent.run(state)
    state["stages_completed"].append("logistics_analysis complete")
    return Msg(
        name="logistics_agent",
        content="logistics_analysis complete",
        role="assistant",
        metadata=state,
    )


def _stage_council(msg: Msg) -> Msg:
    """Stage 4 — council_agent: deliberate and produce final recommendation."""
    state: dict = dict(msg.metadata)
    council_agent.run(state)
    state["stages_completed"].append("council_recommendation complete")
    return Msg(
        name="council_agent",
        content="council_recommendation complete",
        role="assistant",
        metadata=state,
    )


# ---------------------------------------------------------------------------
# MaverickWorkflow orchestrator class
# ---------------------------------------------------------------------------

class MaverickWorkflow:
    """
    Pipeline Orchestrator for the Maverick care-coordination system.

    Uses AgentScope's ``SequentialPipeline`` to execute four specialist
    agents in order, each operating on a shared state dictionary that is
    threaded through the pipeline via ``Msg.metadata``.

    Human-approval workflow
    -----------------------
    When ``require_approval=True`` the pipeline pauses after the logistics
    stage and returns the intermediate state with ``status="awaiting_approval"``.
    Call :meth:`approve_and_continue` with that state to resume from the
    council deliberation step.
    """

    def __init__(self) -> None:
        self._audit = AuditLog()

        # Pre-stage pipeline (email → memory → logistics)
        self._pre_pipeline = SequentialPipeline(
            [_stage_email, _stage_memory, _stage_logistics]
        )

        # Full pipeline (email → memory → logistics → council)
        self._full_pipeline = SequentialPipeline(
            [_stage_email, _stage_memory, _stage_logistics, _stage_council]
        )

        # Council-only pipeline (used when resuming after approval)
        self._council_pipeline = SequentialPipeline([_stage_council])

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def run(self, raw_email: str, require_approval: bool = False) -> dict:
        """
        Execute the agent pipeline for an incoming caregiving email.

        Parameters
        ----------
        raw_email:
            The raw text of the caregiving email to process.
        require_approval:
            If ``True``, the pipeline pauses before the council step and
            returns a state with ``status="awaiting_approval"``.  Call
            :meth:`approve_and_continue` to resume.

        Returns
        -------
        dict
            The completed shared state dict containing all agent outputs
            plus ``status`` and ``stages_completed``.
        """
        state: dict = {
            "raw_email": raw_email,
            "status": "running",
            "stages_completed": [],
        }

        self._audit.log(
            agent_name=_ORCHESTRATOR_NAME,
            input_summary=f"Starting pipeline for email ({len(raw_email)} chars)",
            output_summary="pipeline started",
            status="running",
        )

        if require_approval:
            # ── Run only the first three stages ──────────────────────────
            state = self._run_pre_pipeline(state)
            if state["status"] == "failed":
                return state
            state["status"] = "awaiting_approval"
            self._audit.log(
                agent_name=_ORCHESTRATOR_NAME,
                input_summary="Pre-approval pipeline complete",
                output_summary="awaiting_approval — paused before council",
                status="running",
            )
            return state

        # ── Run the full four-stage pipeline ─────────────────────────────
        state = self._run_full_pipeline(state)
        return state

    def approve_and_continue(self, state: dict) -> dict:
        """
        Resume the pipeline from the council agent step after human approval.

        Parameters
        ----------
        state:
            The intermediate state dict returned by :meth:`run` when
            ``require_approval=True``.  Must have
            ``status="awaiting_approval"``.

        Returns
        -------
        dict
            The completed shared state dict after council deliberation.
        """
        if state.get("status") != "awaiting_approval":
            raise ValueError(
                f"Expected state with status='awaiting_approval', "
                f"got '{state.get('status')}'"
            )

        state["status"] = "running"

        self._audit.log(
            agent_name=_ORCHESTRATOR_NAME,
            input_summary="Human approval granted — resuming council stage",
            output_summary="resuming",
            status="running",
        )

        try:
            init_msg = Msg(
                name="orchestrator",
                content="approved — run council",
                role="user",
                metadata=state,
            )
            result_msg = self._council_pipeline(init_msg)
            state = dict(result_msg.metadata)
            state["status"] = "completed"

            self._audit.log(
                agent_name=_ORCHESTRATOR_NAME,
                input_summary="Council stage completed after approval",
                output_summary=f"stages={state['stages_completed']}",
                status="success",
            )

        except Exception as exc:  # noqa: BLE001
            state["status"] = "failed"
            state["error"] = str(exc)
            self._audit.log(
                agent_name=_ORCHESTRATOR_NAME,
                input_summary="Council stage failed after approval",
                output_summary=f"ERROR: {exc}",
                status="error",
            )

        return state

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _run_pre_pipeline(self, state: dict) -> dict:
        """Run email → memory → logistics stages only."""
        try:
            init_msg = Msg(
                name="orchestrator",
                content=state["raw_email"][:120] + "...",
                role="user",
                metadata=state,
            )
            result_msg = self._pre_pipeline(init_msg)
            return dict(result_msg.metadata)
        except Exception as exc:  # noqa: BLE001
            state["status"] = "failed"
            state["error"] = str(exc)
            self._audit.log(
                agent_name=_ORCHESTRATOR_NAME,
                input_summary="Pre-pipeline stage failed",
                output_summary=f"ERROR: {exc}",
                status="error",
            )
            return state

    def _run_full_pipeline(self, state: dict) -> dict:
        """Run all four stages (email → memory → logistics → council)."""
        try:
            init_msg = Msg(
                name="orchestrator",
                content=state["raw_email"][:120] + "...",
                role="user",
                metadata=state,
            )
            result_msg = self._full_pipeline(init_msg)
            state = dict(result_msg.metadata)
            state["status"] = "completed"

            self._audit.log(
                agent_name=_ORCHESTRATOR_NAME,
                input_summary="Full pipeline completed",
                output_summary=f"stages={state['stages_completed']}",
                status="success",
            )

        except Exception as exc:  # noqa: BLE001
            state["status"] = "failed"
            state["error"] = str(exc)
            self._audit.log(
                agent_name=_ORCHESTRATOR_NAME,
                input_summary="Full pipeline failed",
                output_summary=f"ERROR: {exc}",
                status="error",
            )

        return state


# ---------------------------------------------------------------------------
# Public run_workflow() — used by the FastAPI API layer
# ---------------------------------------------------------------------------

def run_workflow(query: str) -> dict:
    """
    Entry point called by the API layer (routes.py).

    Wraps ``MaverickWorkflow.run()`` and reformats the final state into the
    ``{response, agents_used, details}`` shape expected by ``QueryResponse``.

    Parameters
    ----------
    query:
        Patrick's natural-language request or the raw caregiving email text.

    Returns
    -------
    dict with ``response`` (str), ``agents_used`` (list[str]), and
    ``details`` (dict).
    """
    workflow = MaverickWorkflow()
    state = workflow.run(raw_email=query)

    if state.get("status") == "failed":
        return {
            "response": f"Pipeline error: {state.get('error', 'unknown')}",
            "agents_used": state.get("stages_completed", []),
            "details": state,
        }

    # ── Build a human-readable markdown response from council output ─────
    rec = state.get("council_recommendation") or {}
    recommendation = rec.get("recommendation", "No recommendation provided.")

    response_parts = [recommendation]

    if rec.get("reasoning"):
        response_parts.append(
            "**Reasoning:**\n" + "\n".join(f"- {r}" for r in rec["reasoning"])
        )

    if rec.get("tradeoffs"):
        response_parts.append(
            "**Tradeoffs:**\n" + "\n".join(f"- {r}" for r in rec["tradeoffs"])
        )

    if rec.get("priority_actions"):
        response_parts.append(
            "**Priority Next Steps:**\n"
            + "\n".join(f"{i + 1}. {a}" for i, a in enumerate(rec["priority_actions"]))
        )

    final_response = "\n\n".join(response_parts)

    return {
        "response": final_response,
        "agents_used": ["email_agent", "memory_agent", "logistics_agent", "council_agent"],
        "details": {
            "email_analysis": state.get("email_analysis"),
            "memory_context": state.get("memory_context"),
            "logistics_analysis": state.get("logistics_analysis"),
            "council_recommendation": state.get("council_recommendation"),
            "stages_completed": state.get("stages_completed"),
            "pipeline_status": state.get("status"),
        },
    }
