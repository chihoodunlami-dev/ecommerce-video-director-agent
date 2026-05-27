from director_agent.category import recognize_category
from director_agent.config import load_category_rules, load_examples


def test_recognizes_example_categories():
    expected = {
        "乳霜纸": "母婴纸品类",
        "生姜洗发水": "洗护个护类",
        "洗护三件套": "洗护个护类",
        "免浆牛蛙块": "冻品餐饮类",
        "1688包装袋": "1688工厂定制类",
    }

    for example in load_examples():
        category = recognize_category(
            example["product_name"],
            example["selling_points"],
            example.get("category", ""),
        )
        assert category == expected[example["product_name"]]


def test_user_category_has_priority():
    assert recognize_category("乳霜纸", "柔软", "母婴用品") == "母婴用品"


def test_category_rules_include_priority_categories():
    names = {item["name"] for item in load_category_rules()["categories"]}

    assert {
        "母婴纸品类",
        "洗护个护类",
        "食品零食类",
        "冻品餐饮类",
        "家清日用品类",
        "美妆护肤类",
        "1688工厂定制类",
        "宠物用品类",
        "厨房用品类",
    }.issubset(names)
