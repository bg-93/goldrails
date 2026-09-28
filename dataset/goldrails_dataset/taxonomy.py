"""One taxonomy for every source: the 12 MLCommons AILuminate hazards plus three
non-hazard labels the guardrail surface needs, and the Bedrock category each
maps to. Mappings are many-to-one and are a design decision, versioned here.
"""

AILUMINATE = {
    "vcr": "violent_crimes", "ncr": "nonviolent_crimes", "src": "sex_related_crimes",
    "cse": "child_sexual_exploitation", "iwp": "indiscriminate_weapons", "ssh": "suicide_self_harm",
    "ipv": "intellectual_property", "prv": "privacy", "dfm": "defamation", "hte": "hate",
    "sxc_prn": "sexual_content", "spc_fin": "specialized_advice", "spc_hlt": "specialized_advice",
    "spc_ele": "specialized_advice", "spc_lgl": "specialized_advice",
}
EXTRA = ("injection", "pii", "unsafe_action", "benign")

AILUMINATE_TO_BEDROCK = {
    "violent_crimes": "VIOLENCE", "nonviolent_crimes": "MISCONDUCT", "sex_related_crimes": "SEXUAL",
    "child_sexual_exploitation": "SEXUAL", "indiscriminate_weapons": "MISCONDUCT",
    "suicide_self_harm": "VIOLENCE", "intellectual_property": "MISCONDUCT", "privacy": "PII",
    "defamation": "INSULTS", "hate": "HATE", "sexual_content": "SEXUAL", "specialized_advice": "TOPIC",
    "injection": "PROMPT_ATTACK", "pii": "PII", "unsafe_action": "NONE", "benign": "NONE",
}

# Aegis 2.0 violated_categories -> AILuminate. First match wins when a row lists several.
AEGIS2 = {
    "Hate/Identity Hate": "hate", "Harassment": "hate", "Profanity": "hate",
    "Violence": "violent_crimes", "Threat": "violent_crimes", "Guns and Illegal Weapons": "indiscriminate_weapons",
    "Sexual": "sexual_content", "Sexual (minor)": "child_sexual_exploitation",
    "Suicide and Self Harm": "suicide_self_harm", "Criminal Planning/Confessions": "nonviolent_crimes",
    "Controlled/Regulated Substances": "nonviolent_crimes", "PII/Privacy": "privacy",
    "Copyright/Trademark/Plagiarism": "intellectual_property",
    "Political/Misinformation/Conspiracy": "defamation", "Manipulation": "nonviolent_crimes",
    "Fraud/Deception": "nonviolent_crimes", "Illegal Activity": "nonviolent_crimes",
    "Unauthorized Advice": "specialized_advice", "Other": None, "Needs Caution": None,
}

# JailbreakBench Category -> AILuminate
JBB = {
    "Harassment/Discrimination": "hate", "Malware/Hacking": "nonviolent_crimes",
    "Physical harm": "violent_crimes", "Economic harm": "nonviolent_crimes", "Fraud/Deception": "nonviolent_crimes",
    "Disinformation": "defamation", "Sexual/Adult content": "sexual_content", "Privacy": "privacy",
    "Expert advice": "specialized_advice", "Government decision-making": "nonviolent_crimes",
}

# OpenAI 2022 moderation eval columns -> AILuminate
OPENAI_MOD = {"S": "sexual_content", "H": "hate", "V": "violent_crimes", "HR": "hate",
              "SH": "suicide_self_harm", "S3": "child_sexual_exploitation", "H2": "hate", "V2": "violent_crimes"}

# OR-Bench categories are the topic the benign prompt looks like; keep as source_label only.


def bedrock_for(ailuminate: str | None) -> str | None:
    if ailuminate is None:
        return None
    return AILUMINATE_TO_BEDROCK.get(ailuminate, "NONE")
