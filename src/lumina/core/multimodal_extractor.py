
"""
多模态内容萃取器
支持图片 OCR、PDF 结构化解析、音频/视频字幕提取、代码理解增强
"""

import os
import re
import json
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple, Union
from dataclasses import dataclass
from abc import ABC, abstractmethod
import base64


@dataclass
class ExtractedContent:
    """提取的内容"""
    text: str
    metadata: Dict[str, Any]
    content_type: str  # 'image', 'pdf', 'audio', 'video', 'code'
    confidence: float = 0.0


class BaseExtractor(ABC):
    """内容提取器基类"""
    
    @abstractmethod
    def can_extract(self, file_path: Path) -> bool:
        """判断是否能处理该文件"""
        pass
    
    @abstractmethod
    def extract(self, file_path: Path) -> ExtractedContent:
        """提取内容"""
        pass


class ImageExtractor(BaseExtractor):
    """图片内容提取器（OCR）"""
    
    SUPPORTED_FORMATS = {'.png', '.jpg', '.jpeg', '.gif', '.bmp', '.webp', '.tiff'}
    
    def can_extract(self, file_path: Path) -> bool:
        return file_path.suffix.lower() in self.SUPPORTED_FORMATS
    
    def extract(self, file_path: Path) -> ExtractedContent:
        """提取图片中的文字内容"""
        try:
            # 尝试使用 pytesseract 进行 OCR
            import pytesseract
            from PIL import Image
            
            image = Image.open(file_path)
            text = pytesseract.image_to_string(image, lang='chi_sim+eng')
            
            # 获取图片元数据
            metadata = {
                "width": image.width,
                "height": image.height,
                "format": image.format,
                "mode": image.mode,
                "size_bytes": file_path.stat().st_size,
            }
            
            return ExtractedContent(
                text=text.strip(),
                metadata=metadata,
                content_type="image",
                confidence=0.85  # OCR 置信度
            )
            
        except ImportError:
            # 如果没有安装 pytesseract，返回图片描述
            return ExtractedContent(
                text=f"[Image: {file_path.name} - OCR not available, install pytesseract]",
                metadata={"size_bytes": file_path.stat().st_size},
                content_type="image",
                confidence=0.0
            )
        except Exception as e:
            return ExtractedContent(
                text=f"[Image: {file_path.name} - Error: {str(e)}]",
                metadata={"error": str(e)},
                content_type="image",
                confidence=0.0
            )


class PDFExtractor(BaseExtractor):
    """PDF 内容提取器"""
    
    SUPPORTED_FORMATS = {'.pdf'}
    
    def can_extract(self, file_path: Path) -> bool:
        return file_path.suffix.lower() in self.SUPPORTED_FORMATS
    
    def extract(self, file_path: Path) -> ExtractedContent:
        """提取 PDF 中的文字内容"""
        try:
            import PyPDF2
            
            text_parts = []
            metadata = {}
            
            with open(file_path, 'rb') as f:
                reader = PyPDF2.PdfReader(f)
                
                # 提取元数据
                if reader.metadata:
                    metadata = {
                        "title": reader.metadata.get('/Title', ''),
                        "author": reader.metadata.get('/Author', ''),
                        "subject": reader.metadata.get('/Subject', ''),
                        "creator": reader.metadata.get('/Creator', ''),
                        "pages": len(reader.pages),
                    }
                
                # 提取每页文字
                for i, page in enumerate(reader.pages):
                    page_text = page.extract_text()
                    if page_text:
                        text_parts.append(f"\n--- Page {i+1} ---\n{page_text}")
            
            full_text = "\n".join(text_parts)
            
            # 如果文字很少，可能是扫描版 PDF，提示需要 OCR
            if len(full_text.strip()) < 100:
                full_text = f"[PDF appears to be scanned/image-based. Text extraction limited. Consider using OCR.]\n{full_text}"
            
            return ExtractedContent(
                text=full_text,
                metadata=metadata,
                content_type="pdf",
                confidence=0.9 if len(full_text) > 500 else 0.5
            )
            
        except ImportError:
            return ExtractedContent(
                text=f"[PDF: {file_path.name} - PyPDF2 not installed]",
                metadata={"size_bytes": file_path.stat().st_size},
                content_type="pdf",
                confidence=0.0
            )
        except Exception as e:
            return ExtractedContent(
                text=f"[PDF: {file_path.name} - Error: {str(e)}]",
                metadata={"error": str(e)},
                content_type="pdf",
                confidence=0.0
            )


class AudioExtractor(BaseExtractor):
    """音频内容提取器（语音转文字）"""
    
    SUPPORTED_FORMATS = {'.mp3', '.wav', '.m4a', '.flac', '.ogg', '.aac'}
    
    def can_extract(self, file_path: Path) -> bool:
        return file_path.suffix.lower() in self.SUPPORTED_FORMATS
    
    def extract(self, file_path: Path) -> ExtractedContent:
        """提取音频中的语音内容"""
        try:
            # 尝试使用 Whisper API
            import whisper
            
            model = whisper.load_model("base")
            result = model.transcribe(str(file_path))
            
            text = result["text"]
            segments = result.get("segments", [])
            
            # 格式化输出，包含时间戳
            formatted_parts = []
            for segment in segments:
                start = segment["start"]
                end = segment["end"]
                segment_text = segment["text"]
                formatted_parts.append(f"[{start:.1f}s - {end:.1f}s] {segment_text}")
            
            metadata = {
                "duration": segments[-1]["end"] if segments else 0,
                "language": result.get("language", "unknown"),
                "segments_count": len(segments),
                "size_bytes": file_path.stat().st_size,
            }
            
            return ExtractedContent(
                text="\n".join(formatted_parts),
                metadata=metadata,
                content_type="audio",
                confidence=result.get("confidence", 0.8)
            )
            
        except ImportError:
            return ExtractedContent(
                text=f"[Audio: {file_path.name} - Whisper not installed]",
                metadata={"size_bytes": file_path.stat().st_size},
                content_type="audio",
                confidence=0.0
            )
        except Exception as e:
            return ExtractedContent(
                text=f"[Audio: {file_path.name} - Error: {str(e)}]",
                metadata={"error": str(e)},
                content_type="audio",
                confidence=0.0
            )


class VideoExtractor(BaseExtractor):
    """视频内容提取器（提取音频后转文字）"""
    
    SUPPORTED_FORMATS = {'.mp4', '.avi', '.mkv', '.mov', '.wmv', '.flv'}
    
    def can_extract(self, file_path: Path) -> bool:
        return file_path.suffix.lower() in self.SUPPORTED_FORMATS
    
    def extract(self, file_path: Path) -> ExtractedContent:
        """提取视频中的音频并转文字"""
        try:
            from moviepy.editor import VideoFileClip
            
            # 提取音频到临时文件
            video = VideoFileClip(str(file_path))
            audio_path = file_path.with_suffix('.temp.wav')
            video.audio.write_audiofile(str(audio_path), fps=16000)
            
            # 使用音频提取器
            audio_extractor = AudioExtractor()
            result = audio_extractor.extract(audio_path)
            
            # 添加视频元数据
            result.metadata.update({
                "duration": video.duration,
                "fps": video.fps,
                "size": video.size,
                "original_format": file_path.suffix,
            })
            result.content_type = "video"
            
            # 清理临时文件
            video.close()
            if audio_path.exists():
                audio_path.unlink()
            
            return result
            
        except ImportError:
            return ExtractedContent(
                text=f"[Video: {file_path.name} - moviepy not installed]",
                metadata={"size_bytes": file_path.stat().st_size},
                content_type="video",
                confidence=0.0
            )
        except Exception as e:
            return ExtractedContent(
                text=f"[Video: {file_path.name} - Error: {str(e)}]",
                metadata={"error": str(e)},
                content_type="video",
                confidence=0.0
            )


class CodeExtractor(BaseExtractor):
    """代码文件增强提取器"""
    
    SUPPORTED_FORMATS = {
        '.py', '.js', '.ts', '.java', '.cpp', '.c', '.h', '.hpp',
        '.go', '.rs', '.rb', '.php', '.swift', '.kt', '.scala',
        '.r', '.m', '.mm', '.cs', '.vb', '.fs', '.clj',
        '.erl', '.ex', '.exs', '.hs', '.lua', '.pl', '.pm',
        '.sh', '.bash', '.zsh', '.fish', '.ps1', '.bat', '.cmd',
        '.sql', '.html', '.css', '.scss', '.sass', '.less',
        '.xml', '.json', '.yaml', '.yml', '.toml', '.ini', '.cfg',
        '.dockerfile', '.makefile', '.cmake', '.gradle', '.maven',
    }
    
    def can_extract(self, file_path: Path) -> bool:
        return file_path.suffix.lower() in self.SUPPORTED_FORMATS
    
    def extract(self, file_path: Path) -> ExtractedContent:
        """增强提取代码文件内容"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # 分析代码结构
            analysis = self._analyze_code(content, file_path.suffix)
            
            metadata = {
                "language": analysis["language"],
                "lines": len(content.splitlines()),
                "functions": analysis["functions"],
                "classes": analysis["classes"],
                "imports": analysis["imports"],
                "size_bytes": file_path.stat().st_size,
            }
            
            # 构建增强内容
            enhanced_content = self._build_enhanced_content(content, analysis)
            
            return ExtractedContent(
                text=enhanced_content,
                metadata=metadata,
                content_type="code",
                confidence=0.95
            )
            
        except Exception as e:
            return ExtractedContent(
                text=f"[Code: {file_path.name} - Error: {str(e)}]",
                metadata={"error": str(e)},
                content_type="code",
                confidence=0.0
            )
    
    def _analyze_code(self, content: str, suffix: str) -> Dict[str, Any]:
        """分析代码结构"""
        language_map = {
            '.py': 'Python',
            '.js': 'JavaScript',
            '.ts': 'TypeScript',
            '.java': 'Java',
            '.cpp': 'C++',
            '.c': 'C',
            '.go': 'Go',
            '.rs': 'Rust',
            '.rb': 'Ruby',
        }
        
        # 基础统计
        lines = content.splitlines()
        functions = len(re.findall(r'(?:def|function|func)\s+\w+', content))
        classes = len(re.findall(r'(?:class|struct|interface)\s+\w+', content))
        
        # 提取导入/依赖
        imports = []
        if suffix == '.py':
            imports = re.findall(r'^(?:import|from)\s+([\w.]+)', content, re.MULTILINE)
        elif suffix in ['.js', '.ts']:
            imports = re.findall(r'(?:import|require)\s*\(?[\'"]([^\'"]+)', content)
        
        return {
            "language": language_map.get(suffix, 'Unknown'),
            "functions": functions,
            "classes": classes,
            "imports": imports[:20],  # 限制数量
        }
    
    def _build_enhanced_content(self, content: str, analysis: Dict[str, Any]) -> str:
        """构建增强的代码内容"""
        parts = [
            f"## Code Analysis",
            f"- Language: {analysis['language']}",
            f"- Functions: {analysis['functions']}",
            f"- Classes: {analysis['classes']}",
        ]
        
        if analysis['imports']:
            parts.append(f"- Key Dependencies: {', '.join(analysis['imports'][:10])}")
        
        parts.extend([
            "",
            "## Source Code",
            "```",
            content,
            "```"
        ])
        
        return "\n".join(parts)


class MultimodalExtractor:
    """
    多模态内容提取器
    自动识别文件类型并选择合适的提取器
    """
    
    def __init__(self):
        self.extractors: List[BaseExtractor] = [
            ImageExtractor(),
            PDFExtractor(),
            AudioExtractor(),
            VideoExtractor(),
            CodeExtractor(),
        ]
    
    def extract(self, file_path: Path) -> ExtractedContent:
        """
        提取文件内容
        自动选择合适的提取器
        """
        # 尝试所有提取器
        for extractor in self.extractors:
            if extractor.can_extract(file_path):
                return extractor.extract(file_path)
        
        # 没有合适的提取器，尝试作为文本读取
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            return ExtractedContent(
                text=content,
                metadata={"size_bytes": file_path.stat().st_size},
                content_type="text",
                confidence=1.0
            )
        except Exception:
            return ExtractedContent(
                text=f"[Unsupported file type: {file_path.suffix}]",
                metadata={"size_bytes": file_path.stat().st_size},
                content_type="unknown",
                confidence=0.0
            )
    
    def get_supported_types(self) -> List[str]:
        """获取支持的文件类型列表"""
        types = set()
        for extractor in self.extractors:
            types.update(extractor.SUPPORTED_FORMATS)
        return sorted(list(types))
