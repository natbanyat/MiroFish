"""
Smoke test for the current OASIS profile export formats.

This validates the formats actually written by `OasisProfileGenerator`:
1. Twitter profiles export as the compact OASIS CSV format
2. Reddit profiles export as the JSON format consumed by the simulation scripts
"""

import os
import sys
import json
import csv
import tempfile

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.oasis_profile_generator import OasisProfileGenerator, OasisAgentProfile


def _check_fields(actual_fields, required_fields, label):
    """Validate required fields and return a list of errors."""
    missing = sorted(set(required_fields) - set(actual_fields))
    if missing:
        print(f"\n   [ERROR] {label} missing fields: {missing}")
        return [f"{label} missing fields: {missing}"]

    print(f"\n   [PASS] {label} contains all required fields")
    return []


def test_profile_formats():
    """Validate the exported profile files and return success/failure."""
    print("=" * 60)
    print("OASIS Profile格式测试")
    print("=" * 60)
    errors = []
    
    # 创建测试Profile数据
    test_profiles = [
        OasisAgentProfile(
            user_id=0,
            user_name="test_user_123",
            name="Test User",
            bio="A test user for validation",
            persona="Test User is an enthusiastic participant in social discussions.",
            karma=1500,
            friend_count=100,
            follower_count=200,
            statuses_count=500,
            age=25,
            gender="male",
            mbti="INTJ",
            country="China",
            profession="Student",
            interested_topics=["Technology", "Education"],
            source_entity_uuid="test-uuid-123",
            source_entity_type="Student",
        ),
        OasisAgentProfile(
            user_id=1,
            user_name="org_official_456",
            name="Official Organization",
            bio="Official account for Organization",
            persona="This is an official institutional account that communicates official positions.",
            karma=5000,
            friend_count=50,
            follower_count=10000,
            statuses_count=200,
            profession="Organization",
            interested_topics=["Public Policy", "Announcements"],
            source_entity_uuid="test-uuid-456",
            source_entity_type="University",
        ),
    ]
    
    generator = OasisProfileGenerator.__new__(OasisProfileGenerator)
    
    # 使用临时目录
    with tempfile.TemporaryDirectory() as temp_dir:
        twitter_path = os.path.join(temp_dir, "twitter_profiles.csv")
        reddit_path = os.path.join(temp_dir, "reddit_profiles.json")
        
        # 测试Twitter CSV格式
        print("\n1. 测试Twitter Profile (CSV格式)")
        print("-" * 40)
        generator._save_twitter_csv(test_profiles, twitter_path)
        
        # 读取并验证CSV
        with open(twitter_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            rows = list(reader)
            
        print(f"   文件: {twitter_path}")
        print(f"   行数: {len(rows)}")
        print(f"   表头: {list(rows[0].keys())}")
        print(f"\n   示例数据 (第1行):")
        for key, value in rows[0].items():
            print(f"     {key}: {value}")
        
        required_twitter_fields = ['user_id', 'name', 'username', 'user_char', 'description']
        errors.extend(_check_fields(rows[0].keys(), required_twitter_fields, "Twitter CSV"))

        if rows[0]['username'] != test_profiles[0].user_name:
            errors.append("Twitter CSV username mismatch")
            print("\n   [ERROR] Twitter CSV username mismatch")
        if test_profiles[0].persona not in rows[0]['user_char']:
            errors.append("Twitter CSV user_char does not include persona")
            print("\n   [ERROR] Twitter CSV user_char does not include persona")
        
        # 测试Reddit JSON格式
        print("\n2. 测试Reddit Profile (JSON详细格式)")
        print("-" * 40)
        generator._save_reddit_json(test_profiles, reddit_path)
        
        # 读取并验证JSON
        with open(reddit_path, 'r', encoding='utf-8') as f:
            reddit_data = json.load(f)
        
        print(f"   文件: {reddit_path}")
        print(f"   条目数: {len(reddit_data)}")
        print(f"   字段: {list(reddit_data[0].keys())}")
        print(f"\n   示例数据 (第1条):")
        print(json.dumps(reddit_data[0], ensure_ascii=False, indent=4))
        
        required_reddit_fields = [
            'user_id', 'username', 'name', 'bio', 'persona',
            'karma', 'created_at', 'age', 'gender', 'mbti', 'country'
        ]
        optional_reddit_fields = ['profession', 'interested_topics']

        errors.extend(_check_fields(reddit_data[0].keys(), required_reddit_fields, "Reddit JSON"))

        if reddit_data[0]['username'] != test_profiles[0].user_name:
            errors.append("Reddit JSON username mismatch")
            print("\n   [ERROR] Reddit JSON username mismatch")
        if reddit_data[0]['gender'] not in {'male', 'female', 'other'}:
            errors.append("Reddit JSON gender is not normalized")
            print("\n   [ERROR] Reddit JSON gender is not normalized")

        present_optional = sorted(set(optional_reddit_fields) & set(reddit_data[0].keys()))
        print(f"   [INFO] Optional fields present: {present_optional}")
    
    print("\n" + "=" * 60)
    if errors:
        print(f"测试失败，共 {len(errors)} 个问题")
        for error in errors:
            print(f" - {error}")
    else:
        print("测试通过!")
    print("=" * 60)
    return not errors


def show_expected_formats():
    """显示当前导出的Profile格式参考"""
    print("\n" + "=" * 60)
    print("OASIS 期望的Profile格式参考")
    print("=" * 60)
    
    print("\n1. Twitter Profile (CSV格式)")
    print("-" * 40)
    twitter_example = """user_id,name,username,user_char,description
0,User Zero,user0,I am user zero with interests in technology. User Zero is analytical and cautious.,I am user zero with interests in technology.
1,User One,user1,Tech enthusiast and coffee lover. User One reacts quickly to breaking news.,Tech enthusiast and coffee lover."""
    print(twitter_example)
    
    print("\n2. Reddit Profile (JSON详细格式)")
    print("-" * 40)
    reddit_example = [
        {
            "user_id": 0,
            "username": "millerhospitality",
            "name": "James Miller",
            "bio": "Passionate about hospitality & tourism.",
            "persona": "James is a seasoned professional in the Hospitality & Tourism industry...",
            "karma": 1200,
            "created_at": "2026-03-17",
            "age": 40,
            "gender": "male",
            "mbti": "ESTJ",
            "country": "UK",
            "profession": "Hospitality & Tourism",
            "interested_topics": ["Economics", "Business"]
        }
    ]
    print(json.dumps(reddit_example, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    success = test_profile_formats()
    show_expected_formats()
    sys.exit(0 if success else 1)

