"""
vision_service.py - Manages the local LLaVA vision model and Gemini fallback.
"""
import os
import base64
from typing import Optional

try:
    from llama_cpp import Llama
    from llama_cpp.llama_chat_format import Llava15ChatHandler
    HAS_LLAVA = True
except ImportError:
    HAS_LLAVA = False

class VisionManager:
    def __init__(self, models_dir=None):
        from infrastructure.llm_provider import get_mode
        self.local_vlm = None
        self.gemini_model = None
        self._mode = get_mode()

        # In online mode, skip loading local models
        if self._mode == "online":
            print("[Vision] Online mode — will use Claude Vision API")
            return
        
        if models_dir is None:
            models_dir = os.getenv("MODELS_DIR")
            if models_dir is None and os.path.exists("/app/models"):
                models_dir = "/app/models"
            if models_dir is None:
                models_dir = os.path.join(
                    os.path.expanduser("~"),
                    "OneDrive", "Documentos", "START HACK", "epAI", "models"
                )
                
        llava_path = os.path.join(models_dir, "llava-v1.5-7b-Q4_K.gguf")
        mmproj_path = os.path.join(models_dir, "mmproj-model-f16.gguf")
        
        if HAS_LLAVA and os.path.exists(llava_path) and os.path.exists(mmproj_path):
            try:
                chat_handler = Llava15ChatHandler(clip_model_path=mmproj_path)
                self.local_vlm = Llama(
                    model_path=llava_path,
                    chat_handler=chat_handler,
                    n_ctx=1024,
                    n_threads=12,
                    verbose=False
                )
                print("[Vision] Loaded local LLaVA model")
            except Exception as e:
                print(f"[Vision] Could not load local LLaVA: {e}")
                
        # Fallback Gemini
        api_key = os.getenv("GEMINI_API_KEY")
        if api_key and self.local_vlm is None:
            try:
                import google.generativeai as genai
                genai.configure(api_key=api_key)
                self.gemini_model = genai.GenerativeModel("gemini-1.5-flash")
                print("[Vision] Using Gemini API fallback")
            except Exception as e:
                print(f"[Vision] Gemini init failed: {e}")

    @property
    def available(self) -> bool:
        if self._mode == "online":
            return True
        return self.local_vlm is not None or self.gemini_model is not None

    def analyze_image(self, image_bytes: bytes, prompt: str) -> str:
        if not self.available:
            return "Vision model is currently unavailable."

        # --- Online mode: Claude Vision ---
        if self._mode == "online":
            return self._claude_analyze_image(image_bytes, prompt)
            
        if self.local_vlm:
            # LLaVA chat format expects a data URI or just base64 string
            b64_img = base64.b64encode(image_bytes).decode('utf-8')
            data_uri = f"data:image/jpeg;base64,{b64_img}"
            
            messages = [
                {"role": "system", "content": "You are a helpful medical assistant."},
                {
                    "role": "user",
                    "content": [
                        {"type": "image_url", "image_url": {"url": data_uri}},
                        {"type": "text", "text": prompt}
                    ]
                }
            ]
            print(f"[Vision] Processing image (Base64 size: {len(b64_img)} chars)")
            print(f"[Vision] Prompt: {prompt}")
            try:
                print("[Vision] Sending to Local LLaVA... (This may take a minute)")
                out = self.local_vlm.create_chat_completion(
                    messages=messages, 
                    max_tokens=512,
                    temperature=0.4,
                    presence_penalty=0.4
                )
                raw_text = out["choices"][0]["message"]["content"].strip()
                print(f"[Vision] LLaVA Response: {raw_text[:200]}...")
                return raw_text
            except Exception as e:
                print(f"[Vision] Local LLaVA error: {e}")
                return "Error analyzing image locally."
                
        elif self.gemini_model:
            try:
                import PIL.Image
                import io
                image = PIL.Image.open(io.BytesIO(image_bytes))
                resp = self.gemini_model.generate_content([prompt, image])
                return resp.text.strip()
            except Exception as e:
                print(f"[Vision] Gemini Vision error: {e}")
                return "Error analyzing image with fallback."

    def _claude_analyze_image(self, image_bytes: bytes, prompt: str) -> str:
        """Send image to Claude Vision API for analysis."""
        from infrastructure.llm_provider import get_claude_client, CLAUDE_MODEL
        try:
            client = get_claude_client()
            b64_img = base64.b64encode(image_bytes).decode('utf-8')
            # Detect media type from bytes
            media_type = "image/jpeg"
            if image_bytes[:4] == b'\x89PNG':
                media_type = "image/png"
            elif image_bytes[:4] == b'%PDF':
                media_type = "image/png"  # PDF pages are converted to PNG

            resp = client.messages.create(
                model=CLAUDE_MODEL,
                max_tokens=1024,
                messages=[{
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": media_type,
                                "data": b64_img,
                            }
                        },
                        {
                            "type": "text",
                            "text": prompt
                        }
                    ]
                }]
            )
            return resp.content[0].text.strip()
        except Exception as e:
            print(f"[Vision] Claude Vision error: {e}")
            return "Error analyzing image with Claude."

_vision_manager = None
def get_vlm(models_dir=None):
    global _vision_manager
    from infrastructure.llm_provider import get_mode
    current_mode = get_mode()
    
    if _vision_manager is None or _vision_manager._mode != current_mode:
        _vision_manager = VisionManager(models_dir)
    return _vision_manager

