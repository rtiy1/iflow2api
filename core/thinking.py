

import re
from enum import Enum
from typing import Optional, Dict, Any
from dataclasses import dataclass


class ThinkingMode(Enum):
    """Thinking configuration mode."""
    BUDGET = "budget"  # Numeric token budget
    LEVEL = "level"    # Discrete level (high, medium, low)
    NONE = "none"      # Disabled
    AUTO = "auto"      # Automatic


class ThinkingLevel(Enum):
    """Discrete thinking levels."""
    NONE = "none"
    AUTO = "auto"
    MINIMAL = "minimal"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    XHIGH = "xhigh"


@dataclass
class ThinkingConfig:
    """Unified thinking configuration."""
    mode: ThinkingMode
    budget: int = 0
    level: Optional[ThinkingLevel] = None


@dataclass
class SuffixResult:
    """Result of parsing model name suffix."""
    model_name: str
    has_suffix: bool
    raw_suffix: str = ""


def parse_suffix(model: str) -> SuffixResult:
    """Extract thinking suffix from model name.

    Examples:
        "glm-4.7(8192)" -> model_name="glm-4.7", raw_suffix="8192"
        "glm-4.7(high)" -> model_name="glm-4.7", raw_suffix="high"
        "glm-4.7" -> model_name="glm-4.7", has_suffix=False
    """
    match = re.match(r'^(.+)\(([^)]+)\)$', model)
    if match:
        return SuffixResult(
            model_name=match.group(1),
            has_suffix=True,
            raw_suffix=match.group(2)
        )
    return SuffixResult(model_name=model, has_suffix=False)


def parse_suffix_to_config(raw_suffix: str) -> Optional[ThinkingConfig]:
    """Convert raw suffix to ThinkingConfig.

    Priority:
        1. Special values: "none", "auto", "-1"
        2. Level names: "minimal", "low", "medium", "high", "xhigh"
        3. Numeric values: positive integers
    """
    if not raw_suffix:
        return None

    suffix_lower = raw_suffix.lower().strip()

    # Special values
    if suffix_lower == "none":
        return ThinkingConfig(mode=ThinkingMode.NONE, budget=0)
    if suffix_lower in ("auto", "-1"):
        return ThinkingConfig(mode=ThinkingMode.AUTO, budget=-1)

    # Level names
    try:
        level = ThinkingLevel(suffix_lower)
        return ThinkingConfig(mode=ThinkingMode.LEVEL, level=level)
    except ValueError:
        pass

    # Numeric budget
    try:
        budget = int(raw_suffix)
        if budget == 0:
            return ThinkingConfig(mode=ThinkingMode.NONE, budget=0)
        if budget > 0:
            return ThinkingConfig(mode=ThinkingMode.BUDGET, budget=budget)
    except ValueError:
        pass

    return None


def extract_openai_config(body: Dict[str, Any]) -> Optional[ThinkingConfig]:
    """Extract thinking config from OpenAI format request body.

    OpenAI format: reasoning_effort = "none" | "low" | "medium" | "high"
    """
    effort = body.get("reasoning_effort")
    if not effort:
        return None

    effort_lower = str(effort).lower().strip()

    if effort_lower == "none":
        return ThinkingConfig(mode=ThinkingMode.NONE, budget=0)

    try:
        level = ThinkingLevel(effort_lower)
        return ThinkingConfig(mode=ThinkingMode.LEVEL, level=level)
    except ValueError:
        return None


def extract_iflow_config(body: Dict[str, Any]) -> Optional[ThinkingConfig]:
    """Extract thinking config from iFlow format request body.

    iFlow formats:
        - GLM: chat_template_kwargs.enable_thinking (boolean)
        - MiniMax: reasoning_split (boolean)
    """
    # GLM format
    if "chat_template_kwargs" in body:
        enable_thinking = body["chat_template_kwargs"].get("enable_thinking")
        if enable_thinking is not None:
            if enable_thinking:
                return ThinkingConfig(mode=ThinkingMode.BUDGET, budget=1)
            return ThinkingConfig(mode=ThinkingMode.NONE, budget=0)

    # MiniMax format
    if "reasoning_split" in body:
        reasoning_split = body["reasoning_split"]
        if reasoning_split:
            return ThinkingConfig(mode=ThinkingMode.BUDGET, budget=1)
        return ThinkingConfig(mode=ThinkingMode.NONE, budget=0)

    return None


def config_to_boolean(config: ThinkingConfig) -> bool:
    """Convert ThinkingConfig to boolean for iFlow models.

    Conversion rules:
        - ModeNone: false
        - ModeAuto: true
        - ModeBudget + Budget=0: false
        - ModeBudget + Budget>0: true
        - ModeLevel + Level=none: false
        - ModeLevel + any other level: true
    """
    if config.mode == ThinkingMode.NONE:
        return False
    if config.mode == ThinkingMode.AUTO:
        return True
    if config.mode == ThinkingMode.BUDGET:
        return config.budget > 0
    if config.mode == ThinkingMode.LEVEL:
        return config.level != ThinkingLevel.NONE
    return True


def apply_thinking_to_glm(body: Dict[str, Any], config: ThinkingConfig) -> Dict[str, Any]:
    """Apply thinking configuration for GLM models.

    Output format when enabled:
        {"chat_template_kwargs": {"enable_thinking": true, "clear_thinking": false}}

    Output format when disabled:
        {"chat_template_kwargs": {"enable_thinking": false}}
    """
    enable_thinking = config_to_boolean(config)

    if "chat_template_kwargs" not in body:
        body["chat_template_kwargs"] = {}

    body["chat_template_kwargs"]["enable_thinking"] = enable_thinking

    if enable_thinking:
        body["chat_template_kwargs"]["clear_thinking"] = False

    return body


def apply_thinking_to_minimax(body: Dict[str, Any], config: ThinkingConfig) -> Dict[str, Any]:
    """Apply thinking configuration for MiniMax models.

    Output format:
        {"reasoning_split": true/false}
    """
    body["reasoning_split"] = config_to_boolean(config)
    return body


def is_glm_model(model_id: str) -> bool:
    """Determine if the model is a GLM series model.

    GLM models use chat_template_kwargs.enable_thinking format.
    参考 Go: isGLMModel(modelID string) bool
    """
    return model_id.lower().startswith("glm")


def is_minimax_model(model_id: str) -> bool:
    """Determine if the model is a MiniMax series model.

    MiniMax models use reasoning_split format.
    参考 Go: isMiniMaxModel(modelID string) bool
    """
    return model_id.lower().startswith("minimax")


def preserve_reasoning_content(body: Dict[str, Any], model: str) -> Dict[str, Any]:
    """Preserve reasoning_content in messages for GLM/MiniMax models.

    For GLM-4.6/4.7 and MiniMax M2/M2.1/M2.5, it's recommended to include the full
    assistant response (including reasoning_content) in message history for
    better context continuity in multi-turn conversations.

    This function checks if reasoning_content already exists in assistant messages.
    If present, it means the client has correctly preserved reasoning in history.
    """
    model_lower = model.lower()

    # Only apply to models that support thinking with history preservation
    needs_preservation = (
        model_lower.startswith("glm-4")
        or model_lower.startswith("glm-5")
        or model_lower.startswith("minimax-m2")
    )

    if not needs_preservation:
        return body

    messages = body.get("messages", [])
    if not messages:
        return body

    # Check if any assistant message already has reasoning_content preserved
    has_reasoning_content = any(
        msg.get("role") == "assistant" and msg.get("reasoning_content")
        for msg in messages
    )

    if has_reasoning_content:
        # Reasoning content is already present, properly formatted
        pass

    return body


def strip_thinking_config(body: Dict[str, Any]) -> Dict[str, Any]:
    """Remove thinking configuration fields from request body.

    Used when a model doesn't support thinking but the request contains
    thinking configuration. Silently removes config to prevent upstream errors.
    """
    # iFlow format fields
    if "chat_template_kwargs" in body:
        body["chat_template_kwargs"].pop("enable_thinking", None)
        body["chat_template_kwargs"].pop("clear_thinking", None)
        if not body["chat_template_kwargs"]:
            body.pop("chat_template_kwargs")

    body.pop("reasoning_split", None)
    body.pop("reasoning_effort", None)
    body.pop("thinking", None)

    return body


def apply_thinking(body: Dict[str, Any], model: str) -> Dict[str, Any]:
    """Apply thinking configuration to request body.

    Main entry point for thinking processing. Handles:
        1. Suffix parsing from model name
        2. Config extraction from request body (iFlow format priority)
        3. Suffix priority over body config
        4. Provider-specific application
        5. Reasoning content preservation for multi-turn conversations

    Args:
        body: Request body dict
        model: Model name (may include suffix like "glm-4.7(8192)")

    Returns:
        Modified request body with thinking config applied
    """
    # Parse suffix
    suffix_result = parse_suffix(model)
    base_model = suffix_result.model_name

    # Update model field to base model (without suffix)
    body["model"] = base_model

    # Get config: suffix priority over body, iFlow format priority over OpenAI
    config = None
    if suffix_result.has_suffix:
        config = parse_suffix_to_config(suffix_result.raw_suffix)

    if config is None:
        # Try iFlow format first
        config = extract_iflow_config(body)

    if config is None:
        # Fall back to OpenAI format
        config = extract_openai_config(body)

    if config is None:
        # No thinking config found, just preserve reasoning content if needed
        return preserve_reasoning_content(body, base_model)

    # Remove OpenAI format fields (will be replaced with iFlow format)
    body.pop("reasoning_effort", None)
    body.pop("thinking", None)

    # Apply based on model type
    if is_glm_model(base_model):
        body = apply_thinking_to_glm(body, config)
    elif is_minimax_model(base_model):
        body = apply_thinking_to_minimax(body, config)
    else:
        # For other models, strip thinking config
        body = strip_thinking_config(body)

    # Preserve reasoning content for multi-turn conversations
    body = preserve_reasoning_content(body, base_model)

    return body
