"""
VTT (WebVTT) format writer utility.
"""
from typing import List, Dict, Any, Optional
from pathlib import Path


def write_vtt(segments: List[Dict[str, Any]], path: str, language: Optional[str] = None) -> None:
    """
    Write segments to WebVTT format.
    
    Args:
        segments: List of segment dicts with 'start', 'end', 'text', and optionally 'speaker'
        path: Output file path
        language: Optional language code for VTT header
    """
    vtt_path = Path(path)
    vtt_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(vtt_path, 'w', encoding='utf-8') as f:
        f.write('WEBVTT\n')
        if language:
            f.write(f'Language: {language}\n')
        f.write('\n')
        
        for i, segment in enumerate(segments, start=1):
            start = format_timestamp(segment['start'])
            end = format_timestamp(segment['end'])
            text = segment['text'].strip()
            
            # Add speaker label if available
            if 'speaker' in segment and segment['speaker']:
                text = f"<v {segment['speaker']}>{text}</v>"
            
            f.write(f'{i}\n')
            f.write(f'{start} --> {end}\n')
            f.write(f'{text}\n')
            f.write('\n')


def format_timestamp(seconds: float) -> str:
    """
    Format seconds to VTT timestamp format (HH:MM:SS.mmm).
    
    Args:
        seconds: Time in seconds
        
    Returns:
        Formatted timestamp string
    """
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    millis = int((seconds % 1) * 1000)
    
    return f'{hours:02d}:{minutes:02d}:{secs:02d}.{millis:03d}'


def write_srt(segments: List[Dict[str, Any]], path: str) -> None:
    """
    Write segments to SRT format.
    
    Args:
        segments: List of segment dicts with 'start', 'end', 'text'
        path: Output file path
    """
    srt_path = Path(path)
    srt_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(srt_path, 'w', encoding='utf-8') as f:
        for i, segment in enumerate(segments, start=1):
            start = format_srt_timestamp(segment['start'])
            end = format_srt_timestamp(segment['end'])
            text = segment['text'].strip()
            
            # Remove speaker tags for SRT
            if '<v ' in text and '</v>' in text:
                text = text.split('>', 1)[1].rsplit('<', 1)[0]
            
            f.write(f'{i}\n')
            f.write(f'{start} --> {end}\n')
            f.write(f'{text}\n')
            f.write('\n')


def format_srt_timestamp(seconds: float) -> str:
    """
    Format seconds to SRT timestamp format (HH:MM:SS,mmm).
    
    Args:
        seconds: Time in seconds
        
    Returns:
        Formatted timestamp string
    """
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    millis = int((seconds % 1) * 1000)
    
    return f'{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}'
