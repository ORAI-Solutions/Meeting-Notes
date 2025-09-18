from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, TYPE_CHECKING
import json
import os
import re
from pathlib import Path

from sqlmodel import Session

from app.repositories.summaries import SummariesRepository
from app.repositories.transcripts import TranscriptsRepository
from app.repositories.settings import get_app_settings
from app.config import Settings

try:
    from llama_cpp import Llama, llama_supports_gpu_offload, LlamaGrammar  # type: ignore
except Exception:  # pragma: no cover
    Llama = None  # type: ignore
    llama_supports_gpu_offload = None  # type: ignore
    LlamaGrammar = None  # type: ignore

if TYPE_CHECKING:  # pragma: no cover
    from app.models.transcript_segment import TranscriptSegment


@dataclass
class LlmConfig:
    model_path: Optional[str] = None
    temperature: float = 0.0
    top_p: float = 1.0
    max_tokens: int = 0


def summarize_meeting(
    meeting_id: int,
    session: Session,
    cfg: Optional[LlmConfig] = None,
    length: Optional[str] = None,
) -> dict:
    """Summarize a meeting transcript locally using llama-cpp.

    Uses app settings to resolve model and device. If no model is configured or
    present locally, raises a clear error. Stores the result in the DB.
    """
    segments = TranscriptsRepository(session).list_by_meeting(meeting_id)
    if not segments:
        summary = SummariesRepository(session).upsert_for_meeting(
            meeting_id,
            abstract_md="",
            bullets_md="",
        )
        return {"summary": summary}

    if Llama is None:
        raise RuntimeError(
            "llama-cpp-python is not available. Install it to enable summarization."
        )

    settings_dict = get_app_settings(session)
    model_path = _resolve_model_path_from_settings(settings_dict, cfg)
    n_ctx = 65536
    n_gpu_layers = _determine_gpu_layers(settings_dict)

    llm = Llama(
        model_path=str(model_path),
        n_ctx=n_ctx,
        n_gpu_layers=n_gpu_layers,
        verbose=False,
    )

    # Configure detail profile (short|mid|long) which controls chunking and prompt targets
    profile = _get_length_profile(length or "mid")

    transcript_text = _render_transcript_with_ids(segments)
    chunks = _chunk_text(
        transcript_text,
        max_chars=int(profile.get("chunk_chars", 6000)),
        overlap=int(profile.get("chunk_overlap", 600)),
    )

    temperature = cfg.temperature if cfg else 0.2
    top_p = cfg.top_p if cfg else 0.9
    max_tokens = cfg.max_tokens if cfg and cfg.max_tokens > 0 else 8192

    partials: List[Dict[str, Any]] = []
    for chunk in chunks:
        out = _summarize_chunk_json(
            llm=llm,
            chunk_text=chunk,
            temperature=temperature,
            top_p=top_p,
            max_tokens=max_tokens,
            profile=profile,
        )
        partials.append(out)

    if len(partials) == 1:
        abstract_md = partials[0].get("abstract_md", "").strip()
        bullets_list = partials[0].get("bullets_md", [])
    else:
        reduce_out = _reduce_summaries_json(
            llm=llm,
            partials=partials,
            temperature=temperature,
            top_p=top_p,
            max_tokens=max_tokens,
            profile=profile,
        )
        abstract_md = reduce_out.get("abstract_md", "").strip()
        bullets_list = reduce_out.get("bullets_md", [])

    bullets_md = _format_bullets_md(bullets_list)

    summary = SummariesRepository(session).upsert_for_meeting(
        meeting_id,
        abstract_md=abstract_md,
        bullets_md=bullets_md,
    )
    return {"summary": summary}


def _resolve_model_path_from_settings(settings_dict: Dict[str, Any], cfg: Optional[LlmConfig]) -> Path:
    llm_cfg = settings_dict.get("llm") or {}
    candidate = None
    if cfg and cfg.model_path:
        candidate = cfg.model_path
    elif isinstance(llm_cfg, dict) and llm_cfg.get("model_path"):
        candidate = str(llm_cfg.get("model_path"))
    if candidate:
        p = Path(os.path.expandvars(str(candidate))).expanduser()
        if p.exists():
            return p
        raise FileNotFoundError(f"LLM model file not found: {p}")

    models_dir = Settings().models_dir / "llm"
    try:
        models_dir.mkdir(parents=True, exist_ok=True)
    except Exception:
        pass
    found: List[Path] = []
    for root, _, files in os.walk(models_dir):
        for f in files:
            if f.lower().endswith(".gguf"):
                found.append(Path(root) / f)
    if found:
        return sorted(found)[0]
    raise RuntimeError(
        "No local LLM model configured or found. Configure a GGUF model path in Settings."
    )


def _determine_gpu_layers(settings_dict: Dict[str, Any]) -> int:
    device = str(settings_dict.get("llm_device", "auto")).lower()
    if device == "cpu":
        return 0
    
    # Check if CUDA libraries are available for LLM
    if device in ["cuda", "auto"]:
        try:
            from app.services.cuda_runtime_manager import get_cuda_manager
            cuda_mgr = get_cuda_manager()
            gpu_ready, missing = cuda_mgr.check_gpu_ready("llama_gpu")
            
            if not gpu_ready and device == "cuda":
                # User specifically requested CUDA, try to download missing libraries
                print(f"CUDA requested for LLM but missing libraries: {missing}")
                print("Downloading CUDA runtime libraries for GPU acceleration...")
                success = cuda_mgr.download_libraries(missing)
                if success:
                    print("CUDA libraries downloaded successfully for LLM")
                    return 999
                else:
                    print("Failed to download CUDA libraries for LLM, falling back to CPU")
                    return 0
            elif gpu_ready:
                # Check if llama-cpp actually supports GPU
                if llama_supports_gpu_offload and bool(llama_supports_gpu_offload()):
                    return 999
        except Exception as e:
            print(f"Error checking CUDA availability for LLM: {e}")
            
    return 0


def _render_transcript_with_ids(segments: List["TranscriptSegment"]) -> str:
    parts: List[str] = []
    for seg in segments:
        sid = getattr(seg, "id", None)
        speaker = (seg.speaker or "Speaker").strip()
        marker = f"[#{sid}] " if isinstance(sid, int) else ""
        parts.append(f"{marker}{speaker}: {seg.text}".strip())
    return "\n".join(parts)


def _chunk_text(text: str, max_chars: int = 6000, overlap: int = 600) -> List[str]:
    if max_chars <= 0:
        return [text]
    chunks: List[str] = []
    n = len(text)
    i = 0
    while i < n:
        end = min(n, i + max_chars)
        chunk = text[i:end]
        chunks.append(chunk)
        if end >= n:
            break
        i = max(0, end - overlap)
    return chunks


def _summarize_chunk_json(
    *,
    llm: "Llama",
    chunk_text: str,
    temperature: float,
    top_p: float,
    max_tokens: int,
    profile: Dict[str, Any],
) -> Dict[str, Any]:
    system = (
        "You write concise meeting summaries. Return ONLY strict JSON with keys "
        "'abstract_md' and 'bullets_md'. 'bullets_md' is an array of bullet strings. "
        "Keep citations like [#123] if present."
    )
    target_bullets = int(profile.get("target_bullets", 10))
    target_sentences = int(profile.get("target_abstract_sentences", 8))
    user = (
        "Summarize the following transcript chunk. Output JSON only.\n"
        f"Abstract: Up to {target_sentences} concise sentences.\n"
        f"Bullets: Up to {target_bullets} key points that make sense and contain a relevant detail, each one line.\n\n"
        "Transcript:\n" + chunk_text
    )
    grammar = _get_summary_json_grammar()
    content = _chat_json(
        llm,
        system,
        user,
        temperature,
        top_p,
        max_tokens,
        grammar=grammar,
    )
    data = _parse_json_lenient(content)
    if not isinstance(data, dict):
        return {"abstract_md": "", "bullets_md": []}
    abstract = str(data.get("abstract_md", ""))
    bullets = data.get("bullets_md", [])
    if not isinstance(bullets, list):
        bullets = []
    bullets = [str(b).strip() for b in bullets if str(b).strip()]
    return {"abstract_md": abstract, "bullets_md": bullets}


def _reduce_summaries_json(
    *,
    llm: "Llama",
    partials: List[Dict[str, Any]],
    temperature: float,
    top_p: float,
    max_tokens: int,
    profile: Dict[str, Any],
) -> Dict[str, Any]:
    abstracts = [str(p.get("abstract_md", "")) for p in partials if str(p.get("abstract_md", "")).strip()]
    bullets: List[str] = []
    for p in partials:
        items = p.get("bullets_md", [])
        if isinstance(items, list):
            bullets.extend([str(x) for x in items if str(x).strip()])

    bullets_text = "\n".join(f"- {b.lstrip('- ').strip()}" for b in bullets)
    abstracts_text = "\n\n".join(abstracts)
    system = (
        "Combine partial meeting summaries into a single concise summary. "
        "Return ONLY JSON with 'abstract_md' and 'bullets_md' (array). "
        "Keep citations like [#123] if present. Avoid duplicates."
    )
    target_bullets = int(profile.get("target_bullets", 10))
    target_sentences = int(profile.get("target_abstract_sentences", 8))
    user = (
        "Combine the partials into a final result. Output JSON only.\n"
        f"Abstract: Up to{target_sentences} sentences.\n"
        f"Bullets: Up to {target_bullets} deduped key points.\n\n"
        "Abstracts:\n" + abstracts_text + "\n\n" +
        "Bullets:\n" + bullets_text
    )
    grammar = _get_summary_json_grammar()
    content = _chat_json(
        llm,
        system,
        user,
        temperature,
        top_p,
        max_tokens,
        grammar=grammar,
    )
    data = _parse_json_lenient(content)
    if not isinstance(data, dict):
        return {"abstract_md": "", "bullets_md": []}
    abstract = str(data.get("abstract_md", ""))
    out_bullets = data.get("bullets_md", [])
    if not isinstance(out_bullets, list):
        out_bullets = []
    out_bullets = [str(b).strip() for b in out_bullets if str(b).strip()]
    return {"abstract_md": abstract, "bullets_md": out_bullets}


def _format_bullets_md(bullets: List[str]) -> str:
    if not bullets:
        return ""
    lines = []
    seen: set[str] = set()
    for b in bullets:
        key = b.lstrip("- ").strip()
        if key and key.lower() not in seen:
            lines.append(f"- {key}")
            seen.add(key.lower())
    return "\n".join(lines)


def _get_length_profile(length: str) -> Dict[str, Any]:
    l = (length or "mid").lower()
    if l == "short":
        return {
            "chunk_chars": 7000,
            "chunk_overlap": 700,
            "target_bullets": 8,
            "target_abstract_sentences": 8,
        }
    if l == "long":
        return {
            "chunk_chars": 7000,
            "chunk_overlap": 700,
            "target_bullets": 15,
            "target_abstract_sentences": 15,
        }
    # mid (default)
    return {
        "chunk_chars": 7000,
        "chunk_overlap": 700,
        "target_bullets": 12,
        "target_abstract_sentences": 12,
    }


def _chat_json(
    llm: "Llama",
    system: str,
    user: str,
    temperature: float,
    top_p: float,
    max_tokens: int,
) -> str:
    return _chat_json(
        llm,
        system,
        user,
        temperature,
        top_p,
        max_tokens,
        grammar=None,
    )


def _chat_json(
    llm: "Llama",
    system: str,
    user: str,
    temperature: float,
    top_p: float,
    max_tokens: int,
    grammar: Optional[object] = None,
) -> str:
    try:
        kwargs: Dict[str, Any] = {
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": temperature,
            "top_p": top_p,
            "max_tokens": max_tokens,
        }
        if grammar is not None:
            kwargs["grammar"] = grammar
        else:
            kwargs["response_format"] = {"type": "json_object"}
        resp = llm.create_chat_completion(**kwargs)
        content = resp["choices"][0]["message"]["content"]
        return str(content)
    except Exception:
        # Fallback to plain completion
        prompt = (
            f"System: {system}\n\nUser: {user}\n\nAssistant (JSON only):"
        )
        comp = llm(prompt, max_tokens=max_tokens, temperature=temperature, top_p=top_p)
        return str(comp.get("choices", [{}])[0].get("text", ""))


def _parse_json_lenient(text: str) -> Any:
    t = (text or "").strip()
    try:
        return json.loads(t)
    except Exception:
        pass
    # Try to extract the first {...} block
    start = t.find("{")
    end = t.rfind("}")
    if start != -1 and end != -1 and end > start:
        sub = t[start : end + 1]
        try:
            return json.loads(sub)
        except Exception:
            pass
    # Attempt to coerce from a lax structure into expected keys
    bullets = []
    abstract = ""
    # Lines starting with '-' as bullets
    for line in t.splitlines():
        s = line.strip()
        if s.startswith("-"):
            bullets.append(s.lstrip("- ").strip())
    if not bullets:
        bullets = [s.strip() for s in re.split(r"[\n\.;]", t) if s.strip()][:6]
    # First sentence(s) as abstract
    abstract = ". ".join(bullets[:3])
    return {"abstract_md": abstract, "bullets_md": bullets}


def _get_summary_json_grammar() -> Optional[object]:
    """Return a llama.cpp grammar that enforces valid JSON output if available."""
    if LlamaGrammar is None:
        return None
    gbnf = r"""
root   ::= object
value  ::= object | array | string | number | ("true" | "false" | "null") ws

object ::=
  "{" ws (
            string ":" ws value
    ("," ws string ":" ws value)*
  )? "}" ws

array  ::=
  "[" ws (
            value
    ("," ws value)*
  )? "]" ws

string ::=
  "\"" (
    [^"\\] |
    "\\" (["\\/bfnrt] | "u" [0-9a-fA-F] [0-9a-fA-F] [0-9a-fA-F] [0-9a-fA-F]) # escapes
  )* "\"" ws

number ::= ("-"? ([0-9] | [1-9] [0-9]*)) ("." [0-9]+)? ([eE] [-+]? [0-9]+)? ws

# Optional space: applied in this grammar after literal chars when allowed
ws ::= ([ \t\n] ws)?
"""
    try:
        return LlamaGrammar.from_string(gbnf)
    except Exception:
        return None


