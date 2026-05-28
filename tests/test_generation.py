from pathlib import Path

import pytest

from director_agent.config import load_hook_rules
from director_agent.category import get_strategy, recognize_category
from director_agent.generator import generate_script
from director_agent.llm import LLMClient, LLMError
from director_agent.local_generator import build_local_script_payload
from director_agent.models import ProductInfo
from director_agent.renderer import render_markdown, write_outputs
from director_agent.script_modes import AI_VIDEO_SUBTYPES, LIVE_ACTION_SUBTYPES


LOCAL_SETTINGS = {"llm": {"provider": "local", "max_retries": 0}}


class FakeValidClient(LLMClient):
    provider_name = "fake"

    def generate(self, messages, schema):
        return {
            "product_summary": "乳霜纸适合家庭日常柔软擦拭。",
            "hook": "一张纸巾，看看日常擦拭体验。",
            "scenes": [
                {
                    "order": 1,
                    "title": "开场",
                    "visual": "客厅桌面摆放乳霜纸。",
                    "voiceover": "先看触感。",
                    "subtitle": "柔软触感",
                    "shot": "近景",
                    "duration_seconds": 5,
                    "character_action": "",
                    "product_exposure": "",
                    "negative_prompt": "",
                },
                {
                    "order": 2,
                    "title": "湿水测试",
                    "visual": "纸巾湿水后轻轻按压。",
                    "voiceover": "湿水后也能应对日常擦拭。",
                    "subtitle": "湿水不易破",
                    "shot": "微距",
                    "duration_seconds": 5,
                    "character_action": "",
                    "product_exposure": "",
                    "negative_prompt": "",
                },
                {
                    "order": 3,
                    "title": "收尾",
                    "visual": "家庭成员自然使用。",
                    "voiceover": "适合放在家里高频使用。",
                    "subtitle": "家庭日常",
                    "shot": "中景",
                    "duration_seconds": 5,
                    "character_action": "",
                    "product_exposure": "",
                    "negative_prompt": "",
                },
            ],
            "selling_points": ["柔软亲肤", "湿水不易破"],
            "ai_video_prompt": None,
            "compliance_notes": ["避免绝对化承诺。"],
        }


class FakeInvalidClient(LLMClient):
    provider_name = "fake-invalid"

    def generate(self, messages, schema):
        return {"hook": "missing scenes"}


class FakeTimeoutClient(LLMClient):
    provider_name = "fake-timeout"

    def generate(self, messages, schema):
        raise LLMError("timeout")


class FakePolishClient(LLMClient):
    provider_name = "fake-polish"

    def __init__(self, payload):
        self.payload = payload

    def generate(self, messages, schema):
        return self.payload


def product(script_mode="live_action", selling_points="柔软亲肤，湿水不易破"):
    return ProductInfo(
        product_name="乳霜纸",
        category="",
        audience="有宝宝的家庭",
        selling_points=selling_points,
        platform="抖音",
        duration=30,
        script_mode=script_mode,
    )


def test_mock_llm_valid_json_parses_to_script_result():
    result = generate_script(product(), llm_client=FakeValidClient())

    assert result.metadata["generation_source"] == "llm"
    assert result.metadata["provider"] == "fake"
    assert result.category == "母婴纸品类"
    assert len(result.scenes) == 3


def test_invalid_llm_payload_falls_back_to_local_template():
    result = generate_script(product(), llm_client=FakeInvalidClient())

    assert result.metadata["generation_source"] == "local_fallback"
    assert "scene" in result.metadata["fallback_reason"].lower()
    assert len(result.scenes) >= 3


def test_timeout_falls_back_to_local_template():
    result = generate_script(product(), llm_client=FakeTimeoutClient())

    assert result.metadata["generation_source"] == "local_fallback"
    assert "timeout" in result.metadata["fallback_reason"]


def test_compliance_scans_model_or_template_output():
    result = generate_script(product(selling_points="100%柔软，绝对好用"), llm_client=FakeValidClient())
    terms = {risk.term for risk in result.risk_terms}

    assert "100%" in terms
    assert "绝对" in terms


@pytest.mark.parametrize("script_mode", ["live_action", "ai_video"])
def test_output_file_contains_markdown_sections(tmp_path: Path, script_mode: str):
    info = product(script_mode=script_mode)
    result = generate_script(info, settings=LOCAL_SETTINGS)
    markdown_path, json_path = write_outputs(info, result, output_dir=tmp_path, save_json=True)

    assert markdown_path.exists()
    assert json_path is not None and json_path.exists()
    content = markdown_path.read_text(encoding="utf-8")
    assert "## 基本信息" in content
    assert "## 分镜脚本" in content
    assert "## 合规检查" in content
    if script_mode == "ai_video":
        assert "## AI 视频可复制提示词" in content
        assert "人物动作" in content
        assert "产品露出方式" in content
        assert "负面提示词" in content


def drama_product(
    product_name="生姜洗发水",
    selling_points="生姜植萃香氛，洗后清爽蓬松，适合日常护理",
    video_style="职场逆袭",
    duration=48,
    generation_mode="local_only",
):
    return ProductInfo(
        product_name=product_name,
        category="",
        audience="目标人群",
        selling_points=selling_points,
        platform="抖音",
        duration=duration,
        script_mode="ai_video",
        price_mechanism="单瓶体验装",
        script_style=video_style,
        ai_tool="Seedance",
        script_subtype="AI剧情短剧广告",
        aspect_ratio="9:16",
        video_style=video_style,
        character_setting="精致职场女生",
        scene_setting="高级浴室",
        generation_mode=generation_mode,
    )


def test_ai_drama_ad_outputs_four_story_segments():
    result = generate_script(drama_product(), settings=LOCAL_SETTINGS)
    markdown = render_markdown(drama_product(), result)

    assert len(result.scenes) == 4
    assert "【0-3秒 冲击力开篇】" in markdown
    assert "【4-20秒 冲突铺垫】" in markdown
    assert "【21-35秒 产品植入】" in markdown
    assert "【36-48秒 情绪反转 / 成交引导】" in markdown


def test_frozen_food_avoids_ceo_romance_style():
    info = drama_product(
        product_name="免浆牛蛙块",
        selling_points="免浆处理，省备菜时间，肉质紧实，适合爆炒和火锅",
        video_style="霸总甜宠",
        duration=48,
    )
    result = generate_script(info, settings=LOCAL_SETTINGS)
    markdown = render_markdown(info, result)

    assert result.category == "冻品餐饮类"
    assert result.metadata["video_style"] != "霸总甜宠"
    assert "霸总甜宠" not in " ".join(scene.plot for scene in result.scenes)
    assert "霸总甜宠" not in markdown
    assert "餐饮老板" in result.metadata["video_style"]
    assert "风格调整" in markdown


def test_ai_drama_markdown_contains_negative_prompt_and_continuity():
    info = drama_product()
    result = generate_script(info, settings=LOCAL_SETTINGS)
    markdown = render_markdown(info, result)

    assert "统一负面提示词" in markdown
    assert "连续性要求" in markdown
    assert "可直接复制版提示词" in markdown


def test_washcare_drama_markdown_avoids_exact_risk_terms():
    info = drama_product()
    result = generate_script(info, settings=LOCAL_SETTINGS)
    markdown = render_markdown(info, result)

    assert all(term not in markdown for term in ["生发", "防脱", "治疗", "根治"])


@pytest.mark.parametrize("duration", [48, 37])
def test_ai_drama_scene_durations_equal_input_duration(duration: int):
    result = generate_script(drama_product(duration=duration), settings=LOCAL_SETTINGS)

    assert sum(scene.duration_seconds for scene in result.scenes) == duration


def test_washcare_drama_uses_washcare_scene_not_restaurant_logic():
    info = drama_product(product_name="生姜洗发水")
    result = generate_script(info, settings=LOCAL_SETTINGS)
    text = render_markdown(info, result)

    assert "浴室" in text
    assert "发根" in text or "头发" in text
    assert "餐饮老板" not in text
    assert "后厨效率" not in text


def test_frozen_food_drama_uses_kitchen_efficiency_logic_not_romance():
    info = drama_product(
        product_name="免浆牛蛙块",
        selling_points="免浆处理，省备菜时间，肉质紧实，适合爆炒和火锅",
        video_style="霸总甜宠",
        duration=48,
    )
    result = generate_script(info, settings=LOCAL_SETTINGS)
    text = render_markdown(info, result)

    assert any(keyword in text for keyword in ["后厨", "餐饮", "出餐效率", "备菜"])
    assert "霸总甜宠" not in text


def test_mother_baby_paper_drama_uses_family_baby_scenario():
    info = drama_product(
        product_name="乳霜纸",
        selling_points="柔软亲肤，湿水不易破，适合日常擦脸擦鼻子",
        video_style="宝妈带娃",
        duration=48,
    )
    info = ProductInfo(
        **{
            **info.__dict__,
            "audience": "有宝宝的家庭、鼻炎敏感人群",
            "character_setting": "宝妈和宝宝",
            "scene_setting": "客厅亲子区和婴儿护理台",
        }
    )
    result = generate_script(info, settings=LOCAL_SETTINGS)
    text = render_markdown(info, result)

    assert result.category == "母婴纸品类"
    assert "宝妈" in text
    assert "宝宝" in text
    assert "家庭" in text


def test_ai_drama_result_has_quality_score():
    result = generate_script(drama_product(), settings=LOCAL_SETTINGS)
    quality = result.metadata.get("quality_score")

    assert isinstance(quality, dict)
    assert 0 <= quality["score"] <= 100
    assert quality["strengths"]
    assert quality["improvements"]


def test_ai_drama_local_only_remains_available_for_tests_and_debugging():
    result = generate_script(drama_product(), settings=LOCAL_SETTINGS)

    assert result.metadata["generation_source"] == "local_drama"
    assert result.metadata["provider"] == "local"
    assert result.metadata["generation_mode"] == "local_only"


def test_product_default_generation_mode_is_llm_first():
    info = product().normalized()

    assert info.generation_mode == "llm_generate_with_local_compliance"


def test_ai_drama_llm_generate_with_local_compliance_uses_client():
    info = drama_product(generation_mode="llm_generate_with_local_compliance")
    client = FakePolishClient(local_drama_payload(info))

    result = generate_script(info, settings=LOCAL_SETTINGS, llm_client=client)

    assert result.metadata["generation_source"] == "llm"
    assert result.metadata["generation_mode"] == "llm_generate_with_local_compliance"
    assert result.metadata["requested_generation_mode"] == "llm_generate_with_local_compliance"
    assert result.metadata["provider"] == "fake-polish"


def test_ai_drama_local_plus_llm_polish_uses_client_without_changing_structure():
    info = drama_product(generation_mode="local_plus_llm_polish")
    local_payload = local_drama_payload(info)
    local_payload["scenes"][0]["voiceover"] = "润色后：通勤前的状态差一点，镜头里的精致感就会少一截。"
    client = FakePolishClient(local_payload)

    result = generate_script(info, settings=LOCAL_SETTINGS, llm_client=client)

    assert result.metadata["generation_source"] == "local_drama+llm_polish"
    assert result.metadata["provider"] == "fake-polish"
    assert result.metadata["generation_mode"] == "local_plus_llm_polish"
    assert result.scenes[0].voiceover.startswith("润色后")
    assert [scene.duration_seconds for scene in result.scenes] == [3, 17, 15, 13]


def test_ai_drama_polish_falls_back_to_local_only_without_client():
    info = drama_product(generation_mode="local_plus_llm_polish")
    result = generate_script(info, settings=LOCAL_SETTINGS)

    assert result.metadata["generation_source"] == "local_drama"
    assert result.metadata["provider"] == "local"
    assert result.metadata["generation_mode"] == "local_only"
    assert result.metadata["requested_generation_mode"] == "local_plus_llm_polish"


def test_ai_drama_polish_rejects_structure_changes_and_falls_back():
    info = drama_product(generation_mode="local_plus_llm_polish")
    broken_payload = local_drama_payload(info)
    broken_payload["scenes"][0]["duration_seconds"] = 9
    client = FakePolishClient(broken_payload)

    result = generate_script(info, settings=LOCAL_SETTINGS, llm_client=client)

    assert result.metadata["generation_source"] == "local_drama"
    assert result.metadata["generation_mode"] == "local_only"
    assert "LLM polish failed" in result.metadata["fallback_reason"]
    assert [scene.duration_seconds for scene in result.scenes] == [3, 17, 15, 13]


def local_drama_payload(info: ProductInfo):
    product_info = info.normalized()
    category = recognize_category(product_info.product_name, product_info.selling_points, product_info.category)
    strategy = get_strategy(category).__dict__
    return build_local_script_payload(product_info, category, strategy)


def test_hook_rules_cover_key_categories():
    rules = load_hook_rules()["categories"]
    for category in ["洗护个护类", "母婴纸品类", "冻品餐饮类", "1688工厂定制类", "食品零食类", "家清日用品类"]:
        assert len(rules[category]) >= 5


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("这款洗发水主打生发和防脱", "生发"),
        ("纸巾绝对安全还能治疗红屁屁", "治疗红屁屁"),
        ("零食有减肥和保健功效", "减肥"),
    ],
)
def test_new_category_compliance_terms_are_flagged(text: str, expected: str):
    result = generate_script(product(selling_points=text), settings=LOCAL_SETTINGS)
    terms = {risk.term for risk in result.risk_terms}

    assert expected in terms


def test_script_mode_subtype_options_are_isolated():
    assert LIVE_ACTION_SUBTYPES == [
        "真人口播",
        "真人剧情短剧",
        "测评对比",
        "直播切片",
        "老板口播",
        "探厂脚本",
        "产品使用教程",
    ]
    assert AI_VIDEO_SUBTYPES == [
        "AI剧情短剧广告",
        "AI产品广告片",
        "AI生活方式种草",
        "AI虚拟人口播",
        "AI产品使用教程",
        "AI分镜提示词",
    ]
    assert not set(LIVE_ACTION_SUBTYPES) & set(AI_VIDEO_SUBTYPES)


def live_talking_product(**overrides):
    data = {
        "product_name": "生姜洗发水",
        "category": "",
        "audience": "头发容易扁塌、重视头皮清洁的人群",
        "selling_points": "生姜植萃香氛，洗后清爽蓬松，适合日常护理",
        "platform": "抖音",
        "duration": 35,
        "script_mode": "live_action",
        "price_mechanism": "单瓶体验装",
        "script_subtype": "真人口播",
        "video_style": "真实口播风",
        "script_style": "真实口播风",
        "ai_tool": "Seedance",
        "generation_mode": "local_only",
    }
    data.update(overrides)
    return ProductInfo(**data)


def test_live_action_talking_head_output_has_no_ai_prompt_fields():
    info = live_talking_product()
    result = generate_script(info, settings=LOCAL_SETTINGS)
    markdown = render_markdown(info, result)

    assert result.script_mode == "live_action"
    assert result.ai_video_prompt is None
    assert "AI画面提示词" not in markdown
    assert "负面提示词" not in markdown
    assert "连续性要求" not in markdown
    assert "可直接复制版提示词" not in markdown
    assert "AI 视频可复制提示词" not in markdown


def test_live_action_talking_head_output_uses_talking_structure():
    info = live_talking_product()
    result = generate_script(info, settings=LOCAL_SETTINGS)
    markdown = render_markdown(info, result)

    assert "开头3秒钩子" in markdown
    assert "痛点引入" in markdown
    assert "产品介绍" in markdown
    assert "卖点展开" in markdown
    assert "使用场景" in markdown
    assert "价格/机制" in markdown
    assert "结尾引导" in markdown
    assert "口播内容" in markdown or "台词/口播" in markdown


def test_live_action_ignores_ai_tool_in_generation_metadata_and_markdown():
    info = live_talking_product(ai_tool="Seedance")
    result = generate_script(info, settings=LOCAL_SETTINGS)
    markdown = render_markdown(info, result)

    assert "AI 工具" not in markdown
    assert "真人实拍模式不使用 AI 工具字段" in result.metadata["normalization_reason"]
    assert "ai_tool" not in result.metadata


def test_ai_video_drama_keeps_ai_prompt_fields():
    info = drama_product()
    result = generate_script(info, settings=LOCAL_SETTINGS)
    markdown = render_markdown(info, result)

    assert result.script_mode == "ai_video"
    assert "AI画面提示词" in markdown
    assert "负面提示词" in markdown


def test_illegal_live_action_ai_drama_combo_is_normalized():
    info = live_talking_product(script_subtype="AI剧情短剧广告", video_style="霸总甜宠")
    result = generate_script(info, settings=LOCAL_SETTINGS)
    markdown = render_markdown(info, result)

    assert result.metadata["normalized_script_subtype"] == "真人剧情短剧"
    assert "AI剧情短剧广告" in result.metadata["normalization_reason"]
    assert "霸总甜宠" in result.metadata["normalization_reason"]
    assert "脚本子类型：真人剧情短剧" in markdown
    assert "拍摄/表达风格：真实口播风" in markdown
    assert "霸总甜宠" not in markdown
    assert "AI画面提示词" not in markdown
