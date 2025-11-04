"""
Tests for VTT writer.
"""
import pytest
from pathlib import Path
from app.vtt import write_vtt, write_srt, format_timestamp, format_srt_timestamp


def test_format_timestamp():
    """Test timestamp formatting."""
    assert format_timestamp(0.0) == "00:00:00.000"
    assert format_timestamp(125.5) == "00:02:05.500"
    assert format_timestamp(3661.123) == "01:01:01.123"


def test_format_srt_timestamp():
    """Test SRT timestamp formatting."""
    assert format_srt_timestamp(0.0) == "00:00:00,000"
    assert format_srt_timestamp(125.5) == "00:02:05,500"
    assert format_srt_timestamp(3661.123) == "01:01:01,123"


def test_write_vtt(tmp_path):
    """Test VTT file writing."""
    segments = [
        {'start': 0.0, 'end': 5.0, 'text': 'Первая фраза'},
        {'start': 5.0, 'end': 10.0, 'text': 'Вторая фраза', 'speaker': 'Speaker1'}
    ]
    
    vtt_path = tmp_path / "test.vtt"
    write_vtt(segments, str(vtt_path), language="ru")
    
    assert vtt_path.exists()
    content = vtt_path.read_text(encoding='utf-8')
    assert 'WEBVTT' in content
    assert 'Language: ru' in content
    assert 'Первая фраза' in content
    assert 'Speaker1' in content


def test_write_srt(tmp_path):
    """Test SRT file writing."""
    segments = [
        {'start': 0.0, 'end': 5.0, 'text': 'Первая фраза'},
        {'start': 5.0, 'end': 10.0, 'text': 'Вторая фраза'}
    ]
    
    srt_path = tmp_path / "test.srt"
    write_srt(segments, str(srt_path))
    
    assert srt_path.exists()
    content = srt_path.read_text(encoding='utf-8')
    assert '1\n' in content
    assert '00:00:00,000 --> 00:00:05,000' in content
    assert 'Первая фраза' in content
