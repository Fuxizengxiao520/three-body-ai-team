"""命令行入口。"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .llm import LLM, LLMError
from .models import read_jsonl
from .team import Team

ROOT = Path(__file__).resolve().parent.parent


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def load_roster() -> dict:
    return load_json(ROOT / "config" / "roster.json")


def load_settings() -> dict:
    path = ROOT / "config" / "settings.json"
    return load_json(path) if path.exists() else {}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="三体 AI 团队，本地多智能体协作")
    parser.add_argument(
        "command",
        choices=["demo", "run", "meeting", "ledger", "status", "roster"],
        help="demo 离线演示，run 接真实模型，meeting 临时开会",
    )
    parser.add_argument("topic", nargs="?", default="AI 团队协作的成本")
    parser.add_argument("--mock", action="store_true", help="离线演示，不调用模型")
    parser.add_argument("--auto-approve", action="store_true", help="跳过人工放行")
    parser.add_argument("--model", default=None, help="覆盖配置里的模型名")
    parser.add_argument("--peak", action="store_true", help="按峰时价格记账")
    parser.add_argument("--rounds", type=int, default=1, help="会议轮次")
    args = parser.parse_args(argv)

    if args.command == "roster":
        roster = load_roster()
        for role in roster["roles"]:
            mark = "启用" if role["name"] in roster["active"] else "待命"
            print(mark, role["name"], role["job"])
        return 0

    if args.command == "demo":
        args.mock = True
        args.auto_approve = True

    settings = load_settings()
    llm = LLM(
        base_url=settings.get("base_url"),
        model=args.model or settings.get("model"),
        timeout=int(settings.get("timeout_seconds", 60)),
        retries=int(settings.get("retries", 2)),
        mock=args.mock,
    )
    team = Team(
        ROOT,
        llm,
        load_roster(),
        peak=args.peak or bool(settings.get("peak_pricing", False)),
        auto_approve=args.auto_approve,
    )

    try:
        if args.command in ("demo", "run"):
            report = team.run(args.topic)
            print(json.dumps(report, ensure_ascii=False, indent=2))
            print("\n交接消息 state/mailbox.jsonl")
            print("会议纪要 state/meetings.jsonl")
            print("产出文件 state/artifacts")
            print("账本 state/ledger.jsonl")
        elif args.command == "meeting":
            resolution = team.meeting(args.topic, rounds=args.rounds)
            for item in resolution["transcript"]:
                print(item["speaker"], item["line"])
            print("决议", resolution["decision"])
        elif args.command == "ledger":
            print(json.dumps(team.ledger.summary(), ensure_ascii=False, indent=2))
        elif args.command == "status":
            print("交接消息", len(read_jsonl(team.mailbox)))
            print("会议次数", len(read_jsonl(team.state / "meetings.jsonl")))
            print("决策记录", len(read_jsonl(team.state / "decisions.jsonl")))
            print("账本", json.dumps(team.ledger.summary(), ensure_ascii=False))
    except LLMError as error:
        print("错误", error)
        return 1
    return 0
