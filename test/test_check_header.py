from pathlib import Path

GOOD = bytes.fromhex("1b4c7561530019930d0a1a0a0404040404") + b"rest of the chunk"


def write(tmp_path: Path, name: str, data: bytes) -> str:
    path = tmp_path / name
    path.write_bytes(data)
    return str(path)


def test_expected_header_matches_the_radio_layout(check_header):
    # signature, Lua 5.3, format 0, LUAC_DATA, then int / size_t-as-int /
    # Instruction / lua_Integer / lua_Number all 4 bytes
    assert check_header.EXPECTED == b"\x1bLuaS\x00\x19\x93\r\n\x1a\n\x04\x04\x04\x04\x04"


def test_good_header(check_header, tmp_path, capsys):
    assert check_header.main([write(tmp_path, "ok.luac", GOOD)]) == 0
    assert capsys.readouterr().out == ""


def test_64_bit_host_header_is_rejected(check_header, tmp_path, capsys):
    # what stock luac on a 64-bit host writes: 8-byte size_t, Integer and Number
    stock = bytes.fromhex("1b4c7561530019930d0a1a0a0408040808")
    path = write(tmp_path, "stock.luac", stock)
    assert check_header.main([path]) == 1
    assert f"::error file={path}::Unexpected bytecode header: {stock.hex()}" in (
        capsys.readouterr().out
    )


def test_source_file_is_rejected(check_header, tmp_path):
    assert check_header.main([write(tmp_path, "main.lua", b"local x = 1\nreturn x\n")]) == 1


def test_truncated_file_is_rejected(check_header, tmp_path):
    assert check_header.main([write(tmp_path, "short.luac", GOOD[:5])]) == 1


def test_missing_file_is_reported(check_header, tmp_path, capsys):
    missing = str(tmp_path / "missing.luac")
    assert check_header.main([missing]) == 1
    assert capsys.readouterr().out.startswith(f"::error file={missing}::")


def test_one_bad_file_fails_the_whole_run(check_header, tmp_path, capsys):
    good = write(tmp_path, "a.luac", GOOD)
    bad = write(tmp_path, "b.luac", b"nope")
    assert check_header.main([good, bad, good]) == 1
    assert capsys.readouterr().out.count("::error") == 1
