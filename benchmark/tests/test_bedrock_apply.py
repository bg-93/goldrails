from goldrails_bench.bedrock_apply import BedrockApplyClient, content_of

CFG = {"region": "us-east-1",
       "topics": {"id": "t", "version": "1", "topics": ["InvestmentAdvice", "LegalAdvice"]},
       "words": {"id": "w", "version": "1", "words": ["project falcon", "acme secret sauce"]},
       "grounding": {"id": "g", "version": "1", "thresholds": {"grounding": 0.5, "relevance": 0.5}},
       "pii": {"id": "p", "version": "1", "entities": ["EMAIL", "PHONE"]}}


class Fake:
    def __init__(self, assessments, outputs=None): self.assessments, self.outputs, self.calls = assessments, outputs or [], []
    def apply_guardrail(self, **kw):
        self.calls.append(kw)
        return {"action": "NONE", "assessments": self.assessments, "outputs": self.outputs, "usage": {"topicPolicyUnits": 1}, "ResponseMetadata": {}}


def test_topics_map_detected_flags_to_binary_nouls():
    fake = Fake([{"topicPolicy": {"topics": [{"name": "InvestmentAdvice", "detected": True, "action": "BLOCKED"}, {"name": "LegalAdvice", "detected": False, "action": "NONE"}]}}])
    c = BedrockApplyClient("topics", config=CFG, client=fake)
    call = c.ask({"role": "user", "text": "buy gold?"}, {"investmentadvice": {}, "legaladvice": {}, "any_denied_topic": {}, "severity": {}})
    assert call.ok and call.answers["investmentadvice"]["noul"] == 1.0 and call.answers["legaladvice"]["noul"] == 0.0 and call.answers["any_denied_topic"]["noul"] == 1.0
    assert call.raw["unanswered"] == ["severity"] and fake.calls[0]["source"] == "INPUT" and c.identity["guardrail_version"] == "1"


def test_words_match_case_insensitively_and_profanity_is_separate():
    fake = Fake([{"wordPolicy": {"customWords": [{"match": "Project Falcon", "detected": True}], "managedWordLists": []}}])
    call = BedrockApplyClient("words", config=CFG, client=fake).ask("the Project Falcon plan", {"project_falcon": {}, "acme_secret_sauce": {}, "profanity": {}, "any_word": {}})
    assert call.answers["project_falcon"]["noul"] == 1.0 and call.answers["acme_secret_sauce"]["noul"] == 0.0 and call.answers["profanity"]["noul"] == 0.0 and call.answers["any_word"]["noul"] == 1.0


def test_grounding_sends_qualified_blocks_and_inverts_scores():
    fake = Fake([{"contextualGroundingPolicy": {"filters": [{"type": "GROUNDING", "score": 0.58, "threshold": 0.5}, {"type": "RELEVANCE", "score": 1.0, "threshold": 0.5}]}}])
    call = BedrockApplyClient("grounding", config=CFG, client=fake).ask({"role": "assistant", "text": "It closes at 5.", "source": "opens 9 to 5", "query": "when?"}, {"unsupported": {}, "irrelevant": {}})
    assert fake.calls[0]["source"] == "OUTPUT" and [b["text"]["qualifiers"][0] for b in fake.calls[0]["content"]] == ["grounding_source", "query", "guard_content"]
    assert call.answers["unsupported"]["noul"] == 0.42 and call.answers["irrelevant"]["noul"] == 0.0 and call.raw["grounding_scores"]["GROUNDING"] == 0.58


def test_pii_masking_keeps_masked_text():
    fake = Fake([{"sensitiveInformationPolicy": {"piiEntities": [{"type": "EMAIL", "match": "a@b.co", "action": "ANONYMIZED", "detected": True}]}}], outputs=[{"text": "mail {EMAIL}"}])
    call = BedrockApplyClient("pii", config=CFG, client=fake).ask({"role": "assistant", "text": "mail a@b.co"}, {"EMAIL": {}, "PHONE": {}, "any_supported_entity": {}})
    assert call.answers["EMAIL"]["noul"] == 1.0 and call.answers["PHONE"]["noul"] == 0.0 and call.answers["any_supported_entity"]["noul"] == 1.0
    assert call.raw["masked_text"] == "mail {EMAIL}" and call.raw["pii_matches"][0]["match"] == "a@b.co"


def test_identity_records_the_live_guardrail_policy_including_managed_lists():
    from goldrails_bench.bedrock_apply import BedrockApplyClient

    class Control:
        def get_guardrail(self, guardrailIdentifier, guardrailVersion):
            return {"version": guardrailVersion, "status": "READY",
                    "wordPolicy": {"words": [{"text": "project falcon"}], "managedWordLists": [{"type": "PROFANITY"}]},
                    "topicPolicy": {"topics": [{"name": "InvestmentAdvice"}, {"name": "LegalAdvice"}]}}

    c = BedrockApplyClient("words", config={"words": {"id": "g1", "version": "1", "words": ["project falcon"]}, "region": "us-east-1"},
                           client=object(), control=Control())
    lp = c.identity["live_policy"]
    assert lp["managed_word_lists"] == ["PROFANITY"] and lp["words"] == ["project falcon"]
    assert lp["topics"] == ["InvestmentAdvice", "LegalAdvice"] and lp["policies"] == ["topicPolicy", "wordPolicy"]
