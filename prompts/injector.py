def inject_prompt(template: str, memories: list[str], message: str) -> str:
    """Build the final prompt by combining system template, memory context, and user message.

    Format: [SYSTEM]\n{template}\n\n[CONTEXT]\n{context}\n\n[USER]\n{message}

    If memories is empty, use "No previous context." as the context.
    """
    context = "\n".join(memories) if memories else "No previous context."
    return f"[SYSTEM]\n{template}\n\n[CONTEXT]\n{context}\n\n[USER]\n{message}"


def build_adaptive_prompt(
    strategy: dict, message: str, memories: list[str]
) -> str:
    """Build prompt using full UXStrategy instead of bare ux_mode.

    Richer than existing inject_prompt(). Called by graph nodes
    when UXStrategy is available.

    Args:
        strategy: UXStrategy as dict.
        message: User's message.
        memories: List of memory context strings.

    Returns:
        Formatted prompt string with adaptive modifiers.
    """
    from prompts.templates import TEMPLATES

    ux_mode = strategy.get("ux_mode", "normal")
    tone = strategy.get("response_tone", "neutral")
    verbosity = strategy.get("verbosity_level", "normal")
    suggest_break = strategy.get("suggest_break", False)
    cog_reduction = strategy.get("cognitive_load_reduction", False)
    reasoning = strategy.get("reasoning", [])

    template = TEMPLATES.get(ux_mode, TEMPLATES["normal"])

    modifiers: list[str] = []
    if cog_reduction:
        modifiers.append("Use simple sentences. No bullet points. No lists.")
    if suggest_break:
        modifiers.append(
            "Gently suggest taking a short break if appropriate."
        )
    if tone == "warm":
        modifiers.append("Use a warm, empathetic tone.")
    if tone == "technical":
        modifiers.append("Be precise and technical. Skip pleasantries.")
    if verbosity == "minimal":
        modifiers.append("Maximum 2 sentences.")
    if verbosity == "short":
        modifiers.append("Maximum 3-4 sentences.")

    modifier_block = "\n".join(modifiers) if modifiers else "No additional modifiers."
    memory_block = "\n".join(memories) if memories else "No prior context."
    reasoning_block = " | ".join(reasoning[:3]) if reasoning else ""

    return (
        f"[SYSTEM]\n{template}"
        f"\n\n[ADAPTIVE MODIFIERS]\n{modifier_block}"
        f"\n\n[ORCHESTRATION REASONING]\n{reasoning_block}"
        f"\n\n[CONTEXT]\n{memory_block}"
        f"\n\n[USER]\n{message}"
    )
