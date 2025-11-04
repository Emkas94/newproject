"""
Tests for keyword filtering.
"""
import pytest
from videotext.pipeline import Pipeline


def test_filter_keywords():
    """Test keyword filtering in pipeline."""
    pipeline = Pipeline()
    
    segments = [
        {'start': 0.0, 'end': 5.0, 'text': 'Это важное сообщение'},
        {'start': 5.0, 'end': 10.0, 'text': 'Обычный текст'},
        {'start': 10.0, 'end': 15.0, 'text': 'Критично для понимания'},
        {'start': 15.0, 'end': 20.0, 'text': 'Еще один обычный текст'}
    ]
    
    keywords = "важно,критично"
    filtered = pipeline._filter_keywords(segments, keywords)
    
    assert len(filtered) == 2
    assert filtered[0]['text'] == 'Это важное сообщение'
    assert filtered[1]['text'] == 'Критично для понимания'


def test_filter_keywords_case_insensitive():
    """Test that keyword filtering is case-insensitive."""
    pipeline = Pipeline()
    
    segments = [
        {'start': 0.0, 'end': 5.0, 'text': 'ВАЖНОЕ сообщение'},
        {'start': 5.0, 'end': 10.0, 'text': 'Обычный текст'}
    ]
    
    keywords = "важно"
    filtered = pipeline._filter_keywords(segments, keywords)
    
    assert len(filtered) == 1
    assert filtered[0]['text'] == 'ВАЖНОЕ сообщение'


def test_filter_keywords_empty():
    """Test filtering with empty keywords."""
    pipeline = Pipeline()
    
    segments = [
        {'start': 0.0, 'end': 5.0, 'text': 'Тест'}
    ]
    
    filtered = pipeline._filter_keywords(segments, "")
    assert len(filtered) == 0
