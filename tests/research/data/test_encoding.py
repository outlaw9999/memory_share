import pytest
from pathlib import Path
from kit.core.file_system import read_text_safe, EncodingStatus, EncodingError, FileContent

def test_read_utf8(tmp_path):
    p = tmp_path / "test.py"
    content = "print('hello world')"
    p.write_text(content, encoding="utf-8")
    
    result = read_text_safe(p)
    assert result.text == content
    assert result.encoding == "utf-8"
    assert result.status == EncodingStatus.OK

def test_read_utf8_sig(tmp_path):
    p = tmp_path / "test_bom.py"
    content = "print('hello bom')"
    p.write_text(content, encoding="utf-8-sig")
    
    result = read_text_safe(p)
    assert result.text == content
    assert result.encoding == "utf-8-sig"
    assert result.status == EncodingStatus.BOM_DETECTED

def test_read_utf16(tmp_path):
    p = tmp_path / "test_utf16.py"
    content = "print('hello utf16')"
    p.write_text(content, encoding="utf-16")
    
    result = read_text_safe(p)
    assert result.text == content
    assert result.encoding == "utf-16"
    assert result.status == EncodingStatus.FALLBACK_USED

def test_read_binary_fail(tmp_path):
    p = tmp_path / "binary.bin"
    # Create a file with a NULL byte
    p.write_bytes(b"hello\x00world")
    
    with pytest.raises(EncodingError) as excinfo:
        read_text_safe(p)
    assert excinfo.value.status == EncodingStatus.BINARY_FILE
    assert "NULL-byte" in str(excinfo.value)

def test_read_invalid_encoding(tmp_path):
    p = tmp_path / "invalid.py"
    # Write some bytes that are not valid UTF-8/16
    # 0xFF is often invalid in many contexts
    p.write_bytes(b"\xff\xfe\xfd\xfc")
    
    # Actually \xff\xfe might be seen as UTF-16 BOM LE
    # Let's try something more "random"
    p.write_bytes(b"\x80\x81\x82\x83") # Invalid UTF-8 start bytes
    
    with pytest.raises(EncodingError) as excinfo:
        read_text_safe(p)
    assert excinfo.value.status == EncodingStatus.INVALID_ENCODING

def test_file_not_found():
    with pytest.raises(FileNotFoundError):
        read_text_safe(Path("non_existent_file.py"))
