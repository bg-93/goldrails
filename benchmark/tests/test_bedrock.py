from goldrails_bench.bedrock import BedrockChecksClient, messages_of, plan
from goldrails_bench.question_sets import SEP


class FakeBedrock:
    def __init__(self): self.calls = []
    def invoke_guardrail_checks(self, messages, checks):
        self.calls.append((messages, checks))
        cats = [c["category"] for c in checks["contentFilter"]["categories"]]
        return {"results": {"contentFilter": {"results": [{"category": c, "severityScore": 0.8 if c == "VIOLENCE" else 0.0} for c in cats]}},
                "usage": {"contentFilter": {"textUnits": 1}}, "ResponseMetadata": {}}


def test_plan_maps_names_strips_namespace_and_lists_unanswered():
    qs = {f"v1-f1-bedrock5{SEP}hate": {}, f"v1-f1-bedrock5{SEP}severity": {}, "violent_crimes": {}, "intent_real_world": {}}
    mapping, checks, unanswered = plan(qs)
    assert mapping[f"v1-f1-bedrock5{SEP}hate"] == ("contentFilter", "HATE") and mapping["violent_crimes"] == ("contentFilter", "VIOLENCE")
    assert [c["category"] for c in checks["contentFilter"]["categories"]] == ["HATE", "VIOLENCE"]
    assert set(unanswered) == {f"v1-f1-bedrock5{SEP}severity", "intent_real_world"}


def test_messages_carry_context_and_send_tool_content_as_tagged_user_input():
    m = messages_of({"role": "tool", "text": "result", "context": [{"role": "user", "text": "hi"}]})
    assert m == [{"role": "user", "content": [{"text": "hi"}]},
                 {"role": "user", "content": [{"text": "[Untrusted retrieved content]\nresult"}]}]
    # a retrieved document among the prior turns is tagged the same way; an assistant turn stays an assistant turn
    m = messages_of({"role": "user", "text": "and now?", "context": [{"role": "tool", "text": "doc"}, {"role": "assistant", "text": "ok"}]})
    assert [(x["role"], x["content"][0]["text"]) for x in m] == [("user", "[Untrusted retrieved content]\ndoc"), ("assistant", "ok"), ("user", "and now?")]


def test_ask_returns_severity_as_noul_under_question_names():
    fake = FakeBedrock()
    c = BedrockChecksClient(client=fake)
    call = c.ask({"role": "user", "text": "x"}, {"violence": {}, "hate": {}, "severity": {}})
    assert call.ok and call.answers == {"violence": {"type": "noul", "noul": 0.8, "basis": "bedrock_severity"},
                                        "hate": {"type": "noul", "noul": 0.0, "basis": "bedrock_severity"}}
    assert call.raw["unanswered"] == ["severity"] and call.usage["text_units"] == {"contentFilter": 1}
    assert len(fake.calls) == 1   # one service call per row however many questions


def test_ask_with_nothing_mappable_is_a_recorded_failure():
    call = BedrockChecksClient(client=FakeBedrock()).ask("x", {"severity": {}})
    assert not call.ok and "no question maps" in call.error
