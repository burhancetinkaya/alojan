"""Opt-in real model / isolated PostgreSQL checks using synthetic corrections only."""

import asyncio
import json
import os
import time
from pathlib import Path

import pytest
from agents import Runner

from alojan.migrate import migrate
from alojan_agent.backend import Backend
from alojan_agent.models import Note, Summary
from alojan_agent.service import AgentService
from alojan_agent.store import Store, call_uuid
from test_database import database  # noqa: F401

pytestmark = pytest.mark.skipif(
    os.environ.get("ALOJAN_REAL_SUMMARY") != "1", reason="explicit real API opt-in required"
)


@pytest.fixture(autouse=True)
def provider_diagnostics(monkeypatch):
    # Space separate tests without spending the production worker's deadline.
    time.sleep(6)
    original = Runner.run

    async def run(*args, **kwargs):
        try:
            return await original(*args, **kwargs)
        except Exception as exc:
            # Status/type only: provider response bodies can contain prompts or secrets.
            print(
                json.dumps(
                    {
                        "exception": type(exc).__name__,
                        "http_status": getattr(exc, "status_code", None),
                    }
                )
            )
            raise

    monkeypatch.setattr(Runner, "run", run)


CASES = [
    (
        "saved-repair",
        ["Pazartesi, düzeltiyorum perşembe raporu göndereceğim."],
        "Perşembe raporu göndereceğim.",
        "",
        ["perşembe", "rapor"],
        ["pazartesi"],
    ),
    (
        "two-independent",
        ["Salı rapor, cuma sözleşme gelecek.", "Rapor çarşamba olacak, sözleşme aynı."],
        "Çarşamba rapor, cuma sözleşme gelecek.",
        "",
        ["çarşamba", "rapor", "cuma", "sözleşme"],
        ["salı", "hazırl"],
    ),
    (
        "unsaved-repair",
        ["Pazartesi geleceğim."],
        "Pazartesi geleceğim.",
        "Pazartesi değil perşembe geleceğim. Bu düzeltmeyi söyleyip kapatıyorum.",
        ["perşembe"],
        ["pazartesi"],
    ),
    (
        "uncertain-repair",
        ["Salı rapor, cuma sözleşme gelecek."],
        "Salı rapor, cuma sözleşme gelecek.",
        "Birini haftaya alacağım ama hangisi olacağı henüz belli değil.",
        ["rapor", "sözleşme"],
        ["hazırl"],
    ),
    (
        "unsaved-withdrawal",
        ["Burhan Bey beni arasın ve sözleşmeyi göndersin."],
        "Geri arama ve sözleşme kopyası istiyor.",
        "Aramasına gerek kalmadı, yalnız sözleşmeyi istiyorum.",
        ["sözleşme"],
        [],
    ),
    (
        "product-repair",
        ["Mira uygulaması açılmıyor.", "Uygulama Mira değil Vega, karıştırmışım."],
        "Vega uygulaması açılmıyor.",
        "",
        ["vega"],
        ["mira"],
    ),
    (
        "uncertain-document",
        ["Bütçe raporu ile teklif belgesini göndereceğim."],
        "Bütçe raporu ile teklif belgesini gönderecek.",
        "Birini yarına bırakacağım, hangisini henüz seçmedim.",
        ["bütçe", "teklif"],
        [],
    ),
    (
        "actual-person",
        ["İşe alacağım iki aday Deniz ve Ece."],
        "Deniz ve Ece işe alınacak adaylar.",
        "Birini haftaya işe alacağım, hangisi olacağını henüz seçmedim.",
        ["deniz", "ece", "işe"],
        [],
    ),
    (
        "independent-product-correction",
        ["Atlas için 2 lisans; Nova için 4 lisans istiyorum."],
        "Atlas için 2 lisans, Nova için 4 lisans istiyor.",
        "Atlas adedini 3 yapın, Nova değişmesin.",
        ["atlas", "3", "nova", "4"],
        ["2 lisans", "iki lisans"],
    ),
]


def assert_final_meaning(summary, case):
    name, _, _, later, required, forbidden = case
    text = " ".join((summary.subject, summary.summary, summary.requested_action)).casefold()
    assert all(term in text for term in required)
    assert not any(term in text for term in forbidden)
    assert summary.promised_action == "none"
    assert summary.confirmation_status != "confirmed"
    if name.startswith("uncertain-") or name == "actual-person":
        assert summary.unresolved_questions
        assert later.casefold() in " ".join(summary.unresolved_questions).casefold()
    if name.startswith("uncertain-"):
        assert not any(
            term in summary.model_dump_json().casefold()
            for term in ("çalışan", "işe al", "personel", "kişi", "alım")
        )
    if name in (
        "saved-repair",
        "two-independent",
        "unsaved-repair",
        "uncertain-repair",
        "uncertain-document",
        "actual-person",
    ):
        assert summary.requested_action == ""
    if name == "unsaved-withdrawal":
        action = summary.requested_action.casefold()
        assert "sözleşme" in action
        assert not any(term in action for term in ("arama", "arasın", "aray", "çağrı", "telefon"))


@pytest.mark.parametrize("repeat", range(3))
@pytest.mark.parametrize("case", CASES, ids=[c[0] for c in CASES])
def test_final_meaning_through_real_summary_and_database(database, case, repeat):  # noqa: F811
    output = Path(os.environ["ALOJAN_SUMMARY_EVIDENCE_DIR"])
    output.mkdir(parents=True, exist_ok=True, mode=0o700)

    async def run():
        name, utterances, saved, later, _, _ = case
        migrate(database)
        store = Store(database)
        cid = f"synthetic-summary-{name}-{repeat}"
        await store.start(cid, None)
        for index, utterance in enumerate(utterances):
            await store.utterance(cid, f"u-{index}", "caller", utterance)
        await store.note(cid, Note(subject="Talep", message=saved), 1)
        if later:
            await store.utterance(cid, "u-later", "caller", later)
        await store.end(cid, "disconnected")
        data = await store.summary_input(call_uuid(cid))
        assert json.loads(data["last_note"][0])["message"] == saved
        backend = Backend()
        worker = asyncio.create_task(AgentService(backend, store).summaries())
        try:
            async with asyncio.timeout(25):
                while await store.pending():
                    await asyncio.sleep(0.05)
            row = await store.run(
                lambda conn: conn.execute("SELECT detail_jsonb FROM call_summaries").fetchone()
            )
            assert row, "summary worker failed to persist a result"
            summary = Summary.model_validate(row[0])
        finally:
            worker.cancel()
            await asyncio.gather(worker, return_exceptions=True)
            await backend.close()
        (output / f"{name}-{repeat}.json").write_text(summary.model_dump_json(indent=2))
        assert_final_meaning(summary, case)

    asyncio.run(run())
