import csv

from ksa_pipeline import paths, validation
from ksa_pipeline.schema import columns


def _write_run(folder, run_id, n, segment="A_aesthetic_clinics"):
    folder.mkdir(parents=True, exist_ok=True)
    with (folder / f"{run_id}.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=columns("ingest"), lineterminator="\n")
        w.writeheader()
        for i in range(n):
            row = {c: "" for c in columns("ingest")}
            row.update(record_id=f"google_maps:{run_id}:{i}", run_id=run_id, segment=segment,
                       phone_e164="+966550000001", phone_type="mobile" if i % 2 else "landline",
                       name_location_count="1", is_closed="False", has_whatsapp_link="False")
            w.writerow(row)


def test_runs_glob_and_stratified_sample(tmp_path, monkeypatch):
    monkeypatch.setattr(paths, "INTERIM", tmp_path / "interim")
    monkeypatch.setattr(paths, "SAMPLES", tmp_path / "samples")
    _write_run(tmp_path / "interim" / "google_maps", "2026-09-16__keyword_probe", 50)
    _write_run(tmp_path / "interim" / "google_maps", "2026-09-17__full_A__riyadh", 40)
    _write_run(tmp_path / "interim" / "google_maps", "2026-09-17__full_A__jeddah", 40)

    assert len(validation.load_interim("google_maps", "A_aesthetic_clinics", "2026-09-17__full_*")) == 80

    out = validation.make_sample("google_maps", "A_aesthetic_clinics", "2026-09-17__full_*")
    rows = list(csv.DictReader(out.open(encoding="utf-8")))
    assert len(rows) == 20
    assert sorted({r["run_id"] for r in rows}) == ["2026-09-17__full_A__jeddah", "2026-09-17__full_A__riyadh"]
    assert sum(r["run_id"].endswith("riyadh") for r in rows) == 10
    assert all("•" in r["phone_masked"] for r in rows)                 # phones masked in the committed sample

    overall, per_run = validation.metrics("google_maps", "A_aesthetic_clinics", "2026-09-17__full_*")
    assert overall["n_records"] == 80 and overall["labeled"] == 0
    assert set(per_run) == {"2026-09-17__full_A__jeddah", "2026-09-17__full_A__riyadh"}
    assert validation.verdict(overall).startswith("incomplete")
