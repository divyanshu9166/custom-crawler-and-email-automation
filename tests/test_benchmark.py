import argparse
import asyncio
import importlib.util
import json
from pathlib import Path

import pytest

from outreach.web import PublicWeb, extract_page

spec = importlib.util.spec_from_file_location("batch_benchmark", Path(__file__).resolve().parents[1] / "scripts" / "benchmark.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


async def test_batch_benchmark_preserves_partial_results_and_unknown_quality(tmp_path, monkeypatch):
    source = tmp_path / "input.csv"
    source.write_text("company,website,campaign,country_hint\nA fixture,https://bright-demo.com,A,UK\nDuplicate,https://www.bright-demo.com,A,UK\nB fixture,https://other-demo.com,B,US\nBlocked,https://linkedin.com/company/fixture,A,UK\n", encoding="utf-8")
    async def crawl(self, website):
        page = extract_page(website, "<p>Published hello@bright-demo.com contact details.</p>")
        page["rendered"] = True
        await self.on_page(page, self.report)
        if "other-demo" in website:
            raise TimeoutError("Controlled fixture failure")
        self.report["status"] = "complete"
        return [page]
    monkeypatch.setattr(PublicWeb, "crawl", crawl)
    run = await module.benchmark(argparse.Namespace(input=source, limit=50, pages=30, output=tmp_path / "results"))
    result = json.loads((run / "summary.json").read_text())
    assert len(result["companies"]) == 2 and len(result["input_errors"]) == 1
    assert result["companies"][1]["status"] == "partial"
    assert result["companies"][1]["pages"] == 1
    assert all(row["verified_emails"] is None and row["company_match"] is None for row in result["companies"])
    assert result["peak_full_stack_memory"] is None
    assert result["runtime_versions"]["playwright"]
    assert len(result["source_files_at_start"]["requirements.lock"]) == 64
    assert (run / "review.csv").is_file()


def test_benchmark_rejects_missing_company_inputs(tmp_path):
    path = tmp_path / "bad.csv"
    path.write_text("url\nhttps://example.com", encoding="utf-8")
    with pytest.raises(ValueError, match="CSV needs"):
        module.read_candidates(path, 50)


@pytest.mark.parametrize("override,expected", [(None, 900), (3600, 3600)])
async def test_benchmark_records_effective_deadline_without_reducing_render_scope(tmp_path, monkeypatch, override, expected):
    monkeypatch.setenv("JOB_TIMEOUT_SECONDS", "900")
    source = tmp_path / "input.csv"
    source.write_text("company,website,campaign,country_hint\nFixture,https://bright-demo.com,A,UK\n", encoding="utf-8")
    async def crawl(self, website):
        assert self.settings.job_timeout_seconds == expected
        assert self.settings.crawl_max_pages == 30 and self.settings.crawl_max_depth == 3
        assert self.settings.crawl_render_mode == "always" and self.settings.browser_enabled
        assert not self.settings.sending_enabled and not self.settings.worker_enabled
        self.report["status"] = "complete"
        return [extract_page(website, "<p>Fictional official-source fixture.</p>")]
    monkeypatch.setattr(PublicWeb, "crawl", crawl)
    run = await module.benchmark(argparse.Namespace(input=source, limit=1, pages=30, concurrency=1,
                                timeout=override, output=tmp_path / "results"))
    summary = json.loads((run / "summary.json").read_text(encoding="utf-8"))
    assert summary["scope"]["job_timeout_seconds"] == expected
    assert summary["scope"]["max_pages"] == 30 and summary["scope"]["render_mode"] == "always"
    assert summary["companies"][0]["verified_emails"] is None


async def test_parallel_benchmark_preserves_each_company_evidence_and_scope(tmp_path, monkeypatch):
    source = tmp_path / "input.csv"
    source.write_text("company,website,campaign,country_hint\nAlpha,https://alpha-demo.com,A,US\nBeta,https://beta-demo.com,B,UK\n", encoding="utf-8")
    arrived, active, peak = 0, 0, 0
    gate = asyncio.Event()
    async def crawl(self, website):
        nonlocal arrived, active, peak
        arrived += 1
        active += 1
        peak = max(peak, active)
        if arrived == 2:
            gate.set()
        await asyncio.wait_for(gate.wait(), 2)
        page = extract_page(website, f"<p>Official fixture website: {website}</p>")
        await self.on_page(page, self.report)
        self.report["status"] = "complete"
        active -= 1
        return [page]
    monkeypatch.setattr(PublicWeb, "crawl", crawl)
    run = await module.benchmark(argparse.Namespace(input=source, limit=50, pages=30, concurrency=2, output=tmp_path / "runs"))
    result = json.loads((run / "summary.json").read_text())
    assert peak == 2 and result["run_status"] == "finished"
    assert result["scope"]["max_pages"] == 30 and result["scope"]["company_concurrency"] == 2
    for row in result["companies"]:
        detail = json.loads((run / row["detail_file"]).read_text())
        assert len(detail["pages"]) == 1 and detail["pages"][0]["url"] == row["website"]
