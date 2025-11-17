"""
Pipeline for video/audio transcription processing.
"""
import os
import json
import zipfile
from typing import List, Dict, Any, Optional, Callable, Tuple
from pathlib import Path
from datetime import datetime

from app.vtt import write_vtt, write_srt


class PipelineCallback:
    """Callback interface for pipeline progress updates."""
    
    def on_start(self, job_id: str, config: Dict[str, Any]) -> None:
        """Called when pipeline starts."""
        pass
    
    def on_audio_extracted(self, job_id: str, audio_path: str, duration: float) -> None:
        """Called when audio is extracted from video."""
        pass
    
    def on_asr_started(self, job_id: str) -> None:
        """Called when ASR processing starts."""
        pass
    
    def on_asr_completed(self, job_id: str, segments: List[Dict[str, Any]]) -> None:
        """Called when ASR processing completes."""
        pass
    
    def on_diarization_completed(self, job_id: str, segments: List[Dict[str, Any]]) -> None:
        """Called when speaker diarization completes."""
        pass
    
    def on_ocr_started(self, job_id: str) -> None:
        """Called when OCR processing starts."""
        pass
    
    def on_ocr_completed(self, job_id: str, segments: List[Dict[str, Any]]) -> None:
        """Called when OCR processing completes."""
        pass
    
    def on_translation_completed(self, job_id: str, segments: List[Dict[str, Any]]) -> None:
        """Called when translation completes."""
        pass
    
    def on_export_started(self, job_id: str) -> None:
        """Called when export starts."""
        pass
    
    def on_done(self, job_id: str, artifacts: List[str]) -> None:
        """Called when pipeline completes."""
        pass
    
    def on_error(self, job_id: str, error: Exception) -> None:
        """Called when pipeline encounters an error."""
        pass


class Pipeline:
    """Main transcription pipeline."""
    
    def __init__(
        self,
        callback: Optional[PipelineCallback] = None,
        output_dir: str = "artifacts"
    ):
        self.callback = callback
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
    
    def run(
        self,
        job_id: str,
        source_path: str,
        mode: str = "balance",
        language: Optional[str] = None,
        diarization: bool = False,
        ocr_enabled: bool = False,
        ocr_interval: int = 5,
        denoise: bool = False,
        translate_to: Optional[str] = None,
        keywords: Optional[str] = None
    ) -> List[str]:
        """
        Run the full transcription pipeline.
        
        Returns:
            List of artifact file paths
        """
        config = {
            'mode': mode,
            'language': language,
            'diarization': diarization,
            'ocr_enabled': ocr_enabled,
            'ocr_interval': ocr_interval,
            'denoise': denoise,
            'translate_to': translate_to,
            'keywords': keywords
        }
        
        try:
            self.callback.on_start(job_id, config)
            
            # Step 1: Extract audio if needed
            audio_path, duration = self._extract_audio(source_path, job_id)
            self.callback.on_audio_extracted(job_id, audio_path, duration)
            
            # Step 2: ASR transcription
            self.callback.on_asr_started(job_id)
            asr_segments = self._run_asr(audio_path, mode, language, denoise)
            self.callback.on_asr_completed(job_id, asr_segments)
            
            # Step 3: Speaker diarization (optional)
            if diarization:
                asr_segments = self._run_diarization(audio_path, asr_segments)
                self.callback.on_diarization_completed(job_id, asr_segments)
            
            # Step 4: OCR (optional)
            ocr_segments = []
            if ocr_enabled:
                self.callback.on_ocr_started(job_id)
                ocr_segments = self._run_ocr(source_path, ocr_interval)
                self.callback.on_ocr_completed(job_id, ocr_segments)
            
            # Step 5: Merge ASR + OCR
            merged_segments = self._merge_segments(asr_segments, ocr_segments)
            
            # Step 6: Translation (optional)
            if translate_to:
                merged_segments = self._translate_segments(merged_segments, translate_to)
                self.callback.on_translation_completed(job_id, merged_segments)
            
            # Step 7: Filter by keywords (optional)
            filtered_segments = merged_segments
            if keywords:
                filtered_segments = self._filter_keywords(merged_segments, keywords)
            
            # Step 8: Export artifacts
            self.callback.on_export_started(job_id)
            artifacts = self._export_artifacts(
                job_id,
                asr_segments,
                ocr_segments,
                merged_segments,
                filtered_segments,
                keywords
            )
            
            self.callback.on_done(job_id, artifacts)
            return artifacts
            
        except Exception as e:
            self.callback.on_error(job_id, e)
            raise
    
    def _extract_audio(self, source_path: str, job_id: str) -> Tuple[str, float]:
        """Extract audio from video file. Returns (audio_path, duration)."""
        # TODO: Implement with ffmpeg
        # For now, return stub
        audio_path = str(self.output_dir / f"{job_id}_audio.wav")
        duration = 0.0  # TODO: Get from ffprobe
        return audio_path, duration
    
    def _run_asr(
        self,
        audio_path: str,
        mode: str,
        language: Optional[str],
        denoise: bool
    ) -> List[Dict[str, Any]]:
        """Run ASR transcription."""
        from videotext.asr import transcribe_audio
        
        segments = transcribe_audio(audio_path, mode, language, denoise)
        return segments
    
    def _run_diarization(
        self,
        audio_path: str,
        segments: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Run speaker diarization."""
        # TODO: Implement with pyannote.audio
        # For now, return segments unchanged
        return segments
    
    def _run_ocr(self, video_path: str, interval: int) -> List[Dict[str, Any]]:
        """Run OCR on video frames."""
        from videotext.ocr import extract_text_from_frames
        
        segments = extract_text_from_frames(video_path, interval)
        return segments
    
    def _merge_segments(
        self,
        asr_segments: List[Dict[str, Any]],
        ocr_segments: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Merge ASR and OCR segments by timeline."""
        # Simple merge: combine segments by time
        all_segments = asr_segments + ocr_segments
        all_segments.sort(key=lambda x: x['start'])
        
        # TODO: Implement smarter merging (handle overlaps, gaps)
        return all_segments
    
    def _translate_segments(
        self,
        segments: List[Dict[str, Any]],
        target_lang: str
    ) -> List[Dict[str, Any]]:
        """Translate segments to target language."""
        # TODO: Implement translation (e.g., with googletrans or API)
        return segments
    
    def _filter_keywords(
        self,
        segments: List[Dict[str, Any]],
        keywords: str
    ) -> List[Dict[str, Any]]:
        """Filter segments containing keywords."""
        keyword_list = [k.strip().lower() for k in keywords.split(',') if k.strip()]

        if not keyword_list:
            return []
        
        filtered = []
        for segment in segments:
            text_lower = segment['text'].lower()
            if any(keyword in text_lower for keyword in keyword_list):
                filtered.append(segment)
        
        return filtered
    
    def _export_artifacts(
        self,
        job_id: str,
        asr_segments: List[Dict[str, Any]],
        ocr_segments: List[Dict[str, Any]],
        merged_segments: List[Dict[str, Any]],
        filtered_segments: List[Dict[str, Any]],
        keywords: Optional[str]
    ) -> List[str]:
        """Export all artifacts (SRT, VTT, TXT, JSON, ZIP)."""
        artifacts = []
        job_dir = self.output_dir / job_id
        job_dir.mkdir(parents=True, exist_ok=True)
        
        # Export ASR segments
        if asr_segments:
            asr_srt = job_dir / "asr.srt"
            write_srt(asr_segments, str(asr_srt))
            artifacts.append(str(asr_srt))
            
            asr_txt = job_dir / "asr.txt"
            self._write_txt(asr_segments, str(asr_txt))
            artifacts.append(str(asr_txt))
        
        # Export OCR segments
        if ocr_segments:
            ocr_srt = job_dir / "ocr.srt"
            write_srt(ocr_segments, str(ocr_srt))
            artifacts.append(str(ocr_srt))
            
            ocr_txt = job_dir / "ocr.txt"
            self._write_txt(ocr_segments, str(ocr_txt))
            artifacts.append(str(ocr_txt))
        
        # Export merged segments
        merged_srt = job_dir / "merged.srt"
        write_srt(merged_segments, str(merged_srt))
        artifacts.append(str(merged_srt))
        
        merged_vtt = job_dir / "merged.vtt"
        write_vtt(merged_segments, str(merged_vtt))
        artifacts.append(str(merged_vtt))
        
        merged_txt = job_dir / "merged.txt"
        self._write_txt(merged_segments, str(merged_txt))
        artifacts.append(str(merged_txt))
        
        # Export JSON
        output_json = job_dir / "output.json"
        with open(output_json, 'w', encoding='utf-8') as f:
            json.dump({
                'asr': asr_segments,
                'ocr': ocr_segments,
                'merged': merged_segments,
                'timestamp': datetime.utcnow().isoformat()
            }, f, ensure_ascii=False, indent=2)
        artifacts.append(str(output_json))
        
        # Export filtered segments if keywords provided
        if keywords and filtered_segments:
            keywords_srt = job_dir / "keywords.srt"
            write_srt(filtered_segments, str(keywords_srt))
            artifacts.append(str(keywords_srt))
            
            keywords_vtt = job_dir / "keywords.vtt"
            write_vtt(filtered_segments, str(keywords_vtt))
            artifacts.append(str(keywords_vtt))
            
            keywords_txt = job_dir / "keywords.txt"
            self._write_txt(filtered_segments, str(keywords_txt))
            artifacts.append(str(keywords_txt))
        
        # Create ZIP archive
        zip_path = job_dir / "results.zip"
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
            for artifact in artifacts:
                if Path(artifact).exists():
                    zf.write(artifact, Path(artifact).name)
        artifacts.append(str(zip_path))
        
        # Return relative paths from artifacts directory
        relative_artifacts = []
        for artifact in artifacts:
            try:
                rel_path = Path(artifact).relative_to(self.output_dir)
                relative_artifacts.append(str(rel_path))
            except ValueError:
                # If not relative, use as-is
                relative_artifacts.append(str(artifact))
        
        return relative_artifacts
    
    def _write_txt(self, segments: List[Dict[str, Any]], path: str) -> None:
        """Write segments as plain text."""
        with open(path, 'w', encoding='utf-8') as f:
            for segment in segments:
                f.write(f"{segment['text']}\n")
