import os
import threading

from quantaalpha.utils.file_cache import FileStatCache


def _counting_builder(calls):
    def build(path):
        calls.append(path)
        with open(path, encoding="utf-8") as handle:
            return handle.read()
    return build


def test_reuses_the_value_until_the_file_changes(tmp_path):
    path = tmp_path / "library.json"
    path.write_text("one", encoding="utf-8")
    cache, calls = FileStatCache(), []
    build = _counting_builder(calls)

    assert cache.get(path, build) == "one"
    assert cache.get(str(path), build) == "one"
    assert len(calls) == 1

    path.write_text("three", encoding="utf-8")  # size changes
    assert cache.get(path, build) == "three"
    assert len(calls) == 2


def test_a_rewrite_of_the_same_size_is_seen_through_its_mtime(tmp_path):
    path = tmp_path / "library.json"
    path.write_text("aaa", encoding="utf-8")
    cache, calls = FileStatCache(), []
    build = _counting_builder(calls)
    cache.get(path, build)

    path.write_text("bbb", encoding="utf-8")
    stat = path.stat()
    os.utime(path, ns=(stat.st_atime_ns, stat.st_mtime_ns + 1_000_000))
    assert cache.get(path, build) == "bbb"
    assert len(calls) == 2


def test_extra_key_separates_entries_for_the_same_file(tmp_path):
    path = tmp_path / "library.json"
    path.write_text("x", encoding="utf-8")
    cache = FileStatCache()

    assert cache.get(path, lambda p: "daily", extra=("daily",)) == "daily"
    assert cache.get(path, lambda p: "monthly", extra=("monthly",)) == "monthly"
    assert cache.get(path, lambda p: "rebuilt", extra=("monthly",)) == "monthly"


def test_a_failed_build_is_not_cached(tmp_path):
    path = tmp_path / "library.json"
    path.write_text("x", encoding="utf-8")
    cache = FileStatCache()

    def broken(_):
        raise ValueError("torn write")

    try:
        cache.get(path, broken)
    except ValueError:
        pass
    assert cache.get(path, lambda p: "ok") == "ok"


def test_retain_drops_files_no_longer_listed(tmp_path):
    kept, gone = tmp_path / "kept.json", tmp_path / "gone.json"
    kept.write_text("k", encoding="utf-8")
    gone.write_text("g", encoding="utf-8")
    cache, calls = FileStatCache(), []
    build = _counting_builder(calls)
    cache.get(kept, build)
    cache.get(gone, build)

    cache.retain([kept])
    cache.get(kept, build)
    cache.get(gone, build)
    assert calls.count(str(gone.resolve())) == 2
    assert calls.count(str(kept.resolve())) == 1


def test_concurrent_misses_build_once(tmp_path):
    path = tmp_path / "library.json"
    path.write_text("x", encoding="utf-8")
    cache, calls = FileStatCache(), []
    release = threading.Event()

    def slow(p):
        calls.append(p)
        release.wait(timeout=5)
        return "value"

    threads = [threading.Thread(target=cache.get, args=(path, slow)) for _ in range(5)]
    for thread in threads:
        thread.start()
    release.set()
    for thread in threads:
        thread.join(timeout=5)
    assert len(calls) == 1
