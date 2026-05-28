from pathlib import Path

from director_agent.models import ProductInfo
from director_agent.video_imitation_writer import generate_video_imitation_scripts
from director_agent.video_material_analyzer import analyze_video_material, save_video_material
from director_agent.video_transcriber import transcribe_video


VIDEO_TRANSCRIPT = """
先别急着买这瓶洗发水，早八出门前头发贴头皮真的很影响状态。
女主在浴室里洗完吹干，闺蜜提醒她看发根是不是更蓬松。
产品中段出现，镜头给到泡沫、香味和洗后清爽感。
最后提醒姐妹先收藏，对照自己的头发状态再选。
"""


def video_material():
    return {
        "id": "video_test",
        "title": "通勤前洗发水视频",
        "platform": "抖音",
        "source_url": "https://example.com/video",
        "category": "洗护个护类",
        "transcript": VIDEO_TRANSCRIPT,
        "frame_paths": ["frame_01.jpg", "frame_02.jpg"],
        "frame_summaries": ["关键帧1：浴室近景", "关键帧2：产品特写"],
        "note": "学习节奏，不照抄文案。",
    }


def product(script_mode="ai_video"):
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


def test_manual_transcript_allows_video_analysis_without_service():
    transcript = transcribe_video(manual_transcript=VIDEO_TRANSCRIPT)
    material = {**video_material(), "transcript": transcript["transcript"]}
    analysis = analyze_video_material(material)

    assert transcript["source"] == "manual"
    assert analysis["口播/字幕转写"]
    assert analysis["开头3秒钩子"]
    assert analysis["视频节奏拆解"]
    assert analysis["产品出现时机"]


def test_video_imitation_generates_original_scripts():
    material = video_material()
    analysis = analyze_video_material(material)
    output = generate_video_imitation_scripts(product(), analysis, material, version_count=3)

    assert len(output["original_scripts"]) == 3
    assert output["video_analysis_report"]
    for variant in output["original_scripts"]:
        assert variant["full_text"] != VIDEO_TRANSCRIPT
        assert VIDEO_TRANSCRIPT.strip() not in variant["full_text"]
        assert not variant["similarity_avoidance"]["is_too_similar"]


def test_video_imitation_live_action_has_no_ai_prompt_fields():
    material = video_material()
    analysis = analyze_video_material(material)
    output = generate_video_imitation_scripts(product(script_mode="live_action"), analysis, material, version_count=3)
    text = output["markdown"]

    assert "AI画面提示词" not in text
    assert "负面提示词" not in text
    assert "连续性要求" not in text
    assert "可直接复制版提示词" not in text
    assert "口播/对白" in text


def test_video_imitation_ai_video_has_required_ai_fields():
    material = video_material()
    analysis = analyze_video_material(material)
    output = generate_video_imitation_scripts(product(script_mode="ai_video"), analysis, material, version_count=3)
    text = output["markdown"]

    assert "AI画面提示词" in text
    assert "镜头运动" in text
    assert "负面提示词" in text
    assert "连续性要求" in text
    assert "可直接复制版提示词" in text


def test_video_material_save_does_not_require_raw_video(tmp_path, monkeypatch):
    import director_agent.video_material_analyzer as analyzer

    monkeypatch.setattr(analyzer, "VIDEO_LIBRARY_DIR", tmp_path)
    monkeypatch.setattr(analyzer, "VIDEO_INDEX_PATH", tmp_path / "index.json")
    saved = save_video_material({**video_material(), "analysis_result": analyze_video_material(video_material())})

    assert "raw_video" not in saved
    assert (tmp_path / "index.json").exists()
    assert list(tmp_path.glob("video_*.json")) or (tmp_path / f"{saved['id']}.json").exists()


def test_large_video_paths_are_gitignored():
    ignore = Path(".gitignore").read_text(encoding="utf-8")

    assert "references/video_library/raw_videos/" in ignore
    assert "references/video_library/frames/*" in ignore
    assert "temp/" in ignore
    assert "tmp/" in ignore
