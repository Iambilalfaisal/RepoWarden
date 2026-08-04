from functools import lru_cache

from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import Runnable

from app.agents.llm import build_llm
from app.agents.schemas import PlanSummary

# A real LCEL chain (prompt | structured-output model), separate from the
# main tool-calling agent loop: the Reviewer's own turn already produces
# structured tool-call args for its findings/edits, but its final plan is
# just free streamed text. This one extra call turns that into something
# the approval UI can key off directly (risk level, affected files) instead
# of parsing prose.
SUMMARY_PROMPT = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            "You are summarizing one code-review turn for a human who is "
            "about to decide whether to authorize the proposed changes. "
            "Given the findings and proposed file edits below, produce a "
            "concise, structured risk summary: the single most severe risk "
            "level across every finding, every file with a proposed edit, "
            "and a one-sentence headline a human can read at a glance.",
        ),
        (
            "human",
            "Findings and proposed edits from this review turn:\n\n{transcript}",
        ),
    ]
)


@lru_cache(maxsize=1)
def build_plan_summary_chain() -> Runnable:
    return SUMMARY_PROMPT | build_llm().with_structured_output(PlanSummary)
