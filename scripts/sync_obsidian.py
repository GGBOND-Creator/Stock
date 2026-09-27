from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_VAULT = Path(r"C:\stock\stock")
DEFAULT_NOTE_DIR = "股票模型项目"

SYNC_MAP = {
    PROJECT_ROOT / "docs" / "obsidian_sync" / "股票模型项目" / "00-索引.md": "00-索引.md",
    PROJECT_ROOT / "docs" / "framework_presentation.md": "01-整体框架设定.md",
    PROJECT_ROOT / "docs" / "DATA_STATUS.md": "02-数据状态与接入边界.md",
    PROJECT_ROOT / "reports" / "a_share_segments.md": "03-A股市场分层观察.md",
    PROJECT_ROOT / "docs" / "CONVERSATION_MIGRATION.md": "04-对话迁移记录.md",
    PROJECT_ROOT / "docs" / "NATURAL_ENVIRONMENT_MODEL.md": "05-自然环境模型.md",
    PROJECT_ROOT / "docs" / "STOCK_MOTION_MODEL.md": "06-股票运动模型.md",
    PROJECT_ROOT / "docs" / "A_SHARE_INDUSTRY_NETWORK.md": "07-A股产业网络.md",
    PROJECT_ROOT / "docs" / "NETWORK_SIGNAL_MODEL.md": "08-网络信息素信号模型.md",
    PROJECT_ROOT / "docs" / "HUMAN_NEED_RESOURCE_NETWORK.md": "09-需求资源生产网络.md",
    PROJECT_ROOT / "docs" / "ACCOUNT_MIGRATION_BRIEF.md": "10-账号迁移摘要.md",
    PROJECT_ROOT / "docs" / "obsidian_sync" / "股票模型项目" / "99-同步规则.md": "99-同步规则.md",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Sync project notes to the Obsidian vault.")
    parser.add_argument("--vault", default=str(DEFAULT_VAULT), help="Obsidian vault path.")
    parser.add_argument("--note-dir", default=DEFAULT_NOTE_DIR, help="Subdirectory inside the vault.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    target_dir = Path(args.vault) / args.note_dir
    target_dir.mkdir(parents=True, exist_ok=True)

    for source, target_name in SYNC_MAP.items():
        if not source.exists():
            print(f"Skipped missing source: {source}")
            continue
        target = target_dir / target_name
        shutil.copy2(source, target)
        print(f"Synced: {source.relative_to(PROJECT_ROOT)} -> {target}")


if __name__ == "__main__":
    main()
