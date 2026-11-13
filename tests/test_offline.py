"""离线闭环自检，无需 API key 与网络。"""

import json
import tempfile
import unittest
from pathlib import Path

from src.llm import LLM
from src.models import read_jsonl
from src.team import Team

ROOT = Path(__file__).resolve().parent.parent
ROSTER = json.loads((ROOT / "config" / "roster.json").read_text(encoding="utf-8"))


def make_team(root: Path) -> Team:
    return Team(root, LLM(mock=True), ROSTER, auto_approve=True)


class OfflineLoopTest(unittest.TestCase):
    def test_full_loop(self):
        with tempfile.TemporaryDirectory() as folder:
            team = make_team(Path(folder))
            report = team.run("多智能体协作成本")
            self.assertTrue(report["passed"])
            self.assertTrue(report["approved"])
            self.assertEqual(report["mode"], "mock")
            self.assertEqual(len(report["active_roles"]), 3)
            self.assertGreaterEqual(len(read_jsonl(team.mailbox)), 5)
            self.assertGreaterEqual(
                len(read_jsonl(team.state / "meetings.jsonl")), 1
            )
            self.assertGreaterEqual(team.ledger.summary()["calls"], 5)
            self.assertEqual(team.ledger.summary()["cost_usd"], 0.0)

    def test_meeting_has_all_roles(self):
        with tempfile.TemporaryDirectory() as folder:
            team = make_team(Path(folder))
            resolution = team.meeting("临时议题", rounds=2)
            self.assertEqual(len(resolution["transcript"]), 6)
            self.assertEqual(
                sorted({item["speaker"] for item in resolution["transcript"]}),
                sorted(ROSTER["active"]),
            )
            lines = {
                item["speaker"]: item["line"] for item in resolution["transcript"]
            }
            self.assertNotEqual(lines["维德"], lines["罗辑"])
            self.assertNotEqual(lines["维德"], lines["云天明"])

    def test_verdict_is_separate_from_execution(self):
        with tempfile.TemporaryDirectory() as folder:
            team = make_team(Path(folder))
            team.run("验收分离")
            verdict = json.loads(
                (team.state / "verdict.json").read_text(encoding="utf-8")
            )
            self.assertEqual(verdict["verifier"], "维德")
            self.assertTrue(verdict["passed"])
            self.assertTrue(verdict["human_gate_required"])


if __name__ == "__main__":
    unittest.main()
