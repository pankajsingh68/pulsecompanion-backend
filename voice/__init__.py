"""Phase 6 — Real-Time Empathic Voice Runtime.

New layer on top of existing infrastructure. Does not modify anything outside voice/.
"""

from voice.voice_pipeline import run_voice_session

__all__ = ["run_voice_session"]
