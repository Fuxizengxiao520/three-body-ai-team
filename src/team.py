"""三体 AI 团队编排，派单、交接、临时会议、独立验收、人工放行。"""

from __future__ import annotations

from pathlib import Path

from .ledger import Ledger
from .llm import LLM
from .models import (
    Artifact,
    Message,
    TaskCard,
    append_jsonl,
    identifier,
    timestamp,
    write_json,
)


class Team:
    def __init__(
        self,
        root: Path,
        llm: LLM,
        roster: dict,
        peak: bool = False,
        auto_approve: bool = False,
    ):
        self.root = Path(root)
        self.state = self.root / "state"
        self.llm = llm
        self.roster = roster
        self.auto_approve = auto_approve
        self.active = roster.get("active", [])
        self.roles = {role["name"]: role for role in roster["roles"]}
        self.ledger = Ledger(self.state / "ledger.jsonl", peak=peak)
        self.mailbox = self.state / "mailbox.jsonl"
        self.artifacts_dir = self.state / "artifacts"
        self.state.mkdir(parents=True, exist_ok=True)

    def _send(self, sender, receiver, kind, subject, payload=None) -> Message:
        message = Message(
            identifier("msg"),
            timestamp(),
            sender,
            receiver,
            kind,
            subject,
            payload or {},
        )
        append_jsonl(self.mailbox, message.to_dict())
        return message

    def _system(self, name: str) -> str:
        role = self.roles[name]
        return (
            f"你是三体 AI 团队的{name}，岗位是{role['job']}。"
            f"职责 {role['duty']}。"
            "只做本岗工作，输出结构化内容，不替其他角色做决定，不评价自己的产出。"
        )

    def _call(self, name: str, prompt: str, note: str):
        reply = self.llm.chat(self._system(name), prompt)
        self.ledger.record(name, reply.model, reply, note=note)
        return reply

    def _artifact(self, owner, kind, task_id, content, reply) -> Artifact:
        artifact = Artifact(
            identifier("art"),
            timestamp(),
            owner,
            kind,
            task_id,
            content,
            {
                "input_tokens": reply.input_tokens,
                "output_tokens": reply.output_tokens,
            },
        )
        write_json(self.artifacts_dir / (artifact.id + ".json"), artifact.to_dict())
        return artifact

    def _prompt(self, card: TaskCard, upstream: Artifact | None = None) -> str:
        lines = [
            "任务编号 " + card.id,
            "负责人 " + card.owner,
            "目标 " + card.objective,
            "验收标准",
        ]
        lines += ["- " + item for item in card.acceptance]
        if upstream is not None:
            lines += ["", "上游交接内容，来自 " + upstream.owner, upstream.content]
        lines += ["", "请只输出成品正文，不要解释过程。"]
        return "\n".join(lines)

    def _plan(self, objective: str) -> list[TaskCard]:
        # 确定性拆单，省掉一次协调调用，同时让验收标准可被机器检查
        cards = [
            TaskCard(
                identifier("task"),
                "罗辑",
                "围绕「" + objective + "」整理 3 条前沿资讯",
                ["每条含来源与日期", "每条标注可信度", "恰好 3 条"],
            ),
            TaskCard(
                identifier("task"),
                "云天明",
                "基于上游资讯简报，为「" + objective + "」写一段文案",
                ["正文不超过 300 字", "不引入上游未出现的数字", "结尾含行动指引"],
            ),
        ]
        write_json(self.state / "task_cards.json", [card.to_dict() for card in cards])
        self._send(
            "维德",
            "全体",
            "plan",
            "任务启动，任务卡已下发",
            {"objective": objective, "cards": [card.id for card in cards]},
        )
        return cards

    def meeting(self, topic: str, context: str = "", rounds: int = 1) -> dict:
        transcript = []
        for _ in range(max(1, rounds)):
            for name in self.active:
                history = "\n".join(
                    item["speaker"] + ": " + item["line"] for item in transcript[-6:]
                )
                prompt = (
                    "临时会议主题 " + topic + "\n"
                    "背景 " + context + "\n"
                    "已有发言\n" + (history or "暂无") + "\n"
                    f"请以{name}身份发言一句，说明本岗下一步交付什么，以及对上游的要求。"
                )
                reply = self.llm.chat(self._system(name), prompt)
                self.ledger.record(name, reply.model, reply, note="临时会议")
                transcript.append(
                    {
                        "ts": timestamp(),
                        "speaker": name,
                        "line": reply.text.strip(),
                    }
                )
        resolution = {
            "ts": timestamp(),
            "topic": topic,
            "attendees": list(self.active),
            "transcript": transcript,
            "decision": "按任务卡执行，交接留痕，维德验收后交人工放行",
        }
        append_jsonl(self.state / "meetings.jsonl", resolution)
        self._send(
            "维德",
            "全体",
            "meeting",
            "临时会议纪要已归档",
            {"topic": topic, "attendees": list(self.active)},
        )
        return resolution

    def _verify(self, brief: Artifact, draft: Artifact) -> dict:
        checks = [
            {
                "item": "资讯恰好 3 条",
                "pass": sum(
                    1
                    for line in brief.content.splitlines()
                    if line.strip()[:2] in ("1.", "2.", "3.")
                )
                == 3,
            },
            {"item": "每条含来源", "pass": brief.content.count("来源") >= 3},
            {"item": "每条含日期", "pass": brief.content.count("日期") >= 3},
            {
                "item": "文案不超过 300 字",
                "pass": len(draft.content.replace("\n", "")) <= 300,
            },
            {"item": "结尾含行动指引", "pass": "行动指引" in draft.content},
        ]
        verdict = {
            "ts": timestamp(),
            "verifier": "维德",
            "principle": "执行者不自评，维德只验收不产出",
            "checks": checks,
            "passed": all(check["pass"] for check in checks),
            "human_gate_required": True,
        }
        write_json(self.state / "verdict.json", verdict)
        self._send(
            "维德",
            "人",
            "verdict",
            "验收完成，等待人工放行",
            {"passed": verdict["passed"]},
        )
        return verdict

    def _gate(self, objective: str, verdict: dict) -> bool:
        if self.auto_approve:
            approved = verdict["passed"]
            reason = "自动放行（演示模式）" if approved else "自动拦截，验收未通过"
        else:
            print("\n>>> 验收结果", "通过" if verdict["passed"] else "未通过")
            for check in verdict["checks"]:
                print("   ", "PASS" if check["pass"] else "FAIL", check["item"])
            print(">>> 产出目录", self.artifacts_dir)
            answer = input("人工放行? [y/N] ").strip().lower()
            approved = answer == "y"
            reason = "人工放行" if approved else "人工未放行"
        append_jsonl(
            self.state / "decisions.jsonl",
            {
                "ts": timestamp(),
                "objective": objective,
                "approved": approved,
                "reason": reason,
            },
        )
        return approved

    def run(self, objective: str) -> dict:
        cards = self._plan(objective)
        self.meeting("任务启动会，确认分工与验收标准", objective)

        brief_reply = self._call("罗辑", self._prompt(cards[0]), "资讯抓取")
        brief = self._artifact(
            "罗辑", "research_brief", cards[0].id, brief_reply.text, brief_reply
        )
        self._send(
            "罗辑",
            "云天明",
            "handoff",
            "资讯简报交接",
            {"artifact": brief.id, "next_task": cards[1].id},
        )

        draft_reply = self._call(
            "云天明", self._prompt(cards[1], upstream=brief), "文案撰写"
        )
        draft = self._artifact(
            "云天明", "draft", cards[1].id, draft_reply.text, draft_reply
        )
        self._send(
            "云天明", "维德", "handoff", "文案交接，请验收", {"artifact": draft.id}
        )

        verdict = self._verify(brief, draft)
        approved = self._gate(objective, verdict)
        report = {
            "objective": objective,
            "mode": "mock" if self.llm.mock else "live",
            "active_roles": self.active,
            "artifacts": [brief.id, draft.id],
            "passed": verdict["passed"],
            "approved": approved,
            "ledger": self.ledger.summary(),
            "state_dir": str(self.state),
        }
        write_json(self.state / "last_report.json", report)
        return report
