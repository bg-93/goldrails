from goldrails_bench.regex_words import RegexWordClient
from goldrails_dataset.sources.f4_words import cases_for


def test_regex_baseline_matches_the_generated_cases_exactly():
    c = RegexWordClient(["project falcon"])
    for expected, kind, text in cases_for("project falcon"):
        got = c.ask(text, {"project_falcon": {}}).answers["project_falcon"]["noul"]
        assert (got == 1.0) == (expected == "yes"), (kind, text)


def test_regex_baseline_matches_the_heldout_family_exactly():
    from goldrails_dataset.sources.f4_words import heldout_cases_for
    for phrase in ("project falcon", "internal codename bluebird", "confidential roadmap"):
        c = RegexWordClient([phrase]); key = "".join(ch if ch.isalnum() else "_" for ch in phrase.lower()).strip("_")
        for expected, kind, text in heldout_cases_for(phrase):
            got = c.ask(text, {key: {}}).answers[key]["noul"]
            assert (got == 1.0) == (expected == "yes"), (phrase, kind, text)


def test_regex_baseline_matches_the_scaled_frames_exactly():
    from goldrails_dataset.sources.f4_words import scaled_cases_for
    for phrase in ("project falcon", "internal codename bluebird", "acme secret sauce", "confidential roadmap"):
        c = RegexWordClient([phrase]); key = "".join(ch if ch.isalnum() else "_" for ch in phrase.lower()).strip("_")
        for expected, kind, i, text in scaled_cases_for(phrase):
            assert (c.ask(text, {key: {}}).answers[key]["noul"] == 1.0) == (expected == "yes"), (phrase, kind, text)
