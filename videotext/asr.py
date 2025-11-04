"""
ASR (Automatic Speech Recognition) module using faster-whisper.
"""
from typing import List, Dict, Any, Optional


def transcribe_audio(
    audio_path: str,
    mode: str = "balance",
    language: Optional[str] = None,
    denoise: bool = False
) -> List[Dict[str, Any]]:
    """
    Transcribe audio file using faster-whisper.
    
    Args:
        audio_path: Path to audio file
        mode: Processing mode ('fast', 'balance', 'accurate')
        language: Language code (None for auto-detect)
        denoise: Whether to apply audio denoising
        
    Returns:
        List of segments with 'start', 'end', 'text'
    """
    # TODO: Implement actual transcription
    # This is a stub that returns sample data
    
    try:
        from faster_whisper import WhisperModel
        
        # Model selection based on mode
        model_map = {
            'fast': 'tiny',
            'balance': 'medium',
            'accurate': 'large-v3'
        }
        model_size = model_map.get(mode, 'medium')
        
        # Initialize model (use GPU if available)
        model = WhisperModel(model_size, device="cuda", compute_type="float16")
        
        # Transcribe
        segments_generator, info = model.transcribe(
            audio_path,
            language=language,
            beam_size=5,
            vad_filter=True
        )
        
        segments = []
        for segment in segments_generator:
            segments.append({
                'start': segment.start,
                'end': segment.end,
                'text': segment.text.strip()
            })
        
        return segments
        
    except ImportError:
        # Return stub data if faster-whisper not available
        return [
            {
                'start': 0.0,
                'end': 5.0,
                'text': '[STUB] Транскрипция недоступна. Установите faster-whisper и ctranslate2.'
            }
        ]
    except Exception as e:
        raise RuntimeError(f"ASR transcription failed: {e}") from e


def get_model_info(mode: str) -> Dict[str, Any]:
    """Get model information for a given mode."""
    model_info = {
        'fast': {
            'model': 'tiny',
            'compute_type': 'int8',
            'speed_estimate': '≥ 0.25× RT'
        },
        'balance': {
            'model': 'medium',
            'compute_type': 'float16',
            'speed_estimate': '≥ 0.5× RT'
        },
        'accurate': {
            'model': 'large-v3',
            'compute_type': 'float16',
            'speed_estimate': '≈ 1× RT'
        }
    }
    return model_info.get(mode, model_info['balance'])
