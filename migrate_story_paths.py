"""
迁移脚本：将 ProjectSekai-story 仓库的路径结构迁移到与前端路由一致的路径结构

上游路径 → 目标路径映射：
  story_{lang}/main/{seq} {name}/{scenarioId} {title}.txt → story/main/{seq}/{scenarioId}.txt
  story_{lang}/event/{id} {name} ({banner})/{storyId}-{epNo} {title}.txt → story/event/{id}/{epNo}.txt
  story_{lang}/card/{unit}_{chara}/{cardId} {rest}.txt → story/card/{cardId}.txt
  story_{lang}/area/talk_{category}.txt → story/area/{category}/{actionSetId}.txt (需拆分)
  story_{lang}/self/{unit}_{chara}.txt → story/self/{charaId}.txt
  story_{lang}/special/sp{id} {title}.txt → story/special/{id}.txt

合并策略：cn 和 jp 的内容合并到统一的 story/ 目录，cn 优先（cn 有的内容使用 cn，cn 没有的使用 jp）。
实现方式：先迁移 jp，再迁移 cn（cn 会覆盖 jp 同名文件）。

使用方法：
  python migrate_story_paths.py [--repo-dir REPO_DIR] [--dry-run] [--skip-area-split]

参数：
  --repo-dir         仓库根目录路径（默认当前目录）
  --dry-run          仅打印迁移计划，不实际执行
  --skip-area-split  跳过 area 文件的拆分（推荐使用，area 拆分较复杂，可后续手动处理）
"""

import os
import re
import shutil
import argparse
import json
import sys
from pathlib import Path

# 设置标准输出编码为 UTF-8，避免 Windows 控制台编码问题
if sys.platform == 'win32':
    import codecs
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'ignore')


# 角色名 → charaId 映射（从 gameCharacters.json 获取）
CHARA_NAME_TO_ID = {
    # CN names
    '星乃一歌': 1, '天马咲希': 2, '望月穗波': 3, '日野森志步': 4,
    '花里实乃理': 5, '桐谷遥': 6, '桃井爱莉': 7, '日野森雫': 8,
    '小豆泽心羽': 9, '白石杏': 10, '东云彰人': 11, '青柳冬弥': 12,
    '天马司': 13, '凤笑梦': 14, '草薙宁宁': 15, '神代类': 16,
    '宵崎奏': 17, '朝比奈真冬': 18, '东云绘名': 19, '晓山瑞希': 20,
    '初音未来': 21, '镜音铃': 22, '镜音连': 23, '巡音流歌': 24,
    'MEIKO': 25, 'KAITO': 26,
    # JP names
    '星乃一歌': 1, '天馬咲希': 2, '望月穂波': 3, '日野森志歩': 4,
    '花里みのり': 5, '桐谷遥': 6, '桃井愛莉': 7, '日野森雫': 8,
    '小豆沢こはね': 9, '白石杏': 10, '東雲彰人': 11, '青柳冬弥': 12,
    '天馬司': 13, '鳳えむ': 14, '草薙寧々': 15, '神代類': 16,
    '宵崎奏': 17, '朝比奈まふゆ': 18, '東雲絵名': 19, '暁山瑞希': 20,
    '初音ミク': 21, '鏡音リン': 22, '鏡音レン': 23, '巡音ルカ': 24,
}


def migrate_main(repo_dir: Path, dry_run: bool):
    """迁移主线剧情: story_{lang}/main/{seq} {name}/{scenarioId} {title}.txt → story/main/{seq}/{scenarioId}.txt

    合并策略：先迁移 jp，再迁移 cn（cn 覆盖 jp 同名文件，实现 cn 优先）
    """
    count = 0
    
    # 按语言排序：jp 在前，cn 在后
    for lang in ['jp', 'cn']:
        lang_dir = repo_dir / f'story_{lang}' / 'main'
        if not lang_dir.exists():
            continue
        
        # 遍历每个组合目录，例如 "2 Leo／need"
        for seq_dir in lang_dir.iterdir():
            if not seq_dir.is_dir():
                continue
            
            dir_name = seq_dir.name  # e.g. "2 Leo／need" or "1 バーチャル・シンガー"
            # 提取 seq: "{seq} {name}"
            seq = dir_name.split(' ')[0]
            
            for txt_file in seq_dir.iterdir():
                if not txt_file.is_file() or not txt_file.name.endswith('.txt'):
                    continue
                # 提取 scenarioId: "{scenarioId} {title}.txt"
                scenario_id = txt_file.name.split(' ')[0]
                
                new_path = repo_dir / 'story' / 'main' / seq / f'{scenario_id}.txt'
                if dry_run:
                    print(f'[DRY-RUN] [{lang}] {txt_file.relative_to(repo_dir)} → {new_path.relative_to(repo_dir)}')
                else:
                    new_path.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(str(txt_file), str(new_path))
                count += 1
    
    print(f'[DONE] Migrated {count} main files')


def migrate_event(repo_dir: Path, dry_run: bool):
    """迁移活动剧情: story_{lang}/event/{id} {name} ({banner})/{storyId}-{epNo} {title}.txt → story/event/{id}/{epNo}.txt

    合并策略：先迁移 jp，再迁移 cn（cn 覆盖 jp 同名文件，实现 cn 优先）
    """
    count = 0
    
    # 按语言排序：jp 在前，cn 在后
    for lang in ['jp', 'cn']:
        lang_dir = repo_dir / f'story_{lang}' / 'event'
        if not lang_dir.exists():
            continue
        
        for event_dir in lang_dir.iterdir():
            if not event_dir.is_dir():
                continue
            
            dir_name = event_dir.name  # e.g. "001 雨过天晴的启明星 (Ln_天马咲希)"
            # 提取 event_id: "{id:03d} {rest}"
            event_id = str(int(dir_name.split(' ')[0]))  # 去除前导零
            
            for txt_file in event_dir.iterdir():
                if not txt_file.is_file() or not txt_file.name.endswith('.txt'):
                    continue
                # 提取 episodeNo: "{storyId}-{epNo} {title}.txt" 或 "{storyId}-{epNo} {title} ({chara}).txt"
                parts = txt_file.name.split('-')
                if len(parts) >= 2:
                    ep_no_part = parts[1].split(' ')[0]
                    ep_no = str(int(ep_no_part))  # 去除前导零
                else:
                    print(f'[WARN] Cannot parse event episode file: {txt_file.name}')
                    continue
                
                new_path = repo_dir / 'story' / 'event' / event_id / f'{ep_no}.txt'
                if dry_run:
                    print(f'[DRY-RUN] [{lang}] {txt_file.relative_to(repo_dir)} → {new_path.relative_to(repo_dir)}')
                else:
                    new_path.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(str(txt_file), str(new_path))
                count += 1
    
    print(f'[DONE] Migrated {count} event files')


def migrate_card(repo_dir: Path, dry_run: bool):
    """迁移卡牌剧情: story_{lang}/card/{unit}_{chara}/{cardId} {rest}.txt → story/card/{cardId}.txt

    合并策略：先迁移 jp，再迁移 cn（cn 覆盖 jp 同名文件，实现 cn 优先）
    """
    count = 0
    
    # 按语言排序：jp 在前，cn 在后
    for lang in ['jp', 'cn']:
        lang_dir = repo_dir / f'story_{lang}' / 'card'
        if not lang_dir.exists():
            continue
        
        for chara_dir in lang_dir.iterdir():
            if not chara_dir.is_dir():
                continue
            
            for txt_file in chara_dir.iterdir():
                if not txt_file.is_file() or not txt_file.name.endswith('.txt'):
                    continue
                # 提取 cardId: "{cardId:04d}_{rest}.txt"
                card_id_str = txt_file.name.split('_')[0]
                try:
                    card_id = str(int(card_id_str))  # 去除前导零
                except ValueError:
                    print(f'[WARN] Cannot parse cardId from file: {txt_file.name}')
                    continue
                
                new_path = repo_dir / 'story' / 'card' / f'{card_id}.txt'
                if dry_run:
                    print(f'[DRY-RUN] [{lang}] {txt_file.relative_to(repo_dir)} → {new_path.relative_to(repo_dir)}')
                else:
                    new_path.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(str(txt_file), str(new_path))
                count += 1
    
    print(f'[DONE] Migrated {count} card files')


def migrate_area(repo_dir: Path, dry_run: bool, skip_split: bool):
    """迁移区域对话: story_{lang}/area/talk_{category}.txt → story/area/{category}/{actionSetId}.txt

    合并策略：先迁移 jp，再迁移 cn（cn 覆盖 jp 同名文件，实现 cn 优先）
    """
    count = 0
    
    # 按语言排序：jp 在前，cn 在后
    for lang in ['jp', 'cn']:
        lang_dir = repo_dir / f'story_{lang}' / 'area'
        if not lang_dir.exists():
            continue
        
        for txt_file in lang_dir.iterdir():
            if not txt_file.is_file() or not txt_file.name.endswith('.txt'):
                continue
            
            filename = txt_file.name  # e.g. "talk_event_002.txt" or "talk_grade1.txt"
            
            # 提取 category: "talk_{rest}.txt"
            match = re.match(r'^talk_(.+)\.txt$', filename)
            if not match:
                print(f'[WARN] Cannot parse area file: {filename}')
                continue
            category_raw = match.group(1)  # e.g. "event_002", "grade1", "limited_14", "aprilfool2022"
            
            # 转换 category: event_002 → event_2, limited_14 → limited_14, grade1 → grade1
            if category_raw.startswith('event_'):
                event_id = str(int(category_raw.split('_')[1]))  # 去除前导零
                category = f'event_{event_id}'
            elif category_raw.startswith('limited_'):
                area_id = str(int(category_raw.split('_')[1]))  # 去除前导零
                category = f'limited_{area_id}'
            else:
                category = category_raw  # grade1, grade2, theater, aprilfool2022, etc.
            
            if skip_split:
                # 不拆分，直接复制整个文件到 category 目录下，用特殊文件名
                new_path = repo_dir / 'story' / 'area' / category / '_all.txt'
                if dry_run:
                    print(f'[DRY-RUN] [{lang}] {txt_file.relative_to(repo_dir)} → {new_path.relative_to(repo_dir)} (no split)')
                else:
                    new_path.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(str(txt_file), str(new_path))
                count += 1
            else:
                # 拆分合并文件为按 scenarioId 独立的文件
                # 文件内容格式: "{index} {id}:{scenarioId}\n\n【地点】\n\n（登场角色：...）\n\n对话内容...\n\n\n"
                content = txt_file.read_text(encoding='utf-8')
                
                # 按三个连续换行符分段
                segments = re.split(r'\n\n\n', content)
                
                for seg in segments:
                    seg = seg.strip()
                    if not seg:
                        continue
                    
                    # 提取第一行的 index、id 和 scenarioId
                    # 格式: "{index} {id}:{scenarioId}"
                    first_line_match = re.match(r'^(\d+)\s+\d+:(\S+)', seg)
                    if first_line_match:
                        scenario_id = first_line_match.group(2)  # 使用 scenarioId 作为文件名
                        
                        new_path = repo_dir / 'story' / 'area' / category / f'{scenario_id}.txt'
                        if not dry_run:
                            new_path.parent.mkdir(parents=True, exist_ok=True)
                            new_path.write_text(seg, encoding='utf-8')
                        else:
                            print(f'[DRY-RUN] [{lang}] ... → {new_path.relative_to(repo_dir)}')
                        count += 1
                
                if dry_run and count > 0:
                    print(f'[DRY-RUN] [{lang}] {txt_file.relative_to(repo_dir)} → split into files in story/area/{category}/')
    
    print(f'[DONE] Migrated {count} area files')


def migrate_self(repo_dir: Path, dry_run: bool):
    """迁移自我介绍: story_{lang}/self/{unit}_{chara}.txt → story/self/{charaId}.txt

    合并策略：先迁移 jp，再迁移 cn（cn 覆盖 jp 同名文件，实现 cn 优先）
    """
    count = 0
    
    # 按语言排序：jp 在前，cn 在后
    for lang in ['jp', 'cn']:
        lang_dir = repo_dir / f'story_{lang}' / 'self'
        if not lang_dir.exists():
            continue
        
        for txt_file in lang_dir.iterdir():
            if not txt_file.is_file() or not txt_file.name.endswith('.txt'):
                continue
            
            filename = txt_file.name  # e.g. "Ln_天马咲希.txt"
            
            # 提取角色名: "{unitAbbr}_{charaName}.txt"
            chara_info = filename[:-4]  # 去除 .txt
            chara_name = chara_info.split('_', 1)[1] if '_' in chara_info else chara_info
            chara_id = CHARA_NAME_TO_ID.get(chara_name)
            if chara_id is None:
                print(f'[WARN] Cannot find charaId for: {chara_name} in {filename}')
                continue
            
            new_path = repo_dir / 'story' / 'self' / f'{chara_id}.txt'
            if dry_run:
                print(f'[DRY-RUN] [{lang}] {txt_file.relative_to(repo_dir)} → {new_path.relative_to(repo_dir)}')
            else:
                new_path.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(str(txt_file), str(new_path))
            count += 1
    
    print(f'[DONE] Migrated {count} self files')


def migrate_special(repo_dir: Path, dry_run: bool):
    """迁移特殊剧情: story_{lang}/special/sp{id} {title}.txt → story/special/{id}.txt

    合并策略：先迁移 jp，再迁移 cn（cn 覆盖 jp 同名文件，实现 cn 优先）
    """
    count = 0
    
    # 按语言排序：jp 在前，cn 在后
    for lang in ['jp', 'cn']:
        lang_dir = repo_dir / f'story_{lang}' / 'special'
        if not lang_dir.exists():
            continue
        
        for txt_file in lang_dir.iterdir():
            if not txt_file.is_file() or not txt_file.name.endswith('.txt'):
                continue
            
            filename = txt_file.name  # e.g. "sp003_1周年跨年倒计时动画01.txt"
            
            # 提取 id: "sp{id:03d}_{rest}.txt"
            match = re.match(r'^sp(\d+)', filename)
            if not match:
                print(f'[WARN] Cannot parse special file: {filename}')
                continue
            sp_id = str(int(match.group(1)))  # 去除前导零
            
            new_path = repo_dir / 'story' / 'special' / f'{sp_id}.txt'
            if dry_run:
                print(f'[DRY-RUN] [{lang}] {txt_file.relative_to(repo_dir)} → {new_path.relative_to(repo_dir)}')
            else:
                new_path.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(str(txt_file), str(new_path))
            count += 1
    
    print(f'[DONE] Migrated {count} special files')


def merge_lang_dirs(repo_dir: Path, dry_run: bool):
    """合并已有的 cn/ 和 jp/ 目录到统一的 story/ 目录。

    合并策略：先复制 jp，再复制 cn（cn 覆盖 jp 同名文件，实现 cn 优先 jp 兜底）。
    """
    story_dir = repo_dir / 'story'
    jp_dir = repo_dir / 'jp'
    cn_dir = repo_dir / 'cn'

    if not jp_dir.exists() and not cn_dir.exists():
        print(f'[SKIP] No jp/ or cn/ directories to merge')
        return

    count = 0

    # 先处理 jp，再处理 cn（cn 覆盖 jp）
    for lang_dir in [jp_dir, cn_dir]:
        if not lang_dir.exists():
            continue
        lang = lang_dir.name
        for src_file in lang_dir.rglob('*'):
            if not src_file.is_file():
                continue
            # 计算相对路径（去掉 lang 前缀）
            rel_path = src_file.relative_to(lang_dir)
            dst_file = story_dir / rel_path
            if dry_run:
                print(f'[DRY-RUN] [{lang}] {src_file.relative_to(repo_dir)} → {dst_file.relative_to(repo_dir)}')
            else:
                dst_file.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(str(src_file), str(dst_file))
            count += 1

    # 删除旧的 cn/ 和 jp/ 目录
    if not dry_run:
        for lang_dir in [jp_dir, cn_dir]:
            if lang_dir.exists():
                shutil.rmtree(str(lang_dir))
                print(f'[CLEAN] Removed {lang_dir.name}/')

    print(f'[DONE] Merged {count} files from cn/ + jp/ into story/')


def main():
    parser = argparse.ArgumentParser(description='Migrate story files to new path structure')
    parser.add_argument('--repo-dir', type=str, default='.', help='Repository root directory')
    parser.add_argument('--dry-run', action='store_true', help='Only print migration plan, do not execute')
    parser.add_argument('--skip-area-split', action='store_true', help='Skip area file splitting')
    args = parser.parse_args()

    repo_dir = Path(args.repo_dir).resolve()
    print(f'Repository directory: {repo_dir}')
    print(f'Dry run: {args.dry_run}')
    print(f'Skip area split: {args.skip_area_split}')
    print()

    # Step 1: 合并已有的 cn/ jp/ 目录到 story/（兼容旧版本）
    merge_lang_dirs(repo_dir, args.dry_run)
    print()

    # Step 2: 迁移新格式目录（story_{lang}/story_*）
    migrate_main(repo_dir, args.dry_run)
    print()
    migrate_event(repo_dir, args.dry_run)
    print()
    migrate_card(repo_dir, args.dry_run)
    print()
    migrate_area(repo_dir, args.dry_run, args.skip_area_split)
    print()
    migrate_self(repo_dir, args.dry_run)
    print()
    migrate_special(repo_dir, args.dry_run)
    print()
    
    print('Migration complete!')


if __name__ == '__main__':
    main()
