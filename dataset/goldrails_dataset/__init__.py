"""Gold Rails: a guardrail benchmark dataset for decision models."""
__version__ = "0.0.1"
FEATURES = ("F1", "F2", "F3", "F4", "F5", "F6", "F7", "F8")
SUBTASKS = {
    "F1": ("input", "output", "over_refusal", "harmful_goal"),   # harmful_goal: plain harmful/benign requests (JailbreakBench goals), no attack technique
    "F2": ("jailbreak", "injection", "leakage", "indirect"),
    "F3": ("topic", "policy"),
    "F4": ("word", "profanity", "profanity_obfuscated"),   # profanity_obfuscated: diagnostic only, never in the suite score
    "F5": ("pii", "secret"),
    "F6": ("grounding", "relevance"),
    "F7": ("b1_disparate_fpr", "b2_counterfactual", "b3_decision"),
    "F8": ("action",),
}
