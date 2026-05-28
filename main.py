"""CLI entrypoint for the ecommerce video director agent."""

from __future__ import annotations

import argparse
from pathlib import Path

from director_agent.config import PROJECT_ROOT, load_examples, load_settings
from director_agent.generator import generate_script
from director_agent.models import ProductInfo
from director_agent.renderer import write_outputs


def main() -> None:
    parser = argparse.ArgumentParser(description="电商短视频编导 Agent")
    parser.add_argument("--example", help="使用 examples.yaml 中的示例产品名称")
    args = parser.parse_args()

    settings = load_settings()
    if args.example:
        product = load_example(args.example)
    else:
        product = collect_product_info(settings)

    result = generate_script(product, settings=settings)
    output_dir = PROJECT_ROOT / settings.get("project", {}).get("output_dir", "outputs")
    save_json = bool(settings.get("project", {}).get("save_json_result", True))
    markdown_path, json_path = write_outputs(product, result, output_dir=output_dir, save_json=save_json)

    print("\n生成完成")
    print(f"Markdown: {markdown_path}")
    if json_path:
        print(f"JSON: {json_path}")
    if result.metadata.get("generation_source") == "local_fallback":
        print(f"提示：已使用本地 fallback。原因：{result.metadata.get('fallback_reason')}")


def collect_product_info(settings: dict) -> ProductInfo:
    project_settings = settings.get("project", {})
    default_platform = project_settings.get("default_platform", "抖音")
    default_duration = project_settings.get("default_duration", 30)

    product_name = ask_required("产品名称")
    category = input("类目（可留空自动识别）：").strip()
    audience = ask_required("目标人群")
    selling_points = ask_required("卖点")
    price_mechanism = input("价格机制（可留空）：").strip()
    platform = input(f"平台（默认 {default_platform}）：").strip() or default_platform
    duration_text = input(f"视频时长秒数（默认 {default_duration}）：").strip()
    duration = int(duration_text) if duration_text else int(default_duration)
    script_mode = input("脚本模式 live_action / ai_video：").strip().lower()
    script_subtype = input("脚本子类型（可留空）：").strip()
    aspect_ratio = input("视频比例 9:16 / 16:9 / 1:1（可留空）：").strip()
    script_style = input("脚本风格（可留空）：").strip()
    video_style = input("视频风格（可留空）：").strip()
    character_setting = input("人物设定（可留空）：").strip()
    scene_setting = input("场景设定（可留空）：").strip()
    ai_tool = input("AI 工具（可留空）：").strip()
    generation_mode = input("生成模式 llm_generate_with_local_compliance / local_plus_llm_polish / local_only（默认 llm_generate_with_local_compliance）：").strip() or "llm_generate_with_local_compliance"

    return ProductInfo(
        product_name=product_name,
        category=category,
        audience=audience,
        selling_points=selling_points,
        platform=platform,
        duration=duration,
        script_mode=script_mode,
        price_mechanism=price_mechanism,
        script_style=script_style,
        ai_tool=ai_tool,
        script_subtype=script_subtype,
        aspect_ratio=aspect_ratio,
        video_style=video_style,
        character_setting=character_setting,
        scene_setting=scene_setting,
        generation_mode=generation_mode,
    ).normalized()


def ask_required(label: str) -> str:
    while True:
        value = input(f"{label}：").strip()
        if value:
            return value
        print(f"{label}不能为空")


def load_example(product_name: str) -> ProductInfo:
    for item in load_examples():
        if item["product_name"] == product_name:
            return ProductInfo(**item).normalized()
    available = "、".join(item["product_name"] for item in load_examples())
    raise SystemExit(f"未找到示例：{product_name}。可选：{available}")


if __name__ == "__main__":
    main()
