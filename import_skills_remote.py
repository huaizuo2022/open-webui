#!/usr/bin/env python3
"""
批量导入技能到远程 Open WebUI
使用方法: python3 import_skills_remote.py [--dry-run]
"""

import os
import re
import sys
import json
import requests
from pathlib import Path

# 配置
OPENWEBUI_URL = "https://expanded-wishes-compression-pst.trycloudflare.com"
SKILLS_DIRS = [
    Path.home() / ".agents" / "skills",
    Path.home() / ".codex" / "skills",
]
DRY_RUN = "--dry-run" in sys.argv

def parse_skill_md(file_path):
    """解析 SKILL.md 文件，提取 front matter 和 content"""
    try:
        content = file_path.read_text(encoding='utf-8')
    except Exception as e:
        return None
    
    pattern = r'^---\s*\n(.*?)\n---\s*\n(.*)'
    match = re.match(pattern, content, re.DOTALL)
    
    if not match:
        return {
            'name': file_path.parent.name,
            'description': '',
            'content': content,
            'meta': {'tags': []}
        }
    
    front_matter_text = match.group(1)
    skill_content = match.group(2)
    
    meta = {'tags': []}
    name = file_path.parent.name
    description = ''
    
    for line in front_matter_text.split('\n'):
        if line.startswith('name:'):
            name = line.split(':', 1)[1].strip().strip("'\"")
        elif line.startswith('description:'):
            description = line.split(':', 1)[1].strip().strip("'\"")
        elif line.startswith('tags:'):
            tags_str = line.split(':', 1)[1].strip()
            if tags_str:
                meta['tags'] = [t.strip() for t in tags_str.split(',')]
    
    return {
        'name': name,
        'description': description,
        'content': skill_content,
        'meta': meta
    }

def get_auth_token():
    """获取匿名用户 token"""
    try:
        resp = requests.get(f"{OPENWEBUI_URL}/api/v1/auths/", timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            return data.get('token')
        else:
            print(f"❌ 获取 token 失败: {resp.status_code}")
            return None
    except Exception as e:
        print(f"❌ 连接 Open WebUI 失败: {e}")
        return None

def skill_exists(token, skill_id):
    """检查技能是否已存在"""
    headers = {'Authorization': f'Bearer {token}'}
    try:
        resp = requests.get(f"{OPENWEBUI_URL}/api/v1/skills/", headers=headers, timeout=10)
        if resp.status_code == 200:
            skills = resp.json()
            return any(s.get('id') == skill_id for s in skills)
    except:
        pass
    return False

def create_skill(token, skill_data):
    """通过 API 创建技能"""
    headers = {
        'Authorization': f'Bearer {token}',
        'Content-Type': 'application/json'
    }
    
    skill_id = skill_data['name'].lower().replace(' ', '-')
    
    # 检查是否已存在
    if skill_exists(token, skill_id):
        return 'skipped', '技能已存在'
    
    payload = {
        'id': skill_id,
        'name': skill_data['name'],
        'description': skill_data['description'],
        'content': skill_data['content'],
        'meta': skill_data['meta'],
        'is_active': True
    }
    
    try:
        resp = requests.post(
            f"{OPENWEBUI_URL}/api/v1/skills/create",
            headers=headers,
            json=payload,
            timeout=30
        )
        if resp.status_code == 200:
            return True, resp.json()
        else:
            return False, resp.text[:200]
    except Exception as e:
        return False, str(e)

def main():
    print(f"🎯 目标 Open WebUI: {OPENWEBUI_URL}")
    if DRY_RUN:
        print("🔍 DRY RUN 模式，不会实际创建技能\n")
    else:
        print("")
    
    # 获取 auth token
    if not DRY_RUN:
        print("🔐 获取认证 token...")
        token = get_auth_token()
        if not token:
            print("❌ 无法获取 token，退出")
            return
        print(f"✅ Token 获取成功\n")
    
    total_success = 0
    total_skip = 0
    total_error = 0
    
    for skills_dir in SKILLS_DIRS:
        if not skills_dir.exists():
            continue
        
        print(f"📂 扫描技能目录: {skills_dir}")
        skill_dirs = [d for d in skills_dir.iterdir() if d.is_dir()]
        print(f"📊 找到 {len(skill_dirs)} 个技能目录\n")
        
        success_count = 0
        skip_count = 0
        error_count = 0
        
        for skill_dir in sorted(skill_dirs):
            if skill_dir.name.startswith('.'):
                continue
                
            skill_md = skill_dir / "SKILL.md"
            if not skill_md.exists():
                continue
            
            skill_data = parse_skill_md(skill_md)
            if not skill_data:
                error_count += 1
                continue
            
            if DRY_RUN:
                success_count += 1
                continue
            
            success, result = create_skill(token, skill_data)
            if success is True:
                success_count += 1
            elif success == 'skipped':
                skip_count += 1
            else:
                error_count += 1
        
        total_success += success_count
        total_skip += skip_count
        total_error += error_count
        
        print(f"目录: {skills_dir}")
        print(f"✅ 成功: {success_count}")
        print(f"⏭️  跳过: {skip_count}")
        print(f"❌ 失败: {error_count}")
        print("=" * 50 + "\n")
    
    print("\n" + "=" * 50)
    print(f"总计:")
    print(f"✅ 总成功: {total_success}")
    print(f"⏭️  总跳过: {total_skip}")
    print(f"❌ 总失败: {total_error}")
    print("=" * 50)

if __name__ == "__main__":
    main()
