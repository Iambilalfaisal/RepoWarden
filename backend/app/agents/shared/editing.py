from pathlib import Path

from pydantic import BaseModel, Field

from app.core.fs_safety import (
    PATH_FIELD_DESCRIPTION,
    FsSafetyError,
    MAX_READ_CHARS_FOR_LLM,
    read_text_file,
)


class FileEdit(BaseModel):
    file_name: str
    explanation: str
    original_code: str
    proposed_code: str


class FileEditInput(BaseModel):
    path: str = Field(description=PATH_FIELD_DESCRIPTION)
    explanation: str = Field(
        description="Plain-language summary of what changed in this file and why."
    )
    proposed_code: str = Field(
        description="The COMPLETE new content for the file — not a fragment or diff."
    )


def build_file_edit(root: Path, path: str, explanation: str, proposed_code: str) -> FileEdit:
    """Shared by propose_edit (reviewer) and write_file (editor) — packages
    a FileEdit for display. The model supplies proposed_code itself (it
    already read the file via read_file and reasoned about the change as
    part of its own turn — no nested LLM call here). original_code is
    always re-read from disk rather than trusted from the model, so the
    diff shown to the user stays byte-accurate even if the model's own
    recollection of the file drifted."""
    try:
        original_code = read_text_file(root, path, max_chars=MAX_READ_CHARS_FOR_LLM)
    except FsSafetyError:
        original_code = ""
    return FileEdit(
        file_name=path,
        explanation=explanation,
        original_code=original_code,
        proposed_code=proposed_code,
    )
