from pydantic import BaseModel
from models.human_state import HumanState


class AdaptiveResponse(BaseModel):
    reply: str
    human_state: HumanState
    ux_mode: str
    memory_anchors: list[str]
    response_metadata: dict
