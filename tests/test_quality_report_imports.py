from pathlib import Path


def test_quality_report_injects_repo_root_on_sys_path():
    content = Path("scripts/quality_report.py").read_text(encoding="utf-8")
    insert_index = content.find("sys.path.insert(0, str(ROOT))")
    import_index = content.find("from victus.core.failures import FailureLogger")

    assert insert_index != -1
    assert import_index != -1
    assert insert_index < import_index
