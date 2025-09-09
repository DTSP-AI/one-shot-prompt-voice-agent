"""
Vision processing integration with OpenAI GPT-4V and local CV fallbacks.
Handles image and video analysis for the voice agent system.
"""

import asyncio
import logging
from typing import Dict, Any, Optional, List, Union
import base64
import io
from datetime import datetime

try:
    import cv2
    import numpy as np
    CV2_AVAILABLE = True
except ImportError:
    CV2_AVAILABLE = False
    logger = logging.getLogger(__name__)
    logger.warning("OpenCV not available, limited vision capabilities")

try:
    from openai import AsyncOpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False
    logger = logging.getLogger(__name__)
    logger.warning("OpenAI not available, no cloud vision processing")

from PIL import Image
import httpx

logger = logging.getLogger(__name__)


class VisionError(Exception):
    """Custom vision processing error with remediation."""
    
    def __init__(self, message: str, remediation: str = ""):
        super().__init__(message)
        self.remediation = remediation


class LocalVisionProcessor:
    """Local computer vision processing fallback."""
    
    def __init__(self):
        self.available = CV2_AVAILABLE
        
    def analyze_image(self, image_data: bytes) -> Dict[str, Any]:
        """Analyze image using local CV methods."""
        if not self.available:
            return {"error": "OpenCV not available"}
        
        try:
            # Convert bytes to numpy array
            nparr = np.frombuffer(image_data, np.uint8)
            image = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            
            if image is None:
                return {"error": "Invalid image format"}
            
            # Basic image analysis
            height, width, channels = image.shape
            
            # Color analysis
            mean_color = np.mean(image, axis=(0, 1))
            
            # Edge detection
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            edges = cv2.Canny(gray, 100, 200)
            edge_density = np.sum(edges > 0) / (width * height)
            
            # Brightness analysis
            brightness = np.mean(gray)
            
            return {
                "dimensions": {"width": int(width), "height": int(height)},
                "channels": int(channels),
                "mean_color": mean_color.tolist(),
                "brightness": float(brightness),
                "edge_density": float(edge_density),
                "analysis_type": "local_cv"
            }
            
        except Exception as e:
            logger.error(f"Local vision analysis failed: {e}")
            return {"error": str(e)}


class VisionProcessor:
    """Main vision processor with cloud and local capabilities."""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.enabled = config.get("ENABLE_VISION", False)
        self.model = config.get("VISION_MODEL", "openai:gpt-4o-mini")
        
        # Initialize OpenAI client
        if OPENAI_AVAILABLE and config.get("OPENAI_API_KEY"):
            self.openai_client = AsyncOpenAI(api_key=config["OPENAI_API_KEY"])
            self.openai_available = True
        else:
            self.openai_client = None
            self.openai_available = False
        
        # Initialize local processor
        self.local_processor = LocalVisionProcessor()
        
        # HTTP client for external APIs
        self.http_client = httpx.AsyncClient(timeout=30.0)
        
        # Processing statistics
        self.request_count = 0
        self.error_count = 0
        self.last_error: Optional[str] = None
        
        if not self.enabled:
            logger.info("Vision processing disabled")
    
    async def analyze_image(self, 
                           image_data: bytes, 
                           prompt: str = "Describe what you see in this image",
                           content_type: str = "image/jpeg") -> Dict[str, Any]:
        """Analyze image with AI vision model."""
        if not self.enabled:
            return {
                "error": "Vision processing disabled",
                "remediation": "Set ENABLE_VISION=true to enable"
            }
        
        self.request_count += 1
        
        try:
            # Validate image
            validation_result = self._validate_image(image_data, content_type)
            if validation_result.get("error"):
                return validation_result
            
            # Try cloud processing first
            if self.openai_available:
                result = await self._analyze_with_openai(image_data, prompt, content_type)
                if not result.get("error"):
                    return result
                logger.warning(f"OpenAI analysis failed: {result.get('error')}")
            
            # Fallback to local processing
            logger.info("Using local vision analysis fallback")
            local_result = self.local_processor.analyze_image(image_data)
            local_result["fallback"] = True
            local_result["description"] = "Local computer vision analysis (limited capabilities)"
            
            return local_result
            
        except Exception as e:
            self.error_count += 1
            self.last_error = str(e)
            logger.error(f"Vision analysis failed: {e}")
            
            return {
                "error": str(e),
                "remediation": "Check image format and API configuration"
            }
    
    async def _analyze_with_openai(self, 
                                  image_data: bytes, 
                                  prompt: str,
                                  content_type: str) -> Dict[str, Any]:
        """Analyze image using OpenAI GPT-4V."""
        try:
            # Encode image to base64
            image_b64 = base64.b64encode(image_data).decode('utf-8')
            
            response = await self.openai_client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:{content_type};base64,{image_b64}",
                                    "detail": "high"
                                }
                            }
                        ]
                    }
                ],
                max_tokens=500,
                temperature=0.7
            )
            
            description = response.choices[0].message.content
            
            # Get basic image info
            basic_info = self.local_processor.analyze_image(image_data)
            
            return {
                "description": description,
                "model": "gpt-4o-mini",
                "prompt_tokens": response.usage.prompt_tokens,
                "completion_tokens": response.usage.completion_tokens,
                "analysis_type": "openai_vision",
                "basic_info": basic_info,
                "timestamp": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"OpenAI vision analysis failed: {e}")
            return {
                "error": f"OpenAI analysis failed: {e}",
                "remediation": "Check API key and quota limits"
            }
    
    async def analyze_video_frame(self, 
                                 video_data: bytes,
                                 frame_time: float = 0.0,
                                 prompt: str = "Describe this video frame") -> Dict[str, Any]:
        """Extract and analyze a frame from video data."""
        if not self.enabled:
            return {"error": "Vision processing disabled"}
        
        try:
            # Extract frame using OpenCV
            if not CV2_AVAILABLE:
                return {
                    "error": "Video processing not available",
                    "remediation": "Install OpenCV for video support"
                }
            
            # Save video data temporarily
            temp_path = f"/tmp/temp_video_{datetime.now().timestamp()}.mp4"
            with open(temp_path, "wb") as f:
                f.write(video_data)
            
            # Extract frame
            cap = cv2.VideoCapture(temp_path)
            cap.set(cv2.CAP_PROP_POS_MSEC, frame_time * 1000)  # Seek to time
            
            ret, frame = cap.read()
            cap.release()
            
            if not ret:
                return {"error": "Could not extract video frame"}
            
            # Convert frame to bytes
            _, buffer = cv2.imencode('.jpg', frame)
            frame_bytes = buffer.tobytes()
            
            # Analyze the frame
            result = await self.analyze_image(frame_bytes, prompt, "image/jpeg")
            result["frame_time"] = frame_time
            result["video_analysis"] = True
            
            # Clean up temp file
            try:
                import os
                os.remove(temp_path)
            except:
                pass
            
            return result
            
        except Exception as e:
            logger.error(f"Video frame analysis failed: {e}")
            return {
                "error": str(e),
                "remediation": "Check video format and OpenCV installation"
            }
    
    def _validate_image(self, image_data: bytes, content_type: str) -> Dict[str, Any]:
        """Validate image data and format."""
        try:
            # Check size limits (10MB max)
            if len(image_data) > 10 * 1024 * 1024:
                return {
                    "error": "Image too large (max 10MB)",
                    "remediation": "Compress image or reduce resolution"
                }
            
            # Check if it's a valid image
            try:
                image = Image.open(io.BytesIO(image_data))
                width, height = image.size
                format_name = image.format
            except Exception as e:
                return {
                    "error": f"Invalid image format: {e}",
                    "remediation": "Use JPEG, PNG, or WebP format"
                }
            
            # Check dimensions (reasonable limits)
            if width > 4096 or height > 4096:
                return {
                    "error": "Image dimensions too large (max 4096x4096)",
                    "remediation": "Resize image to smaller dimensions"
                }
            
            if width < 32 or height < 32:
                return {
                    "error": "Image too small (min 32x32)",
                    "remediation": "Use higher resolution image"
                }
            
            return {"valid": True, "width": width, "height": height, "format": format_name}
            
        except Exception as e:
            return {
                "error": f"Image validation failed: {e}",
                "remediation": "Check image file integrity"
            }
    
    async def get_supported_formats(self) -> List[str]:
        """Get list of supported image formats."""
        formats = ["image/jpeg", "image/png", "image/webp"]
        
        if CV2_AVAILABLE:
            formats.extend(["image/bmp", "image/tiff"])
        
        return formats
    
    async def health_check(self) -> Dict[str, Any]:
        """Perform vision service health check."""
        try:
            status = {
                "enabled": self.enabled,
                "openai_available": self.openai_available,
                "local_cv_available": self.local_processor.available,
                "request_count": self.request_count,
                "error_count": self.error_count,
                "error_rate": self.error_count / max(self.request_count, 1),
                "last_error": self.last_error,
                "timestamp": datetime.utcnow().isoformat()
            }
            
            if not self.enabled:
                status["status"] = "disabled"
                return status
            
            # Test with a simple image if available
            if self.openai_available:
                try:
                    # Create a minimal test image
                    test_image = Image.new('RGB', (100, 100), color='red')
                    buffer = io.BytesIO()
                    test_image.save(buffer, format='JPEG')
                    test_data = buffer.getvalue()
                    
                    result = await self._analyze_with_openai(
                        test_data, 
                        "What color is this image?", 
                        "image/jpeg"
                    )
                    
                    if result.get("error"):
                        status["status"] = "degraded"
                        status["openai_error"] = result["error"]
                    else:
                        status["status"] = "healthy"
                        
                except Exception as e:
                    status["status"] = "degraded"
                    status["openai_error"] = str(e)
            else:
                status["status"] = "limited"  # Local only
            
            return status
            
        except Exception as e:
            return {
                "status": "unhealthy",
                "error": str(e),
                "enabled": self.enabled,
                "timestamp": datetime.utcnow().isoformat(),
                "remediation": "Check vision service configuration and dependencies"
            }
    
    def get_stats(self) -> Dict[str, Any]:
        """Get vision processing statistics."""
        return {
            "enabled": self.enabled,
            "model": self.model,
            "request_count": self.request_count,
            "error_count": self.error_count,
            "error_rate": self.error_count / max(self.request_count, 1),
            "last_error": self.last_error,
            "openai_available": self.openai_available,
            "local_available": self.local_processor.available
        }
    
    async def close(self) -> None:
        """Close HTTP clients and cleanup."""
        await self.http_client.aclose()