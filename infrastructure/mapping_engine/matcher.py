"""
matcher.py - Column matching engine with 3-tier strategy + AI interpretation.

Tier 1: Exact match (header == DB column or known alias)
Tier 2: Fuzzy match (Levenshtein distance >= 80%)
Tier 3: AI interpretation via local LLM (Phi-3) or Gemini API
"""

import os
import json
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


from infrastructure.mapping_engine.profiles import COLUMN_ALIASES, STAGING_SCHEMAS

try:
    from fuzzywuzzy import process as fuzz_process
    HAS_FUZZY = True
except ImportError:
    HAS_FUZZY = False

try:
    from llama_cpp import Llama
    HAS_LLAMA = True
except ImportError:
    HAS_LLAMA = False


@dataclass
class ColumnMatch:
    """Represents a single column mapping decision."""
    source: str
    target: Optional[str]
    method: str           # exact | alias | fuzzy | ai | user | unmatched
    confidence: float     # 0.0-1.0
    description: str = "" # human-readable explanation


@dataclass
class MappingResult:
    """Full result of matching all columns from a file."""
    target_table: str
    auto_matched: List[ColumnMatch] = field(default_factory=list)
    ai_suggestions: List[ColumnMatch] = field(default_factory=list)
    unmatched: List[ColumnMatch] = field(default_factory=list)


# Phi-3 prompt template tokens
PHI3_USER_TAG = "<|user|>"
PHI3_END_TAG = "<|end|>"
PHI3_ASST_TAG = "<|assistant|>"


class LLMManager:
    """Local-first LLM: Phi-3 GGUF by default, Gemini if GEMINI_API_KEY is set, Claude if online."""

    def __init__(self, models_dir=None):
        from infrastructure.llm_provider import get_mode
        self.local_llm = None
        self.gemini_model = None
        self._mode = get_mode()   # capture mode at init time

        # In online mode, skip loading local models entirely
        if self._mode == "online":
            print("[matcher] Online mode — will use Claude API")
            return

        if models_dir is None:
            # 1. Try environment variable (useful for cloud/containers)
            models_dir = os.getenv("MODELS_DIR")
            
            # 2. Try container-standard path
            if models_dir is None and os.path.exists("/app/models"):
                models_dir = "/app/models"
                
            # 3. Fallback to local development path
            if models_dir is None:
                models_dir = os.path.join(
                    os.path.expanduser("~"),
                    "OneDrive", "Documentos", "START HACK", "epAI", "models"
                )

        local_path = os.path.join(models_dir, "phi-3-mini-4k-instruct.gguf")
        if HAS_LLAMA and os.path.exists(local_path):
            try:
                self.local_llm = Llama(
                    model_path=local_path, n_ctx=2048, n_threads=12, verbose=False
                )
                print("[matcher] Loaded local LLM: Phi-3 Mini")
            except Exception as e:
                print(f"[matcher] Could not load local LLM: {e}")

        api_key = os.getenv("GEMINI_API_KEY")
        if api_key and self.local_llm is None:
            try:
                import google.generativeai as genai
                genai.configure(api_key=api_key)
                self.gemini_model = genai.GenerativeModel("gemini-1.5-flash")
                print("[matcher] Using Gemini API")
            except Exception as e:
                print(f"[matcher] Gemini init failed: {e}")

    @property
    def available(self):
        if self._mode == "online":
            return True
        return self.local_llm is not None or self.gemini_model is not None

    def interpret_columns(self, unmatched_headers: List[str], target_columns: List[str], target_table: str, samples: Optional[Dict[str, List[Any]]] = None):
        """Ask LLM to interpret unmatched column names, using data samples if available."""
        if not self.available or not unmatched_headers:
            return []

        header_info = []
        for h in unmatched_headers:
            info = {"header": h}
            if samples and h in samples:
                info["example_values"] = [str(v) for v in samples[h][:5]] # top 5 samples
            header_info.append(info)

        prompt = (
            "You are a healthcare data mapping expert.\n"
            f"Target Table: {target_table}\n"
            f"Columns to analyze: {json.dumps(header_info, ensure_ascii=False)}\n"
            f"Available Target DB Columns: {json.dumps(target_columns, ensure_ascii=False)}\n\n"
            "Task: Map the input 'header' (which might be cryptic or encrypted) to the most likely 'target' DB column.\n"
            "Use the 'example_values' to infer the meaning if the header is not clear.\n"
            "If no certain match exists, set target to null.\n"
            'Return ONLY JSON array: [{\"source\":\"header_name\",\"target\":\"db_col_name\",\"description\":\"brief reasoning\",\"confidence\":0.85}]'
        )


        raw = ""
        try:
            if self._mode == "online":
                raw = self._claude_generate(prompt)
            elif self.local_llm:
                out = self.local_llm.create_chat_completion(
                    messages=[{"role": "user", "content": prompt}],
                    max_tokens=512, 
                    temperature=0.0,
                    response_format={"type": "json_object"}
                )
                raw = out["choices"][0]["message"]["content"]
            elif self.gemini_model:
                resp = self.gemini_model.generate_content(prompt)
                raw = resp.text
        except Exception as e:
            print(f"[matcher] LLM error: {e}")
            return []

        return self._parse_ai_response(raw)

    def _parse_ai_response(self, raw):
        """Extract JSON array from LLM response."""
        results = []
        try:
            start = raw.find("[")
            end = raw.rfind("]") + 1
            if start >= 0 and end > start:
                items = json.loads(raw[start:end])
                for item in items:
                    results.append(ColumnMatch(
                        source=item.get("source", ""),
                        target=item.get("target"),
                        method="ai",
                        confidence=float(item.get("confidence", 0.5)),
                        description=item.get("description", ""),
                    ))
        except (json.JSONDecodeError, ValueError) as e:
            print(f"[matcher] Could not parse AI response: {e}")
        return results

    def generate_text(self, prompt, system_prompt="", json_mode=False):
        """General purpose text generation via available LLM."""
        if not self.available:
            return ""

        # --- Online mode: Claude ---
        if self._mode == "online":
            return self._claude_generate(prompt, system_prompt=system_prompt)

        if self.local_llm:
            try:
                if json_mode:
                    msgs = []
                    if system_prompt:
                        msgs.append({"role": "system", "content": system_prompt})
                    msgs.append({"role": "user", "content": prompt})
                    
                    out = self.local_llm.create_chat_completion(
                        messages=msgs,
                        max_tokens=512,
                        temperature=0.0,
                        response_format={"type": "json_object"}
                    )
                    return out["choices"][0]["message"]["content"].strip()
                else:
                    full_prompt = ""
                    if system_prompt:
                        full_prompt += PHI3_USER_TAG + "\nSystem: " + system_prompt + PHI3_END_TAG + "\n"
                    full_prompt += PHI3_USER_TAG + "\n" + prompt + PHI3_END_TAG + "\n" + PHI3_ASST_TAG
                    
                    out = self.local_llm(
                        full_prompt, max_tokens=512, stop=[PHI3_END_TAG], temperature=0.2
                    )
                    return out["choices"][0]["text"].strip()
            except Exception as e:
                print(f"[LLMManager] Local generate error: {e}")
                return ""
        
        elif self.gemini_model:
            try:
                combined = f"{system_prompt}\n\n{prompt}" if system_prompt else prompt
                resp = self.gemini_model.generate_content(combined)
                return resp.text.strip()
            except Exception as e:
                print(f"[LLMManager] Gemini generate error: {e}")
                return ""
        
        return ""

    # -----------------------------------------------------------------
    # Claude helpers (online mode)
    # -----------------------------------------------------------------

    def _claude_generate(self, prompt, system_prompt="", max_tokens=1024):
        """Send a single prompt to Claude and return the text response."""
        from infrastructure.llm_provider import get_claude_client, CLAUDE_MODEL
        try:
            client = get_claude_client()
            kwargs = {
                "model": CLAUDE_MODEL,
                "max_tokens": max_tokens,
                "messages": [{"role": "user", "content": prompt}],
            }
            if system_prompt:
                kwargs["system"] = system_prompt
            resp = client.messages.create(**kwargs)
            return resp.content[0].text.strip()
        except Exception as e:
            print(f"[LLMManager] Claude generate error: {e}")
            return ""

    def claude_chat_completion(self, messages, system_prompt="", max_tokens=1024):
        """
        Multi-turn chat via Claude. `messages` is a list of
        {"role": "user"|"assistant", "content": "..."}.
        """
        from infrastructure.llm_provider import get_claude_client, CLAUDE_MODEL
        try:
            client = get_claude_client()
            # Filter out system messages — Claude uses a separate param
            chat_msgs = [m for m in messages if m["role"] != "system"]
            # Ensure first message is from user (Claude requirement)
            if chat_msgs and chat_msgs[0]["role"] != "user":
                chat_msgs = [{"role": "user", "content": "Hello"}] + chat_msgs
            kwargs = {
                "model": CLAUDE_MODEL,
                "max_tokens": max_tokens,
                "messages": chat_msgs,
            }
            if system_prompt:
                kwargs["system"] = system_prompt
            resp = client.messages.create(**kwargs)
            return resp.content[0].text.strip()
        except Exception as e:
            print(f"[LLMManager] Claude chat error: {e}")
            return ""


# Singleton LLM manager (lazy init)
_llm_manager = None


def get_llm(models_dir=None):
    global _llm_manager
    from infrastructure.llm_provider import get_mode
    current_mode = get_mode()
    
    if _llm_manager is None or _llm_manager._mode != current_mode:
        _llm_manager = LLMManager(models_dir)
    return _llm_manager



def match_columns(source_headers, target_table, use_ai=True, models_dir=None, samples=None):
    """
    Match source file headers to a target staging table's columns.
    `samples` is an optional dict {header: [val1, val2...]} to help AI inference.
    """
    schema = STAGING_SCHEMAS.get(target_table)
    if not schema:
        return MappingResult(target_table=target_table)

    target_cols = [c for c in schema["columns"] if c != "coId"]
    result = MappingResult(target_table=target_table)
    still_unmatched = []

    for header in source_headers:
        match = _try_auto_match(header, target_cols)
        if match:
            result.auto_matched.append(match)
        else:
            still_unmatched.append(header)

    # Tier 3: AI interpretation for remaining unmatched
    if use_ai and still_unmatched:
        llm = get_llm(models_dir)
        ai_results = llm.interpret_columns(still_unmatched, target_cols, target_table, samples=samples)
        matched_by_ai = {r.source for r in ai_results if r.target}
        result.ai_suggestions = [r for r in ai_results if r.target]
        for header in still_unmatched:
            if header not in matched_by_ai:
                result.unmatched.append(
                    ColumnMatch(source=header, target=None, method="unmatched", confidence=0.0)
                )
    else:
        for header in still_unmatched:
            result.unmatched.append(
                ColumnMatch(source=header, target=None, method="unmatched", confidence=0.0)
            )

    return result



def _try_auto_match(header, target_cols):
    """Try exact, alias, prefix, and fuzzy matching (tiers 1-2)."""
    clean = header.strip()
    clean_lower = clean.lower()

    # Tier 1a: Exact match
    for tc in target_cols:
        if clean_lower == tc.lower():
            return ColumnMatch(
                source=header, target=tc, method="exact", confidence=1.0,
                description=f"Exact match: {header} == {tc}"
            )

    # Tier 1b: Known alias (German -> English)
    if clean_lower in COLUMN_ALIASES:
        alias_target = COLUMN_ALIASES[clean_lower]
        # Check alias target exists in this table's columns
        target_lower_map = {t.lower(): t for t in target_cols}
        if alias_target.lower() in target_lower_map:
            return ColumnMatch(
                source=header, target=target_lower_map[alias_target.lower()],
                method="alias", confidence=0.95,
                description=f"Known alias: {header} -> {alias_target}"
            )

    # Tier 1c: co-prefix match (source=sodium_mmol_L -> target=coSodium_mmol_L)
    # Also handle E_I_ pattern for epaAC: e0_i_001 -> coE0I001
    prefixed = "co" + clean[0:1].upper() + clean[1:] if clean else ""
    prefixed_norm = prefixed.replace("_", "").lower()

    for tc in target_cols:
        tc_norm = tc.lower().replace("_", "")
        if prefixed_norm == tc_norm:
            return ColumnMatch(
                source=header, target=tc, method="exact", confidence=0.98,
                description=f"Prefix match: co + {header} == {tc}"
            )


    # Tier 2: Fuzzy matching
    if HAS_FUZZY:
        target_lower_list = [t.lower() for t in target_cols]
        best, score = fuzz_process.extractOne(clean_lower, target_lower_list)
        if score >= 80:
            real_target = target_cols[target_lower_list.index(best)]
            return ColumnMatch(
                source=header, target=real_target, method="fuzzy",
                confidence=score / 100.0,
                description=f"Fuzzy match ({score}%): {header} ~ {real_target}"
            )

    return None
