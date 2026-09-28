from goldrails_bench.bedrock import BedrockChecksClient, plan


class FakeBedrock:
    def invoke_guardrail_checks(self, messages, checks):
        return {"results": {"sensitiveInformation": {"results": [
                    {"type": "EMAIL", "confidenceScore": 0.9, "beginOffset": 3, "endOffset": 15, "messageIndex": 0, "contentIndex": 0},
                    {"type": "NAME", "confidenceScore": 0.4, "beginOffset": 20, "endOffset": 24, "messageIndex": 0, "contentIndex": 0}]}},
                "usage": {"sensitiveInformation": {"textUnits": 1}}, "ResponseMetadata": {}}


def test_pii_questions_map_to_entities_and_absent_types_score_zero():
    mapping, checks, unanswered = plan({"EMAIL": {}, "PHONE": {}, "any_supported_entity": {}, "contains_pii": {}, "severity": {}})
    assert [e["type"] for e in checks["sensitiveInformation"]["entities"]] == ["EMAIL", "PHONE"] and set(unanswered) == {"severity", "contains_pii"}
    call = BedrockChecksClient(client=FakeBedrock()).ask({"role": "user", "text": "x"}, {"EMAIL": {}, "PHONE": {}, "any_supported_entity": {}, "contains_pii": {}})
    assert call.ok and call.answers["EMAIL"]["noul"] == 0.9 and call.answers["PHONE"]["noul"] == 0.0 and "contains_pii" not in call.answers
    assert call.answers["any_supported_entity"]["noul"] == 0.9 and call.answers["any_supported_entity"]["basis"] == "bedrock_confidence_max"
    assert call.raw["results"]["sensitiveInformation"]["results"][0]["beginOffset"] == 3   # offsets kept for the masking study
