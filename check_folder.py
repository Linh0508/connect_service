#!/usr/bin/env python3
"""
Script kiểm tra cấu trúc dự án B6 Core Business
Bỏ qua các thư mục: venv, __pycache__, .git, node_modules, reports, .venv
"""

import os
import sys
from pathlib import Path

# Các thư mục và file cần bỏ qua
IGNORE_DIRS = {
    'venv', '.venv', '__pycache__', '.git', 'node_modules', 
    'reports', '.pytest_cache', '.mypy_cache', '.coverage',
    'htmlcov', 'dist', 'build', '*.egg-info', '.idea', '.vscode'
}

IGNORE_FILES = {
    '*.pyc', '*.pyo', '*.so', '*.dll', '*.dylib',
    '.DS_Store', 'Thumbs.db', '*.log', '*.pid'
}

def should_ignore_path(path: Path, is_dir: bool = False) -> bool:
    """Kiểm tra xem đường dẫn có nên bỏ qua không"""
    name = path.name
    
    # Bỏ qua theo tên thư mục
    if is_dir and name in IGNORE_DIRS:
        return True
    
    # Bỏ qua theo pattern
    for pattern in IGNORE_FILES:
        if name.endswith(pattern.replace('*', '')):
            return True
    
    return False

def print_tree(directory: Path, prefix: str = "", is_last: bool = True, level: int = 0, max_level: int = 4):
    """In cấu trúc thư mục dạng tree"""
    if level > max_level:
        return
    
    # Sắp xếp: thư mục trước, file sau
    items = []
    try:
        for item in sorted(directory.iterdir()):
            if should_ignore_path(item, item.is_dir()):
                continue
            items.append(item)
    except PermissionError:
        return
    
    # Phân loại: thư mục trước, file sau
    dirs = [item for item in items if item.is_dir()]
    files = [item for item in items if item.is_file()]
    
    for i, item in enumerate(dirs):
        is_last_item = (i == len(dirs) - 1 and len(files) == 0)
        
        # Chọn ký tự hiển thị
        if is_last_item:
            connector = "└── "
            next_prefix = prefix + "    "
        else:
            connector = "├── "
            next_prefix = prefix + "│   "
        
        # In thư mục
        print(f"{prefix}{connector}\033[94m{item.name}/\033[0m")
        
        # Đệ quy vào thư mục con
        print_tree(item, next_prefix, is_last_item, level + 1, max_level)
    
    for i, item in enumerate(files):
        is_last_item = (i == len(files) - 1)
        
        # Chọn ký tự hiển thị
        if is_last_item:
            connector = "└── "
        else:
            connector = "├── "
        
        # Định dạng file dựa trên extension
        name = item.name
        if name.endswith('.py'):
            name = f"\033[92m{name}\033[0m"  # Python files - green
        elif name.endswith('.yaml') or name.endswith('.yml'):
            name = f"\033[93m{name}\033[0m"  # YAML files - yellow
        elif name.endswith('.json'):
            name = f"\033[96m{name}\033[0m"  # JSON files - cyan
        elif name.endswith('.md'):
            name = f"\033[95m{name}\033[0m"  # Markdown files - magenta
        elif name.endswith('.sh'):
            name = f"\033[91m{name}\033[0m"  # Shell scripts - red
        elif name in ['Dockerfile', 'Dockerfile.ai', 'Makefile', '.env.example', '.dockerignore']:
            name = f"\033[36m{name}\033[0m"  # Config files - cyan
        
        print(f"{prefix}{connector}{name}")

def count_files(directory: Path, level: int = 0) -> dict:
    """Đếm số lượng file và thư mục"""
    if level > 0 and should_ignore_path(directory, True):
        return {'dirs': 0, 'files': 0}
    
    result = {'dirs': 1, 'files': 0}
    
    try:
        for item in directory.iterdir():
            if should_ignore_path(item, item.is_dir()):
                continue
            
            if item.is_dir():
                sub = count_files(item, level + 1)
                result['dirs'] += sub['dirs']
                result['files'] += sub['files']
            else:
                result['files'] += 1
    except PermissionError:
        pass
    
    return result

def list_all_files(directory: Path) -> list:
    """Liệt kê tất cả file (không phân cấp)"""
    files = []
    
    if should_ignore_path(directory, True):
        return files
    
    try:
        for item in directory.iterdir():
            if should_ignore_path(item, item.is_dir()):
                continue
            
            if item.is_dir():
                files.extend(list_all_files(item))
            else:
                files.append(str(item.relative_to(Path.cwd())))
    except PermissionError:
        pass
    
    return sorted(files)

def main():
    # Lấy thư mục hiện tại
    current_dir = Path.cwd()
    
    print("=" * 70)
    print("🏗️  CẤU TRÚC DỰ ÁN B6 CORE BUSINESS")
    print("=" * 70)
    print(f"\n📁 Thư mục hiện tại: {current_dir}\n")
    
    # In cấu trúc tree
    print("📂 Cấu trúc thư mục:")
    print(f"\033[94m{current_dir.name}/\033[0m")
    print_tree(current_dir, "", True, 0, 5)
    
    # Thống kê
    stats = count_files(current_dir)
    
    print("\n" + "=" * 70)
    print("📊 THỐNG KÊ")
    print("=" * 70)
    
    # Danh sách tất cả file
    all_files = list_all_files(current_dir)
    
    # Phân loại file theo extension
    extensions = {}
    for f in all_files:
        ext = f.split('.')[-1] if '.' in f else 'no_ext'
        extensions[ext] = extensions.get(ext, 0) + 1
    
    print(f"\n📈 Tổng số:")
    print(f"   📁 Thư mục: {stats['dirs']}")
    print(f"   📄 File: {stats['files']}")
    
    print(f"\n📝 Phân loại theo extension:")
    for ext, count in sorted(extensions.items(), key=lambda x: x[1], reverse=True):
        if ext == 'no_ext':
            print(f"   📄 Không extension: {count} file")
        elif ext == 'py':
            print(f"   🐍 Python (.{ext}): {count} file")
        elif ext == 'yaml' or ext == 'yml':
            print(f"   📋 YAML (.{ext}): {count} file")
        elif ext == 'json':
            print(f"   📦 JSON (.{ext}): {count} file")
        elif ext == 'md':
            print(f"   📝 Markdown (.{ext}): {count} file")
        elif ext == 'sh':
            print(f"   🔧 Shell (.{ext}): {count} file")
        else:
            print(f"   📄 .{ext}: {count} file")
    
    print("\n" + "=" * 70)
    print("📋 DANH SÁCH FILE CHÍNH")
    print("=" * 70)
    
    # Hiển thị các file quan trọng
    important_files = [
        'docker-compose.yml', 'Dockerfile', 'Dockerfile.ai', '.env.example',
        'requirements.txt', 'requirements.ai.txt', 'Makefile',
        'contracts/core-business.openapi.yaml',
        'postman/collections/core-business.postman_collection.json',
        'postman/environments/environment_local.json',
        'src/core_service/main.py',
        'src/ai_service/main.py',
        'scripts/init-db.sql',
        'scripts/run-newman.sh',
        'checklists/readiness-checklist.md',
        'RUN_COMPOSE.md', 'README.md'
    ]
    
    found_files = []
    missing_files = []
    
    for f in important_files:
        if (current_dir / f).exists():
            found_files.append(f"   ✅ {f}")
        else:
            missing_files.append(f"   ❌ {f}")
    
    if found_files:
        print("\n✅ Các file đã có:")
        for f in found_files:
            print(f)
    
    if missing_files:
        print("\n⚠️ Các file đang thiếu:")
        for f in missing_files:
            print(f)
    
    # Kiểm tra các service trong docker-compose
    compose_file = current_dir / 'docker-compose.yml'
    if compose_file.exists():
        print("\n" + "=" * 70)
        print("🐳 DOCKER COMPOSE SERVICES")
        print("=" * 70)
        
        with open(compose_file, 'r') as f:
            content = f.read()
        
        services = []
        if 'postgres:' in content or 'postgres' in content:
            services.append("   ✅ PostgreSQL Database")
        if 'ai-vision:' in content:
            services.append("   ✅ AI Vision Service")
        if 'api:' in content:
            services.append("   ✅ Core Business API")
        if 'newman-tests:' in content:
            services.append("   ✅ Newman Test Runner")
        
        for s in services:
            print(s)
    
    print("\n" + "=" * 70)
    print("🏁 KẾT THÚC KIỂM TRA")
    print("=" * 70 + "\n")

if __name__ == "__main__":
    main()