from pathlib import Path
import subprocess

from director_agent.models import ProductInfo
from director_agent.video_frame_extractor import extract_keyframes
import director_agent.video_frame_extractor as frame_extractor
from director_agent.video_imitation_writer import generate_video_imitation_scripts
from director_agent.video_material_analyzer import analyze_video_material, save_video_material
from director_agent.video_transcriber import transcribe_video
from streamlit_app import _has_video_evidence


VIDEO_TRANSCRIPT = """
先别急着买这瓶洗发水，早八出门前头发贴头皮真的很影响状态。
女主在浴室里洗完吹干，闺蜜提醒她看发根是不是更蓬松。
产品中段出现，镜头给到泡沫、香味和洗后清爽感。
最后提醒姐妹先收藏，对照自己的头发状态再选。
"""


class FakeVideoLLM:
    provider_name = "qwen"
    model = "qwen-plus-test"

    def generate(self, messages, schema):
        if "original_scripts" in schema.get("required", []):
            return {
                "original_scripts": [
                    {
                        "方案名称": f"LLM视频仿写方案 {index + 1}",
                        "参考了视频的什么结构": "钩子 -> 状态困扰 -> 产品中段出现 -> 轻转化",
                        "原创改动点": ["改写开头表达", "替换为生姜洗发水场景", "重写产品植入"],
                        "适合平台": "抖音",
                        "开头钩子": "出门前别只看穿搭，头发状态也很关键。",
                        "完整脚本": "女主准备出门时发现头发贴头皮，转到浴室用生姜洗发水，重点展示泡沫和吹干后的蓬松感，最后提醒先收藏。",
                        "字幕文案": ["出门前先看头发状态", "日常护理看细节", "先收藏对照选择"],
                        "口播/对白": "这次不喊夸张效果，只看日常清爽和发根蓬松感。",
                        "分镜/画面建议": ["镜前近景", "浴室产品特写", "吹发后状态镜头"],
                        "产品植入方式": "产品在洗护动作开始时自然出现。",
                        "结尾转化引导": "先收藏，对照自己的头发状态再选。",
                        "AI画面提示词": "通勤前浴室，女主整理头发，生姜洗发水自然露出，电商短剧质感",
                        "镜头运动": "近景推入，中段产品特写，结尾慢推定格",
                        "负面提示词": "照抄原视频, 医疗功效, 夸大承诺",
                        "连续性要求": "人物服装、浴室光线和产品包装保持一致。",
                        "可直接复制版提示词": "生成9:16生姜洗发水电商短剧，通勤前浴室场景，展示清爽蓬松日常护理。",
                    }
                    for index in range(3)
                ]
            }
        return {
            "视频基础信息": {"视频标题": "通勤前洗发水视频", "来源平台": "抖音"},
            "口播/字幕转写": VIDEO_TRANSCRIPT,
            "开头3秒钩子": "先别急着买这瓶洗发水，先看通勤前状态。",
            "视频节奏拆解": "状态钩子 -> 浴室洗护 -> 产品细节 -> 收藏引导",
            "场景设计": ["浴室", "通勤前镜前"],
            "人物关系": "闺蜜与女主",
            "用户痛点": "头发贴头皮影响出门状态",
            "剧情冲突": "出门前状态焦虑和产品护理细节形成反转",
            "产品出现时机": "中段洗护动作开始时出现",
            "卖点植入方式": "泡沫、香味、吹干后状态三段展示",
            "镜头/画面特点": ["产品特写", "镜前状态对比"],
            "字幕风格": "短句强节奏字幕",
            "情绪触发点": ["状态焦虑", "精致期待"],
            "转化引导方式": "先收藏，对照需求选择",
            "可模仿结构": "状态钩子 -> 场景困扰 -> 产品介入 -> 轻转化",
            "不能照搬的表达": ["先别急着买这瓶洗发水"],
            "适合迁移到哪些产品": ["洗发水", "护发产品"],
        }


class HallucinatingVideoLLM(FakeVideoLLM):
    def generate(self, messages, schema):
        payload = super().generate(messages, schema)
        if "original_scripts" not in schema.get("required", []):
            payload["场景设计"] = ["婴儿护理台", "宝妈给宝宝擦脸"]
            payload["人物关系"] = "宝妈与宝宝"
        return payload


class FailingIfCalledVideoLLM(FakeVideoLLM):
    def generate(self, messages, schema):
        raise AssertionError("LLM should not be called without video evidence")


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


def test_video_material_analysis_can_use_llm_client():
    analysis = analyze_video_material(video_material(), llm_client=FakeVideoLLM())

    assert analysis["metadata"]["analysis_source"] == "llm"
    assert analysis["metadata"]["provider"] == "qwen"
    assert analysis["metadata"]["model"] == "qwen-plus-test"
    assert "状态钩子" in analysis["视频节奏拆解"]


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


def test_video_imitation_can_use_llm_client():
    material = video_material()
    analysis = analyze_video_material(material, llm_client=FakeVideoLLM())
    output = generate_video_imitation_scripts(product(), analysis, material, version_count=3, llm_client=FakeVideoLLM())

    assert output["metadata"]["generation_source"] == "llm_video_imitation"
    assert output["metadata"]["analysis_source"] == "llm"
    assert output["metadata"]["provider"] == "qwen"
    assert output["metadata"]["model"] == "qwen-plus-test"
    assert len(output["original_scripts"]) == 3


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


def test_video_analysis_without_evidence_does_not_hallucinate_category_details():
    material = {
        "title": "户外纸巾对话视频",
        "platform": "抖音",
        "category": "母婴纸品类",
        "transcript": "",
        "frame_paths": [],
        "keyframe_count": 0,
        "frame_summaries": [],
        "frame_extraction_error": "ffmpeg failed",
    }

    analysis = analyze_video_material(material, llm_client=FailingIfCalledVideoLLM())
    text = str(analysis)

    assert analysis["分析可信度"] == "不可分析"
    assert analysis["metadata"]["analysis_source"] == "not_analyzable"
    assert "当前无法分析视频内容" in analysis["视频节奏拆解"]
    for hallucinated in ["婴儿", "宝妈", "宝宝", "擦脸", "护理台"]:
        assert hallucinated not in text


def test_video_upload_flow_requires_explicit_evidence_before_analysis():
    assert not _has_video_evidence({"keyframe_count": 0}, "", "")
    assert _has_video_evidence({"keyframe_count": 1}, "", "")
    assert _has_video_evidence({"keyframe_count": 0}, "老板，这纸巾咋卖？", "")
    assert _has_video_evidence({"keyframe_count": 0}, "", "户外真人手持纸巾产品")


def test_video_analysis_uses_supplemental_copy_as_evidence():
    material = {
        "title": "纸巾价格对话",
        "platform": "抖音",
        "category": "母婴纸品类",
        "transcript": "",
        "supplemental_copy": "户外真人手持纸巾产品，对话字幕：老板，这纸巾咋卖？10块钱一包。嫌贵你别买啊。那你学一个看看。",
        "frame_paths": [],
        "keyframe_count": 0,
        "frame_summaries": [],
    }

    analysis = analyze_video_material(material)
    text = str(analysis)

    assert analysis["分析可信度"] == "中"
    assert "老板与顾客" in analysis["人物关系"]
    assert "价格" in analysis["用户痛点"]
    assert "户外" in text
    assert "宝妈" not in text
    assert "宝宝" not in text


def test_video_analysis_uses_frame_summary_as_evidence():
    material = {
        "title": "纸巾产品户外展示",
        "platform": "抖音",
        "category": "母婴纸品类",
        "transcript": "",
        "frame_paths": ["frame_01.jpg"],
        "keyframe_count": 1,
        "frame_summaries": ["关键帧1：户外真人手持纸巾产品，画面有价格对话字幕。"],
    }

    analysis = analyze_video_material(material)
    text = str(analysis)

    assert analysis["分析可信度"] == "中"
    assert "关键帧1：户外真人手持纸巾产品" in text
    assert "户外" in text


def test_video_analysis_records_frame_extraction_error_in_metadata():
    material = {
        "title": "纸巾价格对话",
        "platform": "抖音",
        "category": "母婴纸品类",
        "transcript": "老板，这纸巾咋卖？10块钱一包。嫌贵你别买啊。那你学一个看看。",
        "frame_paths": [],
        "keyframe_count": 0,
        "frame_summaries": [],
        "frame_extraction_error": "ffmpeg failed: unsupported codec",
    }

    analysis = analyze_video_material(material)

    assert analysis["metadata"]["frame_extraction_error"] == "ffmpeg failed: unsupported codec"
    assert analysis["人物关系"] == "老板与顾客/路人"


def test_video_analysis_rejects_llm_details_not_supported_by_evidence():
    material = {
        "title": "纸巾价格对话",
        "platform": "抖音",
        "category": "母婴纸品类",
        "transcript": "",
        "supplemental_copy": "户外真人手持纸巾产品，对话字幕：老板，这纸巾咋卖？10块钱一包。嫌贵你别买啊。那你学一个看看。",
        "frame_paths": [],
        "keyframe_count": 0,
        "frame_summaries": [],
    }

    analysis = analyze_video_material(material, llm_client=HallucinatingVideoLLM())
    text = str(analysis)

    assert analysis["metadata"]["analysis_source"] == "local_fallback"
    assert "unsupported details" in analysis["metadata"]["fallback_reason"]
    assert "婴儿护理台" not in text
    assert "宝妈与宝宝" not in text


def test_extract_keyframes_failure_reports_error(tmp_path):
    result = extract_keyframes(tmp_path / "missing.mp4", output_dir=tmp_path / "frames")

    assert result["keyframe_count"] == 0
    assert result["frame_paths"] == []
    assert result["frame_extraction_error"]


def test_extract_keyframes_reports_imageio_ffmpeg_backend_when_available(tmp_path, monkeypatch):
    video_path = tmp_path / "video.mp4"
    video_path.write_bytes(b"fake video")

    def fake_run(command, check, stdout, stderr, timeout):
        output_pattern = Path(command[-1])
        output_pattern.parent.mkdir(parents=True, exist_ok=True)
        for index in range(1, 3):
            (output_pattern.parent / f"frame_{index:02d}.jpg").write_bytes(b"jpg")

    monkeypatch.setattr(frame_extractor, "_imageio_ffmpeg_path", lambda: "/fake/imageio/ffmpeg")
    monkeypatch.setattr(frame_extractor.shutil, "which", lambda name: "/fake/system/ffmpeg")
    monkeypatch.setattr(frame_extractor.subprocess, "run", fake_run)

    result = extract_keyframes(video_path, output_dir=tmp_path / "frames", interval_seconds=2, max_frames=8)

    assert result["keyframe_count"] == 2
    assert result["extraction_backend"] == "imageio_ffmpeg"
    assert result["attempted_backends"] == ["imageio_ffmpeg"]
    assert result["frame_timestamps"] == [0, 2]


def test_extract_keyframes_ffmpeg_timeout_returns_error(tmp_path, monkeypatch):
    video_path = tmp_path / "video.mp4"
    video_path.write_bytes(b"fake video")

    def timeout_run(command, check, stdout, stderr, timeout):
        raise subprocess.TimeoutExpired(command, timeout)

    monkeypatch.setattr(frame_extractor, "_imageio_ffmpeg_path", lambda: "/fake/imageio/ffmpeg")
    monkeypatch.setattr(frame_extractor.shutil, "which", lambda name: None)
    monkeypatch.setattr(frame_extractor.subprocess, "run", timeout_run)

    real_import = __import__

    def fake_import(name, *args, **kwargs):
        if name == "cv2":
            raise ModuleNotFoundError("cv2 unavailable")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr("builtins.__import__", fake_import)

    result = extract_keyframes(video_path, output_dir=tmp_path / "frames", timeout_seconds=5)

    assert result["keyframe_count"] == 0
    assert "ffmpeg timeout" in result["frame_extraction_error"]
    assert result["attempted_backends"] == ["imageio_ffmpeg", "system_ffmpeg", "opencv"]


def test_extract_keyframes_returns_clear_error_when_all_backends_unavailable(tmp_path, monkeypatch):
    video_path = tmp_path / "video.mp4"
    video_path.write_bytes(b"fake video")

    monkeypatch.setattr(frame_extractor, "_imageio_ffmpeg_path", lambda: None)
    monkeypatch.setattr(frame_extractor.shutil, "which", lambda name: None)

    real_import = __import__

    def fake_import(name, *args, **kwargs):
        if name == "cv2":
            raise ModuleNotFoundError("cv2 unavailable")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr("builtins.__import__", fake_import)

    result = extract_keyframes(video_path, output_dir=tmp_path / "frames")

    assert result["keyframe_count"] == 0
    assert result["extraction_backend"] == "none"
    assert result["attempted_backends"] == ["imageio_ffmpeg", "system_ffmpeg", "opencv"]
    assert "imageio_ffmpeg unavailable" in result["frame_extraction_error"]
    assert "system_ffmpeg unavailable" in result["frame_extraction_error"]
    assert "opencv unavailable" in result["frame_extraction_error"]
