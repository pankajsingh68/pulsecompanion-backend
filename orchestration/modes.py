"""UX mode constants and token limit mappings."""


class UXMode:
    NORMAL = "normal"
    CALM_MINIMAL = "calm_minimal"
    FOCUS_MODE = "focus_mode"
    OVERLOAD_PROTECTION = "overload_protection"


NUM_PREDICT_MAP: dict[str, int] = {
    UXMode.OVERLOAD_PROTECTION: 100,
    UXMode.CALM_MINIMAL: 200,
    UXMode.FOCUS_MODE: 300,
    UXMode.NORMAL: 512,
}
