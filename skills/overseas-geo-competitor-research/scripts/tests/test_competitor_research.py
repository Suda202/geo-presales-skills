from __future__ import annotations

import importlib.util
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "competitor_research.py"
SPEC = importlib.util.spec_from_file_location("competitor_research", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader
SPEC.loader.exec_module(MODULE)


def config(known=None):
    known_competitors = [{"name": "Known"}] if known is None else known
    return MODULE.normalize_input({
        "topic": "AI 搜索可见性监测平台",
        "market": "US",
        "current_date": "2026-07-24",
        "target": {
            "name": "Target",
            "official_domain": "target.example",
            "product_name": "Target",
        },
        "known_competitors": known_competitors,
    })


def evidence(prefix, domain, *, position_date="2026-06-10", official_url=None):
    return [
        {
            "evidence_id": f"{prefix}-OFFICIAL",
            "url": official_url or f"https://{domain}/product",
            "title": "产品页",
            "source_type": "official",
            "published_at": None,
            "accessed_at": "2026-07-24",
            "claims": ["产品仍在运营", "解决相同核心任务"],
        },
        {
            "evidence_id": f"{prefix}-INDEPENDENT",
            "url": f"https://reviews.example/{prefix.lower()}",
            "title": "独立市场评测",
            "source_type": "independent_review",
            "published_at": position_date,
            "accessed_at": "2026-07-24",
            "claims": ["市场地位", "目标客户与采购方式"],
        },
    ]


def candidate(prefix, name, domain, position, *, source="discovered", official_url=None):
    evidence_ids = [f"{prefix}-OFFICIAL", f"{prefix}-INDEPENDENT"]
    bindings = {
        "activity_status": [f"{prefix}-OFFICIAL"],
        "direct_substitute": evidence_ids,
        "same_purchase_set": evidence_ids,
        "market_position": [f"{prefix}-INDEPENDENT"],
        "sub_track": evidence_ids,
        "product_form": [f"{prefix}-OFFICIAL"],
        "target_users": evidence_ids,
        "core_job": evidence_ids,
        "buying_motion": evidence_ids,
        "status_similarity": [f"{prefix}-INDEPENDENT"],
        "specialty_fit": evidence_ids,
    }
    dimensions = {
        "sub_track": 5,
        "product_form": 5,
        "target_users": 4,
        "core_job": 5,
        "buying_motion": 4,
        "status_similarity": 4,
        "specialty_fit": 4 if position == "challenger" else 3,
    }
    return {
        "candidate": {
            "canonical_name": name,
            "official_domain": domain,
            "aliases": [],
            "source": source,
            "activity_status": "active",
            "direct_substitute": True,
            "same_purchase_set": True,
            "market_position": position,
            "dimensions": dimensions,
            "evidence_bindings": bindings,
            "evidence_ids": evidence_ids,
        },
        "evidence": evidence(prefix, domain, official_url=official_url),
    }


def research(rows, *, input_hash, researched_at="2026-07-24"):
    return {
        "input_hash": input_hash,
        "researched_at": researched_at,
        "evidence": [item for row in rows for item in row["evidence"]],
        "candidates": [row["candidate"] for row in rows],
    }


class CompetitorResearchTests(unittest.TestCase):
    def test_accepts_no_user_competitor_and_selects_three_discovered(self):
        cfg = config([])
        rows = [
            candidate("LEADER", "Leader", "leader.example", "leader"),
            candidate("PEER", "Peer", "peer.example", "peer"),
            candidate("CHALLENGER", "Challenger", "challenger.example", "challenger"),
        ]
        result = MODULE.finalize(cfg, research(rows, input_hash=cfg["input_hash"]))
        self.assertEqual(result["status"], "frozen")
        self.assertEqual(result["selection_count"], 3)
        self.assertEqual(result["selection_strategy"]["user_provided_count"], 0)
        self.assertEqual(result["selection_strategy"]["discovery_mode"], "from_scratch")
        self.assertTrue(all(item["source"] == "discovered" for item in result["formal_competitors"]))
        self.assertTrue(all(item["same_purchase_set_eligible"] for item in result["formal_competitors"]))

    def test_rejects_more_than_three_user_candidates(self):
        with self.assertRaisesRegex(MODULE.ContractError, "最多包含 3"):
            config([{"name": f"Competitor {index}"} for index in range(4)])

    def test_selects_peer_leader_and_challenger(self):
        cfg = config([{"name": "Peer", "official_domain": "peer.example"}])
        rows = [
            candidate("PEER", "Peer", "peer.example", "peer"),
            candidate("LEADER", "Leader", "leader.example", "leader"),
            candidate("CHALLENGER", "Challenger", "challenger.example", "challenger"),
        ]
        result = MODULE.finalize(cfg, research(rows, input_hash=cfg["input_hash"]))
        self.assertEqual(result["status"], "frozen")
        self.assertEqual(
            [item["portfolio_role"] for item in result["formal_competitors"]],
            ["销售指定竞品", "头部直接竞品", "垂直挑战者"],
        )
        self.assertEqual(result["selection_count"], 3)
        self.assertEqual(
            result["selection_strategy"]["primary_order"],
            ["same_purchase_set_gate", "eligible_user_provided_first", "leader_representativeness", "total_score"],
        )
        self.assertTrue(result["selection_strategy"]["user_provided_retained"])

    def test_direct_leader_is_selected_before_higher_scoring_direct_peer(self):
        cfg = config([{"name": "Known", "official_domain": "known.example"}])
        low_score_leader = candidate("LEADER", "Category Leader", "leader.example", "leader")
        low_score_leader["candidate"]["dimensions"].update({
            "sub_track": 4,
            "core_job": 4,
            "product_form": 3,
            "target_users": 3,
            "buying_motion": 5,
            "status_similarity": 5,
            "specialty_fit": 4,
        })
        rows = [
            candidate("KNOWN", "Known", "known.example", "peer"),
            low_score_leader,
            candidate("PEER", "Higher Score Peer", "peer.example", "peer"),
            candidate("CHALLENGER", "Higher Score Challenger", "challenger.example", "challenger"),
        ]
        result = MODULE.finalize(cfg, research(rows, input_hash=cfg["input_hash"]))
        selected = result["formal_competitors"]
        leader = next(item for item in selected if item["name"] == "Category Leader")
        peer = next(item for item in selected if item["name"] == "Higher Score Peer")
        self.assertLess(leader["score"], peer["score"])
        self.assertEqual([item["name"] for item in selected], ["Known", "Category Leader", "Higher Score Peer"])

    def test_direct_nonleaders_are_selected_before_adjacent_leader(self):
        cfg = config([{"name": "Known", "official_domain": "known.example"}])
        adjacent_leader = candidate("ADJ", "Adjacent Leader", "adjacent.example", "leader")
        adjacent_leader["candidate"]["direct_substitute"] = False
        rows = [
            candidate("KNOWN", "Known", "known.example", "peer"),
            candidate("PEER", "Direct Peer", "peer.example", "peer"),
            candidate("CHALLENGER", "Direct Challenger", "challenger.example", "challenger"),
            adjacent_leader,
        ]
        result = MODULE.finalize(cfg, research(rows, input_hash=cfg["input_hash"]))
        names = [item["name"] for item in result["formal_competitors"]]
        self.assertIn("Direct Peer", names)
        self.assertIn("Direct Challenger", names)
        self.assertNotIn("Adjacent Leader", names)

    def test_unverified_leader_does_not_receive_head_brand_priority(self):
        cfg = config([{"name": "Known", "official_domain": "known.example"}])
        stale_leader = candidate("STALE", "Stale Leader", "stale.example", "leader")
        stale_leader["evidence"][1]["published_at"] = "2024-01-01"
        adjacent_peer_one = candidate("PEER1", "Adjacent Peer One", "peer-one.example", "peer")
        adjacent_peer_two = candidate("PEER2", "Adjacent Peer Two", "peer-two.example", "peer")
        rows = [
            candidate("KNOWN", "Known", "known.example", "peer"),
            stale_leader,
            adjacent_peer_one,
            adjacent_peer_two,
        ]
        result = MODULE.finalize(cfg, research(rows, input_hash=cfg["input_hash"]))
        names = [item["name"] for item in result["formal_competitors"]]
        self.assertNotIn("Stale Leader", names)
        stale_audit = next(item for item in result["candidate_audit"] if item["name"] == "Stale Leader")
        self.assertFalse(stale_audit["leader_representativeness_verified"])

    def test_evil_subdomain_does_not_match_official_domain(self):
        cfg = config()
        row = candidate(
            "EVIL",
            "Evil",
            "brand.com",
            "peer",
            official_url="https://brand.com.evil.com/product",
        )
        scored = MODULE.score_candidate(
            row["candidate"],
            MODULE.evidence_index(research([row], input_hash=cfg["input_hash"]), cfg),
            cfg,
        )
        self.assertFalse(scored["qualified"])
        self.assertIn("缺少与官网域名一致的官方证据", scored["reasons"])

    def test_missing_official_evidence_is_rejected(self):
        cfg = config()
        row = candidate("NOOFF", "No Official", "nooff.example", "peer")
        row["evidence"] = [row["evidence"][1]]
        row["candidate"]["evidence_ids"] = ["NOOFF-INDEPENDENT"]
        for key, ids in list(row["candidate"]["evidence_bindings"].items()):
            row["candidate"]["evidence_bindings"][key] = [item for item in ids if item != "NOOFF-OFFICIAL"]
        scored = MODULE.score_candidate(
            row["candidate"],
            MODULE.evidence_index(research([row], input_hash=cfg["input_hash"]), cfg),
            cfg,
        )
        self.assertFalse(scored["qualified"])
        self.assertIn("缺少与官网域名一致的官方证据", scored["reasons"])

    def test_stale_market_position_evidence_is_rejected(self):
        cfg = config()
        row = candidate("STALE", "Stale", "stale.example", "leader")
        row["evidence"][1]["published_at"] = "2024-01-01"
        scored = MODULE.score_candidate(
            row["candidate"],
            MODULE.evidence_index(research([row], input_hash=cfg["input_hash"]), cfg),
            cfg,
        )
        self.assertFalse(scored["qualified"])
        self.assertIn("市场地位缺少近 18 个月独立证据", scored["reasons"])

    def test_never_fills_with_candidate_outside_same_purchase_set(self):
        cfg = config([{"name": "Peer", "official_domain": "peer.example"}])
        rows = [
            candidate("PEER", "Peer", "peer.example", "peer"),
            candidate("LEADER", "Leader", "leader.example", "leader"),
        ]
        weak = candidate("WEAK", "Weak", "weak.example", "challenger")
        weak["candidate"]["direct_substitute"] = False
        weak["candidate"]["same_purchase_set"] = False
        rows.append(weak)
        with self.assertRaisesRegex(MODULE.ContractError, "不能用相邻产品"):
            MODULE.finalize(cfg, research(rows, input_hash=cfg["input_hash"]))

    def test_valid_user_candidate_wins_within_same_role(self):
        cfg = config([{"name": "User Peer", "official_domain": "user-peer.example"}])
        user_peer = candidate("USER", "User Peer", "user-peer.example", "peer", source="discovered")
        discovered_peer = candidate("DISC", "Discovered Peer", "discovered-peer.example", "peer")
        discovered_peer["candidate"]["dimensions"]["sub_track"] = 5
        rows = [
            discovered_peer,
            user_peer,
            candidate("LEADER", "Leader", "leader.example", "leader"),
            candidate("CHALLENGER", "Challenger", "challenger.example", "challenger"),
        ]
        result = MODULE.finalize(cfg, research(rows, input_hash=cfg["input_hash"]))
        self.assertEqual(result["formal_competitors"][0]["name"], "User Peer")
        self.assertEqual(result["formal_competitors"][0]["source"], "user_provided")

    def test_uses_second_peer_when_no_qualified_challenger(self):
        cfg = config([{"name": "Peer One", "official_domain": "peer-one.example"}])
        rows = [
            candidate("PEER1", "Peer One", "peer-one.example", "peer"),
            candidate("PEER2", "Peer Two", "peer-two.example", "peer"),
            candidate("LEADER", "Leader", "leader.example", "leader"),
        ]
        result = MODULE.finalize(cfg, research(rows, input_hash=cfg["input_hash"]))
        self.assertEqual(result["status"], "frozen")
        self.assertEqual(result["formal_competitors"][2]["portfolio_role"], "同层级直接竞品")

    def test_user_candidate_outside_purchase_set_is_rejected_and_replaced(self):
        cfg = config([{"name": "Sales Choice", "official_domain": "sales-choice.example"}])
        sales_choice = candidate("SALES", "Sales Choice", "sales-choice.example", "unknown", source="discovered")
        sales_choice["candidate"]["activity_status"] = "unknown"
        sales_choice["candidate"]["direct_substitute"] = False
        sales_choice["candidate"]["same_purchase_set"] = False
        sales_choice["candidate"]["dimensions"] = {}
        sales_choice["candidate"]["evidence_ids"] = []
        sales_choice["candidate"]["evidence_bindings"] = {}
        sales_choice["evidence"] = []
        rows = [
            sales_choice,
            candidate("PEER", "Peer", "peer.example", "peer"),
            candidate("LEADER", "Leader", "leader.example", "leader"),
            candidate("CHALLENGER", "Challenger", "challenger.example", "challenger"),
        ]
        result = MODULE.finalize(cfg, research(rows, input_hash=cfg["input_hash"]))
        self.assertNotIn("Sales Choice", [item["name"] for item in result["formal_competitors"]])
        self.assertEqual(result["selection_strategy"]["user_provided_retained"], False)
        rejection = result["provided_competitor_rejections"][0]
        self.assertEqual(rejection["name"], "Sales Choice")
        self.assertIn("未确认会进入同一次购买决策", rejection["reasons"])

    def test_missing_user_candidate_is_recorded_and_replaced(self):
        cfg = config([{"name": "Sales Choice", "official_domain": "sales-choice.example"}])
        rows = [
            candidate("PEER", "Peer", "peer.example", "peer"),
            candidate("LEADER", "Leader", "leader.example", "leader"),
            candidate("CHALLENGER", "Challenger", "challenger.example", "challenger"),
        ]
        result = MODULE.finalize(cfg, research(rows, input_hash=cfg["input_hash"]))
        self.assertEqual(result["status"], "frozen")
        self.assertEqual(result["selection_strategy"]["user_provided_retained"], False)
        self.assertEqual(result["provided_competitor_rejections"][0]["name"], "Sales Choice")
        self.assertIn("研究候选池未找到匹配项", result["provided_competitor_rejections"][0]["reasons"])

    def test_candidate_pool_under_three_never_returns_manual_status(self):
        cfg = config([{"name": "Peer", "official_domain": "peer.example"}])
        rows = [
            candidate("PEER", "Peer", "peer.example", "peer"),
            candidate("LEADER", "Leader", "leader.example", "leader"),
        ]
        with self.assertRaisesRegex(MODULE.ContractError, "不能用相邻产品"):
            MODULE.finalize(cfg, research(rows, input_hash=cfg["input_hash"]))


if __name__ == "__main__":
    unittest.main()
