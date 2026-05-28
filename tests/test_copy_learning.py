import json

from director_agent.copy_analyzer import analyze_reference_copy
from director_agent.creative_rewriter import generate_original_scripts_from_references
from director_agent.models import ProductInfo
from director_agent.reference_retriever import (
    add_reference_material,
    load_copy_library,
    select_reference_materials,
)


REFERENCE_COPY = """
早八通勤前，头发一贴头皮，精致感直接掉线。
闺蜜说先别急着换发型，洗发水要看洗后清爽和发根蓬松感。
浴室里揉出泡沫，吹干后头顶看起来更轻盈，香味也很舒服。
想要日常护理的姐妹可以先收藏，对照自己的头发状态再选。
"""


class FakeReferenceLLM:
    provider_name = "qwen"
    model = "qwen-plus-test"

    def generate(self, messages, schema):
        if "original_scripts" in schema.get("required", []):
            return {
                "original_scripts": [
                    {
                        "version": index + 1,
                        "title": f"LLM原创迁移方案{index + 1}",
                        "hook": "早八出门前，头发状态先决定第一眼精致感。",
                        "scene": "通勤前浴室",
                        "persona_relation": "闺蜜与女主",
                        "content_structure": "状态钩子 -> 场景困扰 -> 产品细节 -> 轻转化",
                        "plot_conflict": "女主担心头发贴头皮影响状态，闺蜜提醒先看日常护理细节。",
                        "product_placement": "产品在洗护动作中自然出现，承接清爽蓬松卖点。",
                        "conversion": "先收藏，对照自己的头发状态选择。",
                        "markdown": (
                            "### LLM原创迁移\n"
                            "- AI画面提示词：通勤前高级浴室，女主整理头发，产品自然入镜\n"
                            "- 镜头运动：近景推到产品特写\n"
                            "- 人物动作：女主揉泡沫并吹干头发\n"
                            "- 产品露出方式：生姜洗发水中段清晰露出\n"
                            "- 字幕文案：早八前先看头发状态\n"
                            "- 对白/口播：这瓶重点看日常清爽和发根蓬松感\n"
                            "- 负面提示词：夸大承诺, 医疗功效, 照抄参考文案"
                        ),
                    }
                    for index in range(3)
                ]
            }
        return {
            "开头钩子": "早八前头发一贴头皮，精致感先掉线。",
            "用户痛点": ["通勤前头发扁塌影响状态"],
            "目标人群": "重视日常头发状态的人群",
            "场景设计": ["通勤前浴室", "吹发镜前"],
            "人物关系": "闺蜜与女主",
            "内容结构": "状态钩子 -> 场景困扰 -> 产品细节 -> 收藏引导",
            "卖点植入方式": "把清爽蓬松放进洗护动作中呈现",
            "情绪触发点": ["状态焦虑", "变精致期待"],
            "转化引导方式": "先收藏，对照自身需求选择",
            "可复用思路": ["用早八状态钩子制造停留"],
            "不能照搬的表达": ["早八通勤前，头发一贴头皮"],
            "适合迁移的产品类型": ["洗发水", "护发产品"],
            "爆款公式": "状态钩子 -> 场景困扰 -> 产品细节 -> 轻转化",
        }


def reference_item():
    item = {
        "id": "ref_test",
        "title": "通勤前洗发水种草",
        "platform": "小红书",
        "source_url": "https://example.com/washcare-note",
        "category": "洗护个护类",
        "content_type": "小红书笔记",
        "original_copy": REFERENCE_COPY,
        "engagement_data": "点赞2.1万，收藏5000",
        "user_note": "开头场景很强，但不能照抄句子。",
        "analysis_result": {},
        "created_at": "2026-05-28T10:00:00",
    }
    item["analysis_result"] = analyze_reference_copy(item)
    return item


def target_product(script_mode="ai_video"):
    return ProductInfo(
        product_name="生姜洗发水",
        category="",
        audience="头发容易扁塌、重视头皮清洁的人群",
        selling_points="生姜植萃香氛，洗后清爽蓬松，适合日常护理",
        platform="抖音",
        duration=35,
        script_mode=script_mode,
        price_mechanism="单瓶体验装，引导先试用",
        script_subtype="AI剧情短剧广告" if script_mode == "ai_video" else "真人口播",
        video_style="职场逆袭" if script_mode == "ai_video" else "真实口播风",
        script_style="职场逆袭" if script_mode == "ai_video" else "真实口播风",
        ai_tool="Seedance" if script_mode == "ai_video" else "",
        aspect_ratio="9:16",
        character_setting="精致职场女生",
        scene_setting="高级浴室",
        generation_mode="local_only",
    )


def test_reference_copy_analysis_contains_required_fields():
    analysis = analyze_reference_copy(reference_item())

    for field in ["开头钩子", "用户痛点", "场景设计", "内容结构", "转化引导方式"]:
        assert analysis[field]


def test_reference_copy_analysis_can_use_llm_client():
    analysis = analyze_reference_copy(reference_item(), llm_client=FakeReferenceLLM())

    assert analysis["metadata"]["analysis_source"] == "llm"
    assert analysis["metadata"]["provider"] == "qwen"
    assert analysis["metadata"]["model"] == "qwen-plus-test"
    assert analysis["开头钩子"].startswith("早八前")


def test_copy_library_save_and_select(tmp_path, monkeypatch):
    import director_agent.reference_retriever as retriever

    monkeypatch.setattr(retriever, "COPY_LIBRARY_DIR", tmp_path)
    monkeypatch.setattr(retriever, "INDEX_PATH", tmp_path / "index.json")

    saved = add_reference_material(
        title="通勤前洗发水种草",
        platform="小红书",
        source_url="https://example.com/washcare-note",
        category="洗护个护类",
        content_type="小红书笔记",
        original_copy=REFERENCE_COPY,
        engagement_data="点赞2.1万",
        user_note="学习结构，不照抄。",
    )

    assert saved["analysis_result"]["开头钩子"]
    assert len(load_copy_library()) == 1
    selected = select_reference_materials([saved["id"]])
    assert selected[0]["title"] == "通勤前洗发水种草"
    assert json.loads((tmp_path / "index.json").read_text(encoding="utf-8"))[0]["id"] == saved["id"]


def test_reference_rewrite_generates_at_least_three_original_versions():
    output = generate_original_scripts_from_references(target_product(), [reference_item()], version_count=3)

    assert len(output["original_scripts"]) >= 3
    assert output["reference_analysis_report"]
    assert output["boom_formula"]
    for variant in output["original_scripts"]:
        assert variant["markdown"] != REFERENCE_COPY
        assert REFERENCE_COPY.strip() not in variant["markdown"]
        assert not variant["similarity_check"]["is_too_similar"]


def test_reference_rewrite_can_use_llm_client():
    output = generate_original_scripts_from_references(
        target_product(),
        [reference_item()],
        version_count=3,
        llm_client=FakeReferenceLLM(),
    )

    assert output["metadata"]["generation_source"] == "llm_reference_rewrite"
    assert output["metadata"]["provider"] == "qwen"
    assert output["metadata"]["model"] == "qwen-plus-test"
    assert len(output["original_scripts"]) == 3


def test_reference_rewrite_live_action_has_no_ai_prompt_fields():
    output = generate_original_scripts_from_references(target_product(script_mode="live_action"), [reference_item()], version_count=3)
    text = output["markdown"]

    assert "AI画面提示词" not in text
    assert "负面提示词" not in text
    assert "口播内容" in text


def test_reference_rewrite_ai_video_keeps_ai_prompt_fields():
    output = generate_original_scripts_from_references(target_product(script_mode="ai_video"), [reference_item()], version_count=3)
    text = output["markdown"]

    assert "AI画面提示词" in text
    assert "负面提示词" in text
