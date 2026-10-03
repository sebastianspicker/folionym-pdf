"""Discovery pruning retains source visibility, ordering, and containment rules."""

from pathlib import Path

import pytest

from folionym.application import discovery


def test_depth_limit_prunes_scans_without_changing_pdf_filters(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    for name in ("root.PDF", ".hidden.pdf", "skip.pdf", "20260101-invoice.pdf", "note.txt"):
        (tmp_path / name).touch()
    child = tmp_path / "child"
    deep = child / "deep"
    deep.mkdir(parents=True)
    (child / "child.pdf").touch()
    (deep / "deep.pdf").touch()
    (tmp_path / "linked.pdf").symlink_to(tmp_path / "root.PDF")
    scanned: list[Path] = []
    original = discovery.os.scandir

    def scan(path: Path):
        scanned.append(path)
        return original(path)

    monkeypatch.setattr(discovery.os, "scandir", scan)
    result = discovery.collect_pdf_files(
        tmp_path,
        discovery.PdfCollectionOptions(
            recursive=True, max_depth=1, exclude_patterns=["skip*"], skip_if_already_named=True
        ),
    )
    assert [path.name for path in result] == ["root.PDF", "child.pdf"]
    assert scanned == [tmp_path, child]


def test_override_order_and_containment_remain_exact(tmp_path: Path) -> None:
    directory = tmp_path / "inside"
    directory.mkdir()
    first, second, outside = directory / "one.pdf", directory / "two.pdf", tmp_path / "outside.pdf"
    for path in (first, second, outside):
        path.touch()
    assert discovery.collect_pdf_files(
        directory, discovery.PdfCollectionOptions(files_override=[second, first, outside])
    ) == [second, first]


def test_directory_pdf_count_matches_depth_one_discovery_and_ignores_symlinks(tmp_path: Path) -> None:
    (tmp_path / "a.pdf").write_bytes(b"%PDF")
    (tmp_path / "B.PDF").write_bytes(b"%PDF")
    (tmp_path / ".hidden.pdf").write_bytes(b"%PDF")
    (tmp_path / "notes.txt").write_text("x")
    (tmp_path / "sub").mkdir()
    (tmp_path / "sub" / "nested.pdf").write_bytes(b"%PDF")
    outside = tmp_path.parent / f"{tmp_path.name}-outside.pdf"
    outside.write_bytes(b"%PDF")
    try:
        (tmp_path / "link.pdf").symlink_to(outside)
    except OSError:
        pytest.skip("symlinks unavailable")
    assert discovery.count_directory_pdfs(tmp_path) == 2
    assert discovery.count_directory_pdfs(tmp_path) == len(discovery.collect_pdf_files(tmp_path))
    assert discovery.count_directory_pdfs(tmp_path / "missing") == 0


def test_child_directories_are_visible_sorted_and_not_symlinks(tmp_path: Path) -> None:
    for name in ("beta", "Alpha", ".hidden"):
        (tmp_path / name).mkdir()
    (tmp_path / "file.txt").write_text("x")
    try:
        (tmp_path / "linked").symlink_to(tmp_path / "beta", target_is_directory=True)
    except OSError:
        pytest.skip("symlinks unavailable")
    assert [path.name for path in discovery.list_child_directories(tmp_path)] == ["Alpha", "beta"]


def test_local_filesystem_roots_are_unique_resolved_directories() -> None:
    roots = discovery.local_filesystem_roots()
    assert roots and len(set(roots)) == len(roots) and all(root.is_dir() and root == root.resolve() for root in roots)
