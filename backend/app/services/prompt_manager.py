"""Prompt management for improved ASR accuracy through context."""

from __future__ import annotations

import logging
from typing import List, Optional
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger("app.prompt_manager")


class MeetingType(str, Enum):
    """Types of meetings with different vocabulary needs."""
    GENERAL = "general"
    TECHNICAL = "technical"
    MEDICAL = "medical"
    LEGAL = "legal"
    FINANCIAL = "financial"
    EDUCATIONAL = "educational"
    SALES = "sales"


@dataclass
class PromptContext:
    """Context for generating ASR prompts."""
    meeting_type: MeetingType = MeetingType.GENERAL
    company_names: List[str] = None
    technical_terms: List[str] = None
    speaker_names: List[str] = None
    previous_segments: List[str] = None
    custom_vocabulary: List[str] = None


# Domain-specific prompt templates
DOMAIN_PROMPTS = {
    MeetingType.GENERAL: (
        "This is a meeting transcript. "
        "Speakers discuss various topics in a professional setting."
    ),
    MeetingType.TECHNICAL: (
        "This is a technical meeting transcript. "
        "Topics include software development, APIs, databases, cloud services, "
        "debugging, code reviews, architecture, DevOps, CI/CD, and programming languages "
        "like Python, JavaScript, TypeScript, Java, C++, Go, and Rust."
    ),
    MeetingType.MEDICAL: (
        "This is a medical consultation transcript. "
        "Discussion includes patient symptoms, diagnoses, treatments, medications, "
        "procedures, and medical terminology."
    ),
    MeetingType.LEGAL: (
        "This is a legal meeting transcript. "
        "Topics include contracts, litigation, compliance, regulations, "
        "intellectual property, and legal procedures."
    ),
    MeetingType.FINANCIAL: (
        "This is a financial meeting transcript. "
        "Discussion covers investments, budgets, revenue, expenses, "
        "financial planning, accounting, and market analysis."
    ),
    MeetingType.EDUCATIONAL: (
        "This is an educational session transcript. "
        "Content includes lectures, tutorials, explanations, Q&A, "
        "and academic discussions."
    ),
    MeetingType.SALES: (
        "This is a sales meeting transcript. "
        "Topics include product features, pricing, customer needs, "
        "proposals, negotiations, and deal terms."
    ),
}


# Common technical abbreviations and terms that Whisper might misrecognize
TECHNICAL_VOCABULARY = [
    # Programming
    "API", "REST", "GraphQL", "SQL", "NoSQL", "JSON", "XML", "YAML",
    "HTTP", "HTTPS", "WebSocket", "gRPC", "OAuth", "JWT", "CORS",
    "npm", "pip", "Docker", "Kubernetes", "k8s", "CI/CD", "GitOps",
    "React", "Vue", "Angular", "Next.js", "Node.js", "Django", "FastAPI",
    "PostgreSQL", "MySQL", "MongoDB", "Redis", "Elasticsearch",
    "AWS", "Azure", "GCP", "S3", "EC2", "Lambda", "CloudFront",
    "GPU", "CPU", "RAM", "SSD", "CUDA", "TensorFlow", "PyTorch",
    # Common mispronunciations
    "kubectl", "nginx", "regex", "enum", "async", "await", "boolean",
    "nullable", "serializable", "idempotent", "mutex", "semaphore",
]


def generate_initial_prompt(context: PromptContext) -> str:
    """Generate an initial prompt based on context.
    
    The initial prompt helps Whisper understand the domain and
    expected vocabulary, improving accuracy significantly.
    
    Args:
        context: Context information for the meeting
    
    Returns:
        Initial prompt string for Whisper
    """
    # Start with domain-specific base
    prompt_parts = [DOMAIN_PROMPTS[context.meeting_type]]
    
    # Add company names if provided
    if context.company_names:
        names = ", ".join(context.company_names[:5])  # Limit to avoid too long prompt
        prompt_parts.append(f"Companies mentioned: {names}.")
    
    # Add speaker names if known
    if context.speaker_names:
        speakers = ", ".join(context.speaker_names[:5])
        prompt_parts.append(f"Participants: {speakers}.")
    
    # Add technical terms for technical meetings
    if context.meeting_type == MeetingType.TECHNICAL:
        # Include some common technical terms
        tech_terms = TECHNICAL_VOCABULARY[:20]  # Don't overwhelm
        if context.technical_terms:
            tech_terms = context.technical_terms[:10] + tech_terms[:10]
        terms = ", ".join(tech_terms)
        prompt_parts.append(f"Technical terms discussed: {terms}.")
    
    # Add custom vocabulary
    if context.custom_vocabulary:
        custom = ", ".join(context.custom_vocabulary[:15])
        prompt_parts.append(f"Specific terms: {custom}.")
    
    # Add previous context if available (for continued transcription)
    if context.previous_segments:
        # Use last 2-3 segments for context
        recent = " ".join(context.previous_segments[-3:])
        # Truncate if too long
        if len(recent) > 200:
            recent = recent[-200:]
        prompt_parts.append(f"Previous discussion: ...{recent}")
    
    prompt = " ".join(prompt_parts)
    
    # Whisper has a 224 token limit for initial prompt
    # Truncate if necessary (roughly 4 chars per token)
    max_chars = 224 * 4  # ~896 characters
    if len(prompt) > max_chars:
        prompt = prompt[:max_chars-3] + "..."
    
    logger.debug(f"Generated prompt ({len(prompt)} chars): {prompt[:100]}...")
    return prompt


def detect_meeting_type(text: str) -> MeetingType:
    """Auto-detect meeting type from transcript text.
    
    Args:
        text: Sample of transcript text
    
    Returns:
        Detected meeting type
    """
    text_lower = text.lower()
    
    # Check for technical indicators
    technical_keywords = [
        "code", "api", "database", "deploy", "debug", "pull request",
        "function", "variable", "algorithm", "frontend", "backend",
        "server", "client", "framework", "library", "package"
    ]
    technical_score = sum(1 for kw in technical_keywords if kw in text_lower)
    
    # Check for medical indicators
    medical_keywords = [
        "patient", "symptom", "diagnosis", "treatment", "medication",
        "prescription", "surgery", "doctor", "nurse", "hospital"
    ]
    medical_score = sum(1 for kw in medical_keywords if kw in text_lower)
    
    # Check for legal indicators
    legal_keywords = [
        "contract", "agreement", "legal", "litigation", "compliance",
        "regulation", "clause", "liability", "attorney", "court"
    ]
    legal_score = sum(1 for kw in legal_keywords if kw in text_lower)
    
    # Check for financial indicators
    financial_keywords = [
        "revenue", "budget", "investment", "profit", "expense",
        "financial", "accounting", "tax", "audit", "portfolio"
    ]
    financial_score = sum(1 for kw in financial_keywords if kw in text_lower)
    
    # Check for educational indicators
    educational_keywords = [
        "student", "teacher", "lesson", "homework", "exam",
        "course", "curriculum", "assignment", "lecture", "tutorial"
    ]
    educational_score = sum(1 for kw in educational_keywords if kw in text_lower)
    
    # Check for sales indicators
    sales_keywords = [
        "customer", "product", "price", "deal", "proposal",
        "discount", "quota", "lead", "prospect", "closing"
    ]
    sales_score = sum(1 for kw in sales_keywords if kw in text_lower)
    
    # Find highest scoring type
    scores = {
        MeetingType.TECHNICAL: technical_score,
        MeetingType.MEDICAL: medical_score,
        MeetingType.LEGAL: legal_score,
        MeetingType.FINANCIAL: financial_score,
        MeetingType.EDUCATIONAL: educational_score,
        MeetingType.SALES: sales_score,
    }
    
    max_score = max(scores.values())
    if max_score >= 3:  # Threshold for detection
        for meeting_type, score in scores.items():
            if score == max_score:
                logger.info(f"Auto-detected meeting type: {meeting_type} (score: {score})")
                return meeting_type
    
    return MeetingType.GENERAL


def create_contextual_config(
    base_config: "ASRConfig",
    context: Optional[PromptContext] = None,
) -> "ASRConfig":
    """Return base_config with initial_prompt set from context (no other changes)."""
    if context:
        base_config.initial_prompt = generate_initial_prompt(context)
    return base_config
