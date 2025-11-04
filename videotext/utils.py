"""
Utility functions for video/audio processing.
"""
import subprocess
from typing import List, Dict, Any
from pathlib import Path


def extract_frames(
    video_path: str,
    interval: int = 5
) -> List[Dict[str, Any]]:
    """
    Extract frames from video at specified intervals.
    
    Args:
        video_path: Path to video file
        interval: Seconds between frames
        
    Returns:
        List of dicts with 'timestamp' and 'frame' (numpy array)
    """
    try:
        import cv2
        
        cap = cv2.VideoCapture(video_path)
        fps = cap.get(cv2.CAP_PROP_FPS)
        frame_interval = int(fps * interval)
        
        frames = []
        frame_count = 0
        
        while cap.isOpened():
            ret, frame = cap.read()
            if not ret:
                break
            
            if frame_count % frame_interval == 0:
                timestamp = frame_count / fps
                frames.append({
                    'timestamp': timestamp,
                    'frame': frame
                })
            
            frame_count += 1
        
        cap.release()
        return frames
        
    except ImportError:
        return []


def get_video_duration(video_path: str) -> float:
    """Get video duration in seconds using ffprobe."""
    try:
        cmd = [
            'ffprobe',
            '-v', 'error',
            '-show_entries', 'format=duration',
            '-of', 'default=noprint_wrappers=1:nokey=1',
            video_path
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        return float(result.stdout.strip())
    except (subprocess.CalledProcessError, FileNotFoundError, ValueError):
        return 0.0


def get_audio_duration(audio_path: str) -> float:
    """Get audio duration in seconds using ffprobe."""
    return get_video_duration(audio_path)


def is_video_file(filename: str) -> bool:
    """Check if file is a video file."""
    video_extensions = {'.mp4', '.mov', '.mkv', '.webm', '.avi', '.m4v'}
    return Path(filename).suffix.lower() in video_extensions


def is_audio_file(filename: str) -> bool:
    """Check if file is an audio file."""
    audio_extensions = {'.mp3', '.wav', '.m4a', '.ogg', '.flac', '.aac'}
    return Path(filename).suffix.lower() in audio_extensions
