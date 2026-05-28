"""Streamlit web UI for the ecommerce video director agent."""

from __future__ import annotations

import hmac
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

import streamlit as st
import streamlit.components.v1 as components

from director_agent.config import load_examples, load_settings
from director_agent.copy_analyzer import analyze_reference_copy
from director_agent.creative_rewriter import generate_original_scripts_from_references, write_reference_rewrite_outputs
from director_agent.generator import generate_script
from director_agent.models import ProductInfo
from director_agent.reference_retriever import (
    add_reference_material,
    load_copy_library,
    select_reference_materials,
)
from director_agent.renderer import render_markdown, sanitize_filename, write_outputs
from director_agent.script_modes import (
    AI_VIDEO_STYLES,
    AI_VIDEO_SUBTYPES,
    LIVE_ACTION_STYLES,
    LIVE_ACTION_SUBTYPES,
)
from director_agent.video_frame_extractor import extract_keyframes, save_uploaded_video_temporarily
from director_agent.video_imitation_writer import generate_video_imitation_scripts, write_video_imitation_outputs
from director_agent.video_material_analyzer import analyze_video_material, load_video_library, save_video_material
from director_agent.video_transcriber import transcribe_video


SCRIPT_MODE_LABELS = {
    "真人实拍": "live_action",
    "AI 视频": "ai_video",
}

ASPECT_RATIOS = ["9:16", "16:9", "1:1"]
AI_TOOLS = ["Seedance", "即梦", "可灵", "Runway", "海螺", "Sora"]
GENERATION_MODE_LABELS = {
    "本地稳定生成": "local_only",
    "本地生成 + 大模型润色": "local_plus_llm_polish",
    "大模型生成 + 本地合规兜底（预留）": "llm_generate_with_local_compliance",
}
GENERATION_MODE_OPTIONS = ["本地生成 + 大模型润色", "本地稳定生成"]
WORKSPACE_OPTIONS = ["脚本生成工作台", "爆款素材学习库"]
FORM_KEYS = {
    "product_name": "form_product_name",
    "category": "form_category",
    "audience": "form_audience",
    "selling_points": "form_selling_points",
    "price_mechanism": "form_price_mechanism",
    "platform": "form_platform",
    "duration": "form_duration",
    "mode_label": "form_mode_label",
    "script_subtype": "form_script_subtype",
    "aspect_ratio": "form_aspect_ratio",
    "video_style": "form_video_style",
    "character_setting": "form_character_setting",
    "scene_setting": "form_scene_setting",
    "ai_tool": "form_ai_tool",
    "generation_mode_label": "form_generation_mode_label",
}


def main() -> None:
    st.set_page_config(
        page_title="电商短视频编导 Agent",
        layout="wide",
        initial_sidebar_state="collapsed",
    )
    inject_styles()
    require_app_access()

    if "markdown_result" not in st.session_state:
        st.session_state.markdown_result = ""
        st.session_state.result = None
        st.session_state.product = None
        st.session_state.output_path = None
        st.session_state.json_output_path = None
        st.session_state.history = []

    settings = load_settings()
    project_settings = settings.get("project", {})
    ensure_form_defaults(
        str(project_settings.get("default_platform", "抖音")),
        int(project_settings.get("default_duration", 30)),
    )

    st.title("电商短视频编导 Agent")
    workspace = render_workspace_navigation()

    if workspace == "爆款素材学习库":
        render_copy_learning_workspace()
    else:
        render_script_generation_workspace()


def render_workspace_navigation() -> str:
    st.markdown(
        """
        <div class="workspace-nav-title">功能导航</div>
        <div class="workspace-nav-caption">选择当前工作区。两个工作区相互独立显示，避免信息混在同一个页面里。</div>
        """,
        unsafe_allow_html=True,
    )
    selected = st.radio(
        "功能导航",
        WORKSPACE_OPTIONS,
        horizontal=True,
        label_visibility="collapsed",
        key="active_workspace",
    )
    st.markdown(f'<div class="workspace-active-pill">当前工作区：{selected}</div>', unsafe_allow_html=True)
    return selected


def render_script_generation_workspace() -> None:
    input_col, output_col = st.columns([0.38, 0.62], gap="large")

    with input_col:
        st.subheader("输入区")
        product = render_input_form()

    with output_col:
        st.subheader("输出区")
        if product:
            with st.spinner("正在生成脚本..."):
                result = generate_script(product)
                markdown = render_markdown(product.normalized(), result)
                markdown_path, json_path = write_outputs(product.normalized(), result)
                st.session_state.product = product.normalized()
                st.session_state.result = result
                st.session_state.markdown_result = markdown
                st.session_state.output_path = markdown_path
                st.session_state.json_output_path = json_path
                add_history_record(product.normalized(), result, markdown, markdown_path)

        render_output_panel()


def render_copy_learning_workspace() -> None:
    render_copy_learning_area()


def require_app_access() -> None:
    passwords = get_configured_passwords()
    if not passwords:
        return
    if st.session_state.get("app_access_granted"):
        return

    st.markdown(
        """
        <div class="auth-panel">
            <div class="auth-title">电商短视频编导 Agent</div>
            <div class="auth-text">请输入公司内部访问密码。</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    password = st.text_input("访问密码", type="password", key="app_access_password")
    if st.button("进入工具", use_container_width=True):
        if any(hmac.compare_digest(password, item) for item in passwords):
            st.session_state.app_access_granted = True
            st.rerun()
        else:
            st.error("访问密码不正确。")
    st.stop()


def get_configured_passwords() -> list[str]:
    raw_passwords = get_secret_value("APP_PASSWORDS")
    single_password = get_secret_value("APP_PASSWORD")

    passwords: list[str] = []
    if isinstance(raw_passwords, str):
        passwords.extend(item.strip() for item in raw_passwords.split(",") if item.strip())
    elif isinstance(raw_passwords, (list, tuple)):
        passwords.extend(str(item).strip() for item in raw_passwords if str(item).strip())

    if single_password:
        passwords.append(str(single_password).strip())

    return [item for item in passwords if item]


def get_secret_value(name: str) -> Any:
    env_value = os.getenv(name)
    if env_value:
        return env_value
    try:
        return st.secrets.get(name)
    except Exception:
        return None


def render_input_form() -> Optional[ProductInfo]:
    settings = load_settings()
    project_settings = settings.get("project", {})
    default_platform = str(project_settings.get("default_platform", "抖音"))
    default_duration = int(project_settings.get("default_duration", 30))
    ensure_form_defaults(default_platform, default_duration)
    render_example_loader()

    current_mode = SCRIPT_MODE_LABELS.get(st.session_state.get(FORM_KEYS["mode_label"], "AI 视频"), "ai_video")
    subtype_options = AI_VIDEO_SUBTYPES if current_mode == "ai_video" else LIVE_ACTION_SUBTYPES
    style_options = AI_VIDEO_STYLES if current_mode == "ai_video" else LIVE_ACTION_STYLES
    subtype_fallback = "AI剧情短剧广告" if current_mode == "ai_video" else "真人口播"
    style_fallback = "高级产品广告风" if current_mode == "ai_video" else "真实口播风"
    ensure_select_value(FORM_KEYS["script_subtype"], subtype_options, subtype_fallback)
    ensure_select_value(FORM_KEYS["video_style"], style_options, style_fallback)

    with st.expander("基础信息", expanded=True):
        product_name = st.text_input("产品名称", key=FORM_KEYS["product_name"])
        category = st.text_input("产品类目", placeholder="可留空自动识别", key=FORM_KEYS["category"])
        audience = st.text_input("目标人群", key=FORM_KEYS["audience"])
        selling_points = st.text_area(
            "核心卖点",
            height=96,
            key=FORM_KEYS["selling_points"],
        )

    with st.expander("投放信息", expanded=True):
        price_mechanism = st.text_input("价格机制", key=FORM_KEYS["price_mechanism"])
        platform = st.selectbox(
            "平台",
            ["抖音", "快手", "小红书", "视频号", "淘宝", "拼多多"],
            key=FORM_KEYS["platform"],
        )
        duration = st.number_input("视频时长", min_value=5, max_value=180, step=5, key=FORM_KEYS["duration"])
        if current_mode == "ai_video":
            ai_tool = st.selectbox("AI 工具", AI_TOOLS, key=FORM_KEYS["ai_tool"])
        else:
            ai_tool = ""

    with st.expander("脚本设定", expanded=True):
        mode_label = st.radio("脚本模式", list(SCRIPT_MODE_LABELS.keys()), horizontal=True, key=FORM_KEYS["mode_label"])
        current_mode = SCRIPT_MODE_LABELS[mode_label]
        subtype_options = AI_VIDEO_SUBTYPES if current_mode == "ai_video" else LIVE_ACTION_SUBTYPES
        style_options = AI_VIDEO_STYLES if current_mode == "ai_video" else LIVE_ACTION_STYLES
        ensure_select_value(FORM_KEYS["script_subtype"], subtype_options, "AI剧情短剧广告" if current_mode == "ai_video" else "真人口播")
        ensure_select_value(FORM_KEYS["video_style"], style_options, "高级产品广告风" if current_mode == "ai_video" else "真实口播风")
        script_subtype = st.selectbox("脚本子类型", subtype_options, key=FORM_KEYS["script_subtype"])
        aspect_ratio = st.selectbox("视频比例", ASPECT_RATIOS, key=FORM_KEYS["aspect_ratio"])
        style_label = "AI视频风格" if current_mode == "ai_video" else "拍摄/表达风格"
        video_style = st.selectbox(style_label, style_options, key=FORM_KEYS["video_style"])
        character_setting = st.text_input("人物设定", key=FORM_KEYS["character_setting"])
        scene_setting = st.text_input("场景设定", key=FORM_KEYS["scene_setting"])

    with st.expander("生成配置", expanded=True):
        generation_mode_label = st.selectbox(
            "生成模式",
            GENERATION_MODE_OPTIONS,
            key=FORM_KEYS["generation_mode_label"],
        )

    submitted = st.button("生成脚本", use_container_width=True)

    if not submitted:
        return None

    if not product_name.strip() or not audience.strip() or not selling_points.strip():
        st.error("产品名称、目标人群、核心卖点不能为空。")
        return None

    return ProductInfo(
        product_name=product_name,
        category=category,
        audience=audience,
        selling_points=selling_points,
        platform=platform or default_platform,
        duration=int(duration),
        script_mode=SCRIPT_MODE_LABELS[mode_label],
        price_mechanism=price_mechanism,
        script_style=video_style,
        ai_tool=ai_tool,
        script_subtype=script_subtype,
        aspect_ratio=aspect_ratio,
        video_style=video_style,
        character_setting=character_setting,
        scene_setting=scene_setting,
        generation_mode=GENERATION_MODE_LABELS[generation_mode_label],
    )


def ensure_form_defaults(default_platform: str, default_duration: int) -> None:
    defaults = {
        FORM_KEYS["product_name"]: "生姜洗发水",
        FORM_KEYS["category"]: "",
        FORM_KEYS["audience"]: "头发容易扁塌、重视头皮清洁的人群",
        FORM_KEYS["selling_points"]: "生姜植萃香氛，洗后清爽蓬松，适合日常护理",
        FORM_KEYS["price_mechanism"]: "单瓶体验装，引导先试用",
        FORM_KEYS["platform"]: default_platform,
        FORM_KEYS["duration"]: default_duration,
        FORM_KEYS["mode_label"]: "AI 视频",
        FORM_KEYS["script_subtype"]: "AI剧情短剧广告",
        FORM_KEYS["aspect_ratio"]: "9:16",
        FORM_KEYS["video_style"]: "职场逆袭",
        FORM_KEYS["character_setting"]: "精致职场女生，早上通勤前整理发型",
        FORM_KEYS["scene_setting"]: "高级浴室和通勤前梳妆台",
        FORM_KEYS["ai_tool"]: "Seedance",
        FORM_KEYS["generation_mode_label"]: "本地生成 + 大模型润色",
    }
    for key, value in defaults.items():
        st.session_state.setdefault(key, value)
    if not st.session_state.get("v06_generation_mode_defaulted"):
        if st.session_state.get(FORM_KEYS["generation_mode_label"]) == "本地稳定生成":
            st.session_state[FORM_KEYS["generation_mode_label"]] = "本地生成 + 大模型润色"
        st.session_state["v06_generation_mode_defaulted"] = True


def render_example_loader() -> None:
    examples = load_examples()
    supported_names = ["生姜洗发水", "乳霜纸", "免浆牛蛙块", "1688包装袋"]
    filtered_examples = [item for item in examples if item["product_name"] in supported_names]
    example_names = ["手动输入新产品"] + [item["product_name"] for item in filtered_examples]
    if not example_names:
        return

    with st.container():
        st.selectbox(
            "示例产品快速载入",
            example_names,
            index=0,
            key="selected_example_product",
            on_change=apply_selected_example,
            args=(filtered_examples,),
        )
        if st.session_state.get("selected_example_product") == "手动输入新产品":
            st.caption("当前为手动输入模式，下面所有字段都可以自由编辑。")
        else:
            st.caption(f"已载入示例：{st.session_state.get('selected_example_product')}，下面所有字段仍可继续修改。")


def apply_selected_example(examples: list) -> None:
    selected_name = st.session_state.get("selected_example_product")
    if not selected_name or selected_name == "手动输入新产品":
        return
    selected = next((item for item in examples if item["product_name"] == selected_name), None)
    if selected:
        apply_example_to_form(selected)


def apply_example_to_form(example: Dict[str, Any]) -> None:
    mode_label = next((label for label, value in SCRIPT_MODE_LABELS.items() if value == example.get("script_mode")), "AI 视频")
    is_ai_video = SCRIPT_MODE_LABELS[mode_label] == "ai_video"
    subtype_options = AI_VIDEO_SUBTYPES if is_ai_video else LIVE_ACTION_SUBTYPES
    style_options = AI_VIDEO_STYLES if is_ai_video else LIVE_ACTION_STYLES
    default_subtype = "AI剧情短剧广告" if is_ai_video else "真人口播"
    default_style = "职场逆袭" if is_ai_video else "真实口播风"
    values = {
        FORM_KEYS["product_name"]: example.get("product_name", ""),
        FORM_KEYS["category"]: example.get("category", ""),
        FORM_KEYS["audience"]: example.get("audience", ""),
        FORM_KEYS["selling_points"]: example.get("selling_points", ""),
        FORM_KEYS["price_mechanism"]: example.get("price_mechanism", ""),
        FORM_KEYS["platform"]: _allowed_value(example.get("platform", "抖音"), ["抖音", "快手", "小红书", "视频号", "淘宝", "拼多多"], "抖音"),
        FORM_KEYS["duration"]: int(example.get("duration", 48)),
        FORM_KEYS["mode_label"]: mode_label,
        FORM_KEYS["script_subtype"]: _allowed_value(example.get("script_subtype", default_subtype), subtype_options, default_subtype),
        FORM_KEYS["aspect_ratio"]: _allowed_value(example.get("aspect_ratio", "9:16"), ASPECT_RATIOS, "9:16"),
        FORM_KEYS["video_style"]: _allowed_value(example.get("video_style", default_style), style_options, default_style),
        FORM_KEYS["character_setting"]: example.get("character_setting", ""),
        FORM_KEYS["scene_setting"]: example.get("scene_setting", ""),
        FORM_KEYS["ai_tool"]: _allowed_value(example.get("ai_tool", "Seedance") or "Seedance", AI_TOOLS, "Seedance"),
        FORM_KEYS["generation_mode_label"]: "本地生成 + 大模型润色",
    }
    for key, value in values.items():
        st.session_state[key] = value


def _allowed_value(value: str, options: list, fallback: str) -> str:
    return value if value in options else fallback


def ensure_select_value(key: str, options: list, fallback: str) -> None:
    if st.session_state.get(key) not in options:
        st.session_state[key] = fallback


def render_output_panel() -> None:
    markdown = st.session_state.markdown_result
    result = st.session_state.result
    product = st.session_state.product

    if not markdown or result is None or product is None:
        st.markdown(
            """
            <div class="empty-output-panel">
                <div class="empty-output-title">等待生成脚本</div>
                <div class="empty-output-text">
                    生成后会在这里展示剧情分镜、AI画面提示词、字幕、对白、负面提示词、质量评分和 metadata。
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        render_history_panel()
        return

    source = result.metadata.get("generation_source", "unknown")
    provider = result.metadata.get("provider", "unknown")
    generation_mode = result.metadata.get("generation_mode", product.generation_mode)
    st.caption(f"生成来源：{source} · Provider：{provider} · Generation Mode：{generation_mode}")

    preview_col, action_col = st.columns([0.58, 0.42], gap="large")

    with preview_col:
        if result.script_mode == "ai_video":
            tabs = st.tabs(["基础信息", "剧情分镜", "AI提示词", "字幕/口播", "合规检查", "质量评分", "metadata"])
            with tabs[0]:
                render_basic_info(product, result)
            with tabs[1]:
                render_storyboard(result)
            with tabs[2]:
                render_prompt_section(result, markdown)
            with tabs[3]:
                render_subtitle_voiceover(result)
            with tabs[4]:
                render_compliance_panel(result)
            with tabs[5]:
                render_quality_panel(result)
            with tabs[6]:
                render_metadata_panel(result)
        else:
            tabs = st.tabs(["基础信息", "分镜脚本", "字幕/口播", "合规检查", "质量评分", "metadata"])
            with tabs[0]:
                render_basic_info(product, result)
            with tabs[1]:
                render_storyboard(result)
            with tabs[2]:
                render_subtitle_voiceover(result)
            with tabs[3]:
                render_compliance_panel(result)
            with tabs[4]:
                render_quality_panel(result)
            with tabs[5]:
                render_metadata_panel(result)

    with action_col:
        render_action_panel(product, result, markdown)


def render_copy_learning_area() -> None:
    st.markdown("## 爆款素材学习库")
    st.caption("仅支持手动添加链接和粘贴文案。Agent 只学习结构和思路，不照抄参考文案原文。")
    st.caption(
        f"原创迁移将使用“脚本生成工作台”中的当前产品信息：{st.session_state.get(FORM_KEYS['product_name'], '未命名产品')}。"
    )
    material_type = st.radio(
        "素材类型",
        ["文案 / 笔记素材", "视频素材"],
        horizontal=True,
        key="learning_material_type",
    )
    if material_type == "视频素材":
        render_video_learning_area()
        return

    input_col, library_col = st.columns([0.46, 0.54], gap="large")
    with input_col:
        with st.container(border=True):
            card_title("快速添加参考素材")
            ref_title = st.text_input("素材标题", key="ref_title")
            ref_platform = st.selectbox("来源平台", ["抖音", "小红书", "快手", "视频号", "淘宝", "1688", "网页", "其他"], key="ref_platform")
            ref_url = st.text_input("来源链接，选填", key="ref_url")
            st.caption("当前版本不会自动抓取链接内容，请将笔记正文、视频口播或字幕粘贴到素材内容中。链接仅用于记录来源。")
            ref_category = st.selectbox(
                "产品类目",
                ["洗护个护类", "母婴纸品类", "冻品餐饮类", "1688工厂定制类", "食品零食类", "家清日用品类", "美妆护肤类", "厨房用品类", "宠物用品类", "其他"],
                key="ref_category",
            )
            ref_copy = st.text_area(
                "素材内容",
                height=220,
                placeholder="请粘贴小红书笔记正文、短视频口播稿、字幕文案、网页摘录或你的整理备注。",
                key="ref_original_copy",
            )
            with st.expander("高级信息，可选", expanded=False):
                ref_content_type = st.selectbox("内容类型", ["短视频口播", "短剧广告", "小红书笔记", "直播切片", "商品详情页", "同行案例"], key="ref_content_type")
                ref_engagement = st.text_input("互动数据", placeholder="例如：点赞2.1万，评论820，收藏5000", key="ref_engagement")
                ref_note = st.text_area("用户备注", height=72, key="ref_user_note")

            analyze_col, save_col = st.columns(2)
            with analyze_col:
                if st.button("分析素材", use_container_width=True):
                    if not ref_title.strip():
                        st.error("素材标题不能为空。")
                    elif not ref_copy.strip():
                        st.error("当前版本无法仅凭链接分析，请粘贴具体文案内容后再分析。")
                    else:
                        draft = build_reference_draft(
                            ref_title,
                            ref_platform,
                            ref_url,
                            ref_category,
                            ref_content_type,
                            ref_copy,
                            ref_engagement,
                            ref_note,
                        )
                        draft["analysis_result"] = analyze_reference_copy(draft)
                        st.session_state.reference_draft = draft
            with save_col:
                if st.button("保存到素材库", use_container_width=True):
                    draft = st.session_state.get("reference_draft")
                    if not draft:
                        st.error("请先点击“分析素材”。")
                    else:
                        saved = add_reference_material(
                            title=draft["title"],
                            platform=draft["platform"],
                            source_url=draft["source_url"],
                            category=draft["category"],
                            content_type=draft["content_type"],
                            original_copy=draft["original_copy"],
                            engagement_data=draft["engagement_data"],
                            user_note=draft["user_note"],
                            analyze=True,
                        )
                        st.session_state.reference_draft = saved
                        st.success("已保存到 references/copy_library/。")

            draft = st.session_state.get("reference_draft")
            if draft:
                st.markdown("#### 素材分析报告")
                render_reference_analysis(draft.get("analysis_result") or {})

    with library_col:
        with st.container(border=True):
            card_title("素材库原创迁移")
            library = load_copy_library()
            if not library:
                st.caption("素材库暂无内容。先在左侧添加并保存一条参考素材。")
                return

            label_to_id = {
                f"{item.get('title', '未命名')} · {item.get('category', '未分类')} · {item.get('platform', '未知平台')}": item.get("id")
                for item in library
            }
            selected_labels = st.multiselect("选择 1-5 条参考素材", list(label_to_id.keys()), key="selected_reference_labels")
            selected_ids = [label_to_id[label] for label in selected_labels if label_to_id.get(label)]
            if len(selected_ids) > 5:
                st.warning("最多选择 5 条参考素材，系统会使用前 5 条。")
                selected_ids = selected_ids[:5]

            version_count = st.slider("原创脚本方案数量", min_value=3, max_value=5, value=3, step=1)
            if st.button("基于参考素材生成原创脚本", use_container_width=True):
                if not selected_ids:
                    st.error("请至少选择 1 条参考素材。")
                else:
                    current_product = build_product_from_form_state()
                    references = select_reference_materials(selected_ids)
                    output = generate_original_scripts_from_references(current_product, references, version_count=version_count)
                    markdown_path, json_path = write_reference_rewrite_outputs(current_product, output)
                    st.session_state.reference_rewrite_output = output
                    st.session_state.reference_rewrite_markdown_path = markdown_path
                    st.session_state.reference_rewrite_json_path = json_path

            output = st.session_state.get("reference_rewrite_output")
            if output:
                st.markdown("#### 原创迁移结果")
                st.markdown(output.get("markdown", ""))
                output_path = st.session_state.get("reference_rewrite_markdown_path")
                json_path = st.session_state.get("reference_rewrite_json_path")
                download_cols = st.columns(2)
                with download_cols[0]:
                    st.download_button(
                        "下载原创迁移 Markdown",
                        data=output.get("markdown", ""),
                        file_name=display_filename(output_path) or "reference_rewrite.md",
                        mime="text/markdown",
                        use_container_width=True,
                    )
                with download_cols[1]:
                    st.download_button(
                        "下载原创迁移 JSON",
                        data=json.dumps({key: value for key, value in output.items() if key != "markdown"}, ensure_ascii=False, indent=2),
                        file_name=display_filename(json_path) or "reference_rewrite.json",
                        mime="application/json",
                        use_container_width=True,
                    )


def render_video_learning_area() -> None:
    input_col, output_col = st.columns([0.46, 0.54], gap="large")
    with input_col:
        with st.container(border=True):
            card_title("上传视频素材")
            uploaded_video = st.file_uploader("上传视频文件", type=["mp4", "mov", "m4v", "avi"], key="video_material_upload")
            if uploaded_video:
                st.video(uploaded_video)
            video_title = st.text_input("视频标题", key="video_title")
            video_platform = st.selectbox("来源平台", ["抖音", "小红书", "快手", "视频号", "淘宝", "1688", "网页", "其他"], key="video_platform")
            video_url = st.text_input("原始链接，选填，仅记录来源", key="video_source_url")
            video_category = st.selectbox(
                "产品类目",
                ["洗护个护类", "母婴纸品类", "冻品餐饮类", "1688工厂定制类", "食品零食类", "家清日用品类", "美妆护肤类", "厨房用品类", "宠物用品类", "其他"],
                key="video_category",
            )
            manual_transcript = st.text_area(
                "补充口播/字幕文案，选填",
                height=150,
                placeholder="如果没有自动转写服务，请粘贴视频口播稿、字幕文案或你的整理版内容。",
                key="video_manual_transcript",
            )
            video_note = st.text_area("素材备注，选填", height=72, key="video_note")

            analyze_col, save_col = st.columns(2)
            with analyze_col:
                if st.button("分析视频素材", use_container_width=True):
                    if not uploaded_video:
                        st.error("请先上传视频文件。")
                    elif not video_title.strip():
                        st.error("视频标题不能为空。")
                    else:
                        video_path = None
                        try:
                            video_path = save_uploaded_video_temporarily(uploaded_video)
                            frame_result = extract_keyframes(video_path)
                            transcript_result = transcribe_video(video_path, manual_transcript)
                            if not transcript_result["transcript"]:
                                st.warning("当前环境没有可用自动转写结果，请补充口播或字幕文案以提升分析准确度。")
                            material = build_video_material_draft(
                                title=video_title,
                                platform=video_platform,
                                source_url=video_url,
                                category=video_category,
                                transcript=transcript_result["transcript"],
                                note=video_note,
                                frame_result=frame_result,
                                transcript_result=transcript_result,
                            )
                            material["analysis_result"] = analyze_video_material(material)
                            st.session_state.video_material_draft = material
                        finally:
                            if video_path and video_path.exists():
                                video_path.unlink(missing_ok=True)
            with save_col:
                if st.button("保存到视频素材库", use_container_width=True):
                    draft = st.session_state.get("video_material_draft")
                    if not draft:
                        st.error("请先点击“分析视频素材”。")
                    else:
                        saved = save_video_material(draft)
                        st.session_state.video_material_draft = saved
                        st.success("已保存到 references/video_library/。")

            draft = st.session_state.get("video_material_draft")
            if draft:
                st.markdown("#### 视频素材分析报告")
                render_video_analysis(draft.get("analysis_result") or {})

    with output_col:
        with st.container(border=True):
            card_title("视频原创仿写生成")
            video_library = load_video_library()
            if video_library:
                st.caption(f"视频素材库已有 {len(video_library)} 条记录。当前按钮默认基于左侧刚分析的视频生成。")
            else:
                st.caption("视频素材库暂无保存记录。你仍可基于左侧刚分析的视频直接生成原创脚本。")
            version_count = st.selectbox("原创脚本方案数量", [3, 5, 8], key="video_imitation_version_count")
            if st.button("基于该视频生成原创脚本", use_container_width=True):
                draft = st.session_state.get("video_material_draft")
                if not draft:
                    st.error("请先分析一条视频素材。")
                else:
                    current_product = build_product_from_form_state()
                    output = generate_video_imitation_scripts(
                        current_product,
                        draft.get("analysis_result") or {},
                        draft,
                        version_count=int(version_count),
                    )
                    markdown_path, json_path = write_video_imitation_outputs(current_product, output)
                    st.session_state.video_imitation_output = output
                    st.session_state.video_imitation_markdown_path = markdown_path
                    st.session_state.video_imitation_json_path = json_path

            output = st.session_state.get("video_imitation_output")
            if output:
                st.markdown("#### 原创仿写结果")
                st.markdown(output.get("markdown", ""))
                output_path = st.session_state.get("video_imitation_markdown_path")
                json_path = st.session_state.get("video_imitation_json_path")
                download_cols = st.columns(2)
                with download_cols[0]:
                    st.download_button(
                        "下载视频仿写 Markdown",
                        data=output.get("markdown", ""),
                        file_name=display_filename(output_path) or "video_imitation.md",
                        mime="text/markdown",
                        use_container_width=True,
                    )
                with download_cols[1]:
                    st.download_button(
                        "下载视频仿写 JSON",
                        data=json.dumps({key: value for key, value in output.items() if key != "markdown"}, ensure_ascii=False, indent=2),
                        file_name=display_filename(json_path) or "video_imitation.json",
                        mime="application/json",
                        use_container_width=True,
                    )


def build_video_material_draft(
    title: str,
    platform: str,
    source_url: str,
    category: str,
    transcript: str,
    note: str,
    frame_result: Dict[str, Any],
    transcript_result: Dict[str, Any],
) -> Dict[str, Any]:
    return {
        "id": "",
        "title": title.strip(),
        "platform": platform.strip(),
        "source_url": source_url.strip(),
        "category": category.strip(),
        "transcript": transcript.strip(),
        "transcript_source": transcript_result.get("source", "none"),
        "transcription_note": transcript_result.get("note", ""),
        "frame_paths": frame_result.get("frame_paths", []),
        "frame_summaries": frame_result.get("frame_summaries", []),
        "frame_extraction_backend": frame_result.get("backend", "none"),
        "frame_extraction_note": frame_result.get("note", ""),
        "note": note.strip(),
        "analysis_result": {},
        "created_at": "",
    }


def render_video_analysis(analysis: Dict[str, Any]) -> None:
    for field in [
        "视频基础信息",
        "口播/字幕转写",
        "开头3秒钩子",
        "视频节奏拆解",
        "场景设计",
        "人物关系",
        "用户痛点",
        "剧情冲突",
        "产品出现时机",
        "卖点植入方式",
        "镜头/画面特点",
        "字幕风格",
        "情绪触发点",
        "转化引导方式",
        "可模仿结构",
        "不能照搬的表达",
        "适合迁移到哪些产品",
    ]:
        st.markdown(f"**{field}：** {format_display_value(analysis.get(field, '未提取'))}")


def format_display_value(value: Any) -> str:
    if isinstance(value, dict):
        return "；".join(f"{key}：{item}" for key, item in value.items())
    if isinstance(value, list):
        return "；".join(str(item) for item in value)
    return str(value)


def build_reference_draft(
    title: str,
    platform: str,
    source_url: str,
    category: str,
    content_type: str,
    original_copy: str,
    engagement_data: str,
    user_note: str,
) -> Dict[str, Any]:
    return {
        "id": "",
        "title": title.strip(),
        "platform": platform.strip(),
        "source_url": source_url.strip(),
        "category": category.strip(),
        "content_type": content_type.strip(),
        "original_copy": original_copy.strip(),
        "engagement_data": engagement_data.strip(),
        "user_note": user_note.strip(),
        "analysis_result": {},
        "created_at": "",
    }


def render_reference_analysis(analysis: Dict[str, Any]) -> None:
    for field in [
        "开头钩子",
        "用户痛点",
        "目标人群",
        "场景设计",
        "人物关系",
        "内容结构",
        "卖点植入方式",
        "情绪触发点",
        "转化引导方式",
        "可复用思路",
        "不能照搬的表达",
        "适合迁移的产品类型",
    ]:
        value = analysis.get(field, "未提取")
        if isinstance(value, list):
            value = "；".join(str(item) for item in value)
        st.markdown(f"**{field}：** {value}")


def build_product_from_form_state() -> ProductInfo:
    mode_label = st.session_state.get(FORM_KEYS["mode_label"], "AI 视频")
    return ProductInfo(
        product_name=st.session_state.get(FORM_KEYS["product_name"], "未命名产品"),
        category=st.session_state.get(FORM_KEYS["category"], ""),
        audience=st.session_state.get(FORM_KEYS["audience"], "目标人群"),
        selling_points=st.session_state.get(FORM_KEYS["selling_points"], "核心卖点"),
        platform=st.session_state.get(FORM_KEYS["platform"], "抖音"),
        duration=int(st.session_state.get(FORM_KEYS["duration"], 30)),
        script_mode=SCRIPT_MODE_LABELS.get(mode_label, "ai_video"),
        price_mechanism=st.session_state.get(FORM_KEYS["price_mechanism"], ""),
        script_style=st.session_state.get(FORM_KEYS["video_style"], ""),
        ai_tool=st.session_state.get(FORM_KEYS["ai_tool"], ""),
        script_subtype=st.session_state.get(FORM_KEYS["script_subtype"], ""),
        aspect_ratio=st.session_state.get(FORM_KEYS["aspect_ratio"], "9:16"),
        video_style=st.session_state.get(FORM_KEYS["video_style"], ""),
        character_setting=st.session_state.get(FORM_KEYS["character_setting"], ""),
        scene_setting=st.session_state.get(FORM_KEYS["scene_setting"], ""),
        generation_mode=GENERATION_MODE_LABELS.get(st.session_state.get(FORM_KEYS["generation_mode_label"], "本地稳定生成"), "local_only"),
    )


def render_basic_info(product: ProductInfo, result) -> None:
    metadata = result.metadata
    rows = {
        "产品名称": product.product_name,
        "识别类目": result.category,
        "目标人群": product.audience,
        "平台": product.platform,
        "视频时长": f"{product.duration} 秒",
        "脚本模式": result.script_mode,
        "脚本子类型": metadata.get("normalized_script_subtype") or metadata.get("script_subtype") or product.script_subtype or "未填写",
        "视频比例": product.aspect_ratio or metadata.get("aspect_ratio", "未填写"),
        "视频风格": metadata.get("video_style") or product.video_style or "未填写",
        "人物设定": product.character_setting or metadata.get("character_setting", "未填写"),
        "场景设定": product.scene_setting or metadata.get("scene_setting", "未填写"),
        "生成来源": metadata.get("generation_source", "unknown"),
        "Provider": metadata.get("provider", "unknown"),
        "Generation Mode": metadata.get("generation_mode", product.generation_mode),
    }
    for label, value in rows.items():
        st.markdown(f"**{label}：** {value}")


def render_storyboard(result) -> None:
    for scene in result.scenes:
        with st.expander(scene.title, expanded=scene.order == 1):
            if result.script_mode == "live_action":
                if scene.plot:
                    st.markdown(f"**结构说明：** {scene.plot}")
                st.markdown(f"**画面描述：** {scene.visual}")
                st.markdown(f"**拍摄镜头：** {scene.shot}")
                if scene.character_action:
                    st.markdown(f"**人物动作：** {scene.character_action}")
                st.markdown(f"**台词/口播：** {scene.voiceover}")
                st.markdown(f"**字幕文案：** {scene.subtitle}")
            else:
                if scene.plot:
                    st.markdown(f"**剧情：** {scene.plot}")
                st.markdown(f"**AI画面提示词：** {scene.visual}")
                st.markdown(f"**镜头运动：** {scene.shot}")
                if scene.character_action:
                    st.markdown(f"**人物动作：** {scene.character_action}")
                if scene.product_exposure:
                    st.markdown(f"**产品露出方式：** {scene.product_exposure}")
                st.markdown(f"**字幕文案：** {scene.subtitle}")
                st.markdown(f"**对白/口播：** {scene.voiceover}")
                if scene.negative_prompt:
                    st.markdown(f"**负面提示词：** {scene.negative_prompt}")
            st.caption(f"时长：{scene.duration_seconds} 秒")


def render_prompt_section(result, markdown: str) -> None:
    st.code(result.ai_video_prompt or markdown, language="text")
    copy_button("复制可直接复制版提示词", result.ai_video_prompt or markdown, "copy-prompt-tab")


def render_subtitle_voiceover(result) -> None:
    subtitle_col, voiceover_col = st.columns(2)
    with subtitle_col:
        st.markdown("#### 字幕文案")
        st.code(collect_scene_field(result, "subtitle"), language="text")
        copy_button("复制字幕文案", collect_scene_field(result, "subtitle"), "copy-subtitle-tab")
    with voiceover_col:
        st.markdown("#### 对白/口播")
        st.code(collect_scene_field(result, "voiceover"), language="text")
        copy_button("复制对白/口播", collect_scene_field(result, "voiceover"), "copy-voiceover-tab")


def render_quality_panel(result) -> None:
    quality = result.metadata.get("quality_score") or {}
    if not isinstance(quality, dict) or quality.get("score") is None:
        st.info("暂无质量评分。")
        return
    score = int(quality.get("score"))
    grade, suggestion = quality_grade_and_suggestion(score, quality)
    st.metric("脚本质量评分", f"{score}/100", grade)
    st.markdown(f"**等级：** {grade}")
    st.markdown(f"**简短建议：** {suggestion}")
    dimensions = quality.get("dimensions") or {}
    if dimensions:
        st.markdown("#### 分项评分")
        for name, score in dimensions.items():
            st.markdown(f"- {name}：{score}/10")
    strengths = quality.get("strengths") or []
    if strengths:
        st.markdown("#### 优点")
        for item in strengths:
            st.markdown(f"- {item}")
    improvements = quality.get("improvements") or []
    if improvements:
        st.markdown("#### 需要优化的地方")
        for item in improvements:
            st.markdown(f"- {item}")


def render_metadata_panel(result) -> None:
    st.json(result.metadata)


def render_action_panel(product: ProductInfo, result, markdown: str) -> None:
    st.markdown("### 当前结果操作")

    with st.container(border=True):
        card_title("脚本质量评分")
        quality = result.metadata.get("quality_score") or {}
        if isinstance(quality, dict) and quality.get("score") is not None:
            score = int(quality.get("score"))
            grade, suggestion = quality_grade_and_suggestion(score, quality)
            st.markdown(
                f"""
                <div class="score-card-body">
                    <div class="score-number">{score}<span>/100</span></div>
                    <div class="score-grade">等级：<strong>{grade}</strong></div>
                    <div class="score-suggestion">{suggestion}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )
        else:
            st.info("暂无质量评分。")

    with st.container(border=True):
        card_title("一键复制")
        copy_row_a = st.columns(2)
        with copy_row_a[0]:
            copy_button("复制完整提示词", result.ai_video_prompt or markdown, "copy-prompt")
        with copy_row_a[1]:
            copy_button("复制字幕文案", collect_scene_field(result, "subtitle"), "copy-subtitles")

        copy_row_b = st.columns(2)
        with copy_row_b[0]:
            copy_button("复制对白/口播", collect_scene_field(result, "voiceover"), "copy-voiceover")
        with copy_row_b[1]:
            copy_button("复制画面提示词", collect_scene_field(result, "visual"), "copy-visuals")

    with st.container(border=True):
        card_title("导出文件")
        output_path = st.session_state.output_path
        json_output_path = st.session_state.get("json_output_path")
        filename = display_filename(output_path) or build_download_filename(product)
        json_filename = display_filename(json_output_path) or filename.replace(".md", ".json")

        st.caption("Markdown / JSON 已保存到 outputs/")
        with st.expander("查看文件信息", expanded=False):
            st.markdown(f"Markdown：`{filename}`")
            st.markdown(f"JSON：`{json_filename}`")
            st.markdown(f"保存目录：`{display_save_dir(output_path)}`")

        file_actions = st.columns(2)
        with file_actions[0]:
            st.download_button(
                "下载 Markdown",
                data=markdown,
                file_name=filename,
                mime="text/markdown",
                use_container_width=True,
            )
        with file_actions[1]:
            st.download_button(
                "下载 JSON",
                data=json.dumps(result.to_dict(), ensure_ascii=False, indent=2),
                file_name=json_filename,
                mime="application/json",
                use_container_width=True,
            )
        copy_button("复制完整路径", build_full_path_text(output_path, json_output_path), "copy-output-path")

    render_history_records_card()


def render_compliance_panel(result) -> None:
    if result.risk_terms:
        for risk in result.risk_terms:
            st.warning(f"高风险词：{risk.term}（出现 {risk.count} 次）｜原因：{risk.reason}｜替代表达：{risk.replacement}")
    else:
        st.success("未命中内置高风险词。")

    if result.compliance_notes:
        st.markdown("#### 模型/模板合规备注")
        for note in result.compliance_notes:
            st.markdown(f"- {note}")


def add_history_record(product: ProductInfo, result, markdown: str, markdown_path) -> None:
    history = st.session_state.setdefault("history", [])
    quality = result.metadata.get("quality_score") or {}
    history.insert(
        0,
        {
            "time": datetime.now().strftime("%H:%M:%S"),
            "product_name": product.product_name,
            "category": result.category,
            "script_mode": result.script_mode,
            "script_subtype": product.script_subtype or result.metadata.get("script_subtype", ""),
            "generation_mode": result.metadata.get("generation_mode", product.generation_mode),
            "score": quality.get("score") if isinstance(quality, dict) else None,
            "markdown": markdown,
            "path": str(markdown_path),
        },
    )
    del history[8:]


def render_history_panel() -> None:
    st.markdown("### 历史生成记录")
    render_history_records_card()


def render_history_records_card() -> None:
    history = st.session_state.get("history", [])
    with st.container(border=True):
        card_title("历史生成记录")
        if not history:
            st.caption("本次会话还没有历史记录。")
            return

        for index, item in enumerate(history, start=1):
            score_text = f"{item['score']}/100" if item.get("score") is not None else "未评分"
            with st.container(border=True):
                st.markdown(
                    f"""
                    <div class="history-item-title">{item['product_name']} · {item['category']}</div>
                    <div class="history-item-meta">评分：{score_text} · {item['time']}</div>
                    <div class="history-item-meta">{item['script_mode']} / {item.get('generation_mode', 'local_only')}</div>
                    <div class="history-item-meta">文件名：{display_filename(item.get('path')) or '未保存'}</div>
                    """,
                    unsafe_allow_html=True,
                )
                history_actions = st.columns(2)
                with history_actions[0]:
                    copy_button("复制该记录", item["markdown"], f"copy-history-{index}")
                with history_actions[1]:
                    copy_button("复制路径", item.get("path", ""), f"copy-history-path-{index}")


def collect_scene_field(result, field_name: str) -> str:
    lines = []
    for scene in result.scenes:
        value = getattr(scene, field_name, "")
        if value:
            lines.append(f"{scene.title}\n{value}")
    return "\n\n".join(lines)


def card_title(title: str) -> None:
    st.markdown(f'<div class="card-title">{title}</div>', unsafe_allow_html=True)


def quality_grade_and_suggestion(score: int, quality: Dict[str, Any]) -> tuple[str, str]:
    if score >= 90:
        grade = "优秀"
    elif score >= 80:
        grade = "良好"
    elif score >= 70:
        grade = "可用"
    else:
        grade = "待优化"

    improvements = quality.get("improvements") or []
    if improvements:
        suggestion = str(improvements[0])
    elif score >= 90:
        suggestion = "结构完整、表达清晰，可直接进入拍摄或 AI 视频生成环节。"
    elif score >= 80:
        suggestion = "整体可用，建议继续强化开头钩子和产品植入细节。"
    elif score >= 70:
        suggestion = "具备基础可用性，建议补足画面提示词、镜头动作和成交引导。"
    else:
        suggestion = "建议先优化剧情完整度、合规表达和 AI 视频可生成性。"
    return grade, suggestion


def display_filename(path_value: Any) -> str:
    if not path_value:
        return ""
    return Path(str(path_value)).name


def display_save_dir(path_value: Any) -> str:
    if not path_value:
        return "outputs/"
    path = Path(str(path_value))
    if "outputs" in path.parts:
        return "outputs/"
    return f"{path.parent.name}/" if path.parent.name else "./"


def build_full_path_text(markdown_path: Any, json_path: Any) -> str:
    paths = []
    if markdown_path:
        paths.append(f"Markdown: {markdown_path}")
    if json_path:
        paths.append(f"JSON: {json_path}")
    return "\n".join(paths)


def copy_button(label: str, text: str, button_id: str) -> None:
    text_json = json.dumps(text, ensure_ascii=False)
    label_json = json.dumps(label, ensure_ascii=False)
    copied_label_json = json.dumps("已复制", ensure_ascii=False)
    components.html(
        f"""
        <button id="{button_id}" style="
            width: 100%;
            height: 42px;
            border: 1px solid #f5c76b;
            border-radius: 8px;
            background: linear-gradient(135deg, #f5c76b 0%, #d99732 100%);
            color: #111827;
            font-size: 13px;
            font-weight: 700;
            cursor: pointer;
            box-shadow: 0 8px 22px rgba(217, 151, 50, 0.22);
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
            padding: 0 10px;
        ">{label}</button>
        <script>
        const button = document.getElementById("{button_id}");
        button.onclick = async () => {{
            const text = {text_json};
            await navigator.clipboard.writeText(text);
            button.innerText = {copied_label_json};
            setTimeout(() => button.innerText = {label_json}, 1200);
        }};
        </script>
        """,
        height=50,
    )


def build_download_filename(product: ProductInfo) -> str:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"{timestamp}_{sanitize_filename(product.product_name)}_{product.script_mode}.md"


def inject_styles() -> None:
    st.markdown(
        """
        <style>
        :root {
            color-scheme: dark;
        }
        .stApp {
            background:
                radial-gradient(circle at 18% 0%, rgba(245, 199, 107, 0.08), transparent 28rem),
                linear-gradient(135deg, #0b0f14 0%, #121821 54%, #090c10 100%);
            color: #eef2f7;
        }
        [data-testid="stAppViewContainer"] {
            background: transparent;
        }
        .block-container {
            padding-top: 1.5rem;
            padding-bottom: 2rem;
            max-width: 1480px;
        }
        h1 {
            font-size: 1.7rem;
            margin-bottom: 1rem;
            color: #f8fafc;
        }
        h2, h3 {
            letter-spacing: 0;
            color: #f8fafc;
        }
        h3 {
            font-size: 1.45rem;
            margin-top: 0.2rem;
            margin-bottom: 0.85rem;
        }
        h4, h5, h6 {
            color: #eef2f7;
        }
        [data-testid="stVerticalBlockBorderWrapper"] {
            background: rgba(18, 25, 35, 0.94);
            border: 1px solid rgba(148, 163, 184, 0.22);
            border-radius: 12px;
            box-shadow: 0 14px 36px rgba(0, 0, 0, 0.18);
            margin-bottom: 18px;
        }
        [data-testid="stVerticalBlockBorderWrapper"] [data-testid="stVerticalBlockBorderWrapper"] {
            background: rgba(13, 19, 27, 0.66);
            border-color: rgba(148, 163, 184, 0.14);
            box-shadow: none;
            margin-top: 10px;
            margin-bottom: 12px;
        }
        div[data-testid="stForm"] {
            border: 1px solid rgba(148, 163, 184, 0.24);
            border-radius: 8px;
            padding: 1rem;
            background: #161d27;
        }
        label,
        label p,
        [data-testid="stWidgetLabel"],
        [data-testid="stWidgetLabel"] p {
            color: #e5edf6 !important;
            font-weight: 650;
        }
        .stTextInput input,
        .stTextArea textarea,
        .stNumberInput input,
        .stSelectbox [data-baseweb="select"] > div,
        .stMultiSelect [data-baseweb="select"] > div {
            background-color: #0d131b !important;
            border-color: rgba(148, 163, 184, 0.32) !important;
            color: #f8fafc !important;
            border-radius: 7px !important;
        }
        .stTextInput input:focus,
        .stTextArea textarea:focus,
        .stNumberInput input:focus {
            border-color: #f5c76b !important;
            box-shadow: 0 0 0 1px rgba(245, 199, 107, 0.75) !important;
        }
        .stSelectbox [data-baseweb="select"] span,
        .stSelectbox [data-baseweb="select"] svg,
        .stNumberInput button svg,
        .stRadio label,
        .stRadio p {
            color: #f8fafc !important;
            fill: #f8fafc !important;
        }
        .stButton > button,
        .stDownloadButton > button,
        div[data-testid="stFormSubmitButton"] button {
            background: linear-gradient(135deg, #f5c76b 0%, #d99732 100%) !important;
            border: 1px solid #f5c76b !important;
            color: #111827 !important;
            border-radius: 8px !important;
            font-weight: 800 !important;
            min-height: 2.65rem;
            box-shadow: 0 12px 26px rgba(217, 151, 50, 0.24);
            white-space: nowrap !important;
            font-size: 13px !important;
            padding-left: 0.65rem !important;
            padding-right: 0.65rem !important;
        }
        .stButton > button:hover,
        .stDownloadButton > button:hover,
        div[data-testid="stFormSubmitButton"] button:hover {
            border-color: #ffd77d !important;
            filter: brightness(1.05);
        }
        [data-testid="stTabs"] button {
            color: #d6deea !important;
        }
        [data-testid="stTabs"] button[aria-selected="true"] {
            color: #f5c76b !important;
        }
        [data-testid="stExpander"] {
            background: #121923;
            border: 1px solid rgba(148, 163, 184, 0.2);
            border-radius: 8px;
        }
        [data-testid="stMetric"] {
            background: #121923;
            border: 1px solid rgba(245, 199, 107, 0.25);
            border-radius: 8px;
            padding: 0.75rem;
        }
        .stCodeBlock,
        pre {
            background: #0b1118 !important;
            color: #e5edf6 !important;
            border-radius: 8px !important;
        }
        [data-testid="stCaptionContainer"],
        [data-testid="stCaptionContainer"] p {
            color: #aab6c5 !important;
        }
        div[data-testid="stMarkdownContainer"] p,
        div[data-testid="stMarkdownContainer"] li {
            line-height: 1.62;
            color: #dce4ef;
        }
        .card-title {
            color: #f8fafc;
            font-size: 15.5px;
            font-weight: 800;
            letter-spacing: 0;
            margin-bottom: 0.85rem;
        }
        .score-card-body {
            padding: 0.1rem 0 0.15rem;
        }
        .score-number {
            color: #f5c76b;
            font-size: 40px;
            line-height: 1;
            font-weight: 900;
            letter-spacing: 0;
            margin-bottom: 0.7rem;
        }
        .score-number span {
            color: #d6deea;
            font-size: 18px;
            font-weight: 700;
            margin-left: 3px;
        }
        .score-grade {
            color: #e5edf6;
            font-size: 14px;
            margin-bottom: 0.5rem;
        }
        .score-grade strong {
            color: #f5c76b;
        }
        .score-suggestion {
            color: #aab6c5;
            font-size: 13px;
            line-height: 1.65;
        }
        .file-line {
            display: grid;
            grid-template-columns: 88px minmax(0, 1fr);
            gap: 8px;
            align-items: center;
            color: #dce4ef;
            font-size: 13px;
            margin-bottom: 0.48rem;
        }
        .file-line span {
            color: #aab6c5;
            white-space: nowrap;
        }
        .file-line code {
            display: block;
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
            color: #f8fafc;
            background: rgba(11, 17, 24, 0.9);
            border: 1px solid rgba(148, 163, 184, 0.16);
            border-radius: 6px;
            padding: 0.28rem 0.42rem;
            font-size: 12px;
        }
        .file-line.muted {
            margin-bottom: 0.9rem;
        }
        .history-item-title {
            color: #eef2f7;
            font-size: 14px;
            font-weight: 800;
            margin-bottom: 0.34rem;
        }
        .history-item-meta {
            color: #aab6c5;
            font-size: 12px;
            line-height: 1.55;
        }
        .empty-output-panel {
            border: 1px dashed rgba(245, 199, 107, 0.45);
            border-radius: 10px;
            background: rgba(17, 24, 39, 0.72);
            padding: 1.15rem;
            margin-bottom: 1rem;
        }
        .empty-output-title {
            color: #f5c76b;
            font-size: 1.02rem;
            font-weight: 800;
            margin-bottom: 0.35rem;
        }
        .empty-output-text {
            color: #d6deea;
            line-height: 1.7;
        }
        .workspace-nav-title {
            color: #f8fafc;
            font-size: 1rem;
            font-weight: 850;
            margin: 0.2rem 0 0.2rem;
        }
        .workspace-nav-caption {
            color: #aab6c5;
            font-size: 0.86rem;
            margin-bottom: 0.55rem;
        }
        .workspace-active-pill {
            display: inline-flex;
            align-items: center;
            border: 1px solid rgba(245, 199, 107, 0.32);
            background: rgba(245, 199, 107, 0.1);
            color: #f5c76b;
            border-radius: 999px;
            padding: 0.28rem 0.72rem;
            font-size: 0.82rem;
            font-weight: 800;
            margin: 0.25rem 0 1rem;
        }
        div[role="radiogroup"] {
            gap: 0.7rem;
        }
        div[role="radiogroup"] label {
            background: rgba(18, 25, 35, 0.9);
            border: 1px solid rgba(148, 163, 184, 0.2);
            border-radius: 10px;
            padding: 0.45rem 0.72rem;
        }
        .auth-panel {
            max-width: 460px;
            margin: 12vh auto 1.2rem;
            padding: 1.4rem;
            border: 1px solid rgba(245, 199, 107, 0.36);
            border-radius: 12px;
            background: rgba(18, 25, 35, 0.94);
            box-shadow: 0 20px 48px rgba(0, 0, 0, 0.26);
        }
        .auth-title {
            color: #f8fafc;
            font-size: 1.35rem;
            font-weight: 900;
            margin-bottom: 0.55rem;
        }
        .auth-text {
            color: #aab6c5;
            font-size: 0.95rem;
            line-height: 1.7;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


if __name__ == "__main__":
    main()
