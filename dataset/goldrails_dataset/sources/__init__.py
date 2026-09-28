from . import nemotron_pii, bias_pairs_reviewed, civil_comments_profanity, f2_indirect_controls, f3_test_candidates, bbq, civil_comments_identity, discrim_eval, f3_controls_v2, holistic_bias, llmail_inject, ai4privacy, f3_controls, f4_words, ragtruth, f5_controls, jbb_artifacts, f2_controls, aegis2, ailuminate_demo, deepset_injections, gandalf, jailbreakbench, openai_moderation, orbench

SOURCES = {
    "aegis2": aegis2, "ailuminate_demo": ailuminate_demo, "orbench": orbench,
    "jailbreakbench": jailbreakbench, "deepset_injections": deepset_injections,
    "gandalf": gandalf, "openai_moderation": openai_moderation, "f2_controls": f2_controls,
    "jbb_artifacts": jbb_artifacts, "ai4privacy": ai4privacy, "nemotron_pii": nemotron_pii, "f5_controls": f5_controls,
    "f3_controls": f3_controls, "f4_words": f4_words, "ragtruth": ragtruth,
    # registered so they can be loaded and audited; not in PILOT_PLAN until the pending decisions in docs/19-21 are made
    "llmail_inject": llmail_inject, "f2_indirect_controls": f2_indirect_controls, "f3_test_candidates": f3_test_candidates, "f3_controls_v2": f3_controls_v2, "civil_comments_identity": civil_comments_identity,
    "holistic_bias": holistic_bias, "discrim_eval": discrim_eval, "bbq": bbq,
    "bias_pairs_reviewed": bias_pairs_reviewed, "civil_comments_profanity": civil_comments_profanity,
}
