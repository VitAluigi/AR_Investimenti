# =============================================================================
# modules/ai_client.py - Client AI unificato (Claude o Azure, stesso contratto)
# =============================================================================
# Unico punto in cui cambia il provider. mapper.py e word_writer.py
# chiamano sempre chiedi_ai() senza sapere chi risponde sotto.
# =============================================================================

import re
import json
from config import AI_PROVIDER

def chiedi_ai(prompt: str, max_tokens: int = 500) -> str:
    if AI_PROVIDER == "claude":
        return _chiedi_claude(prompt, max_tokens)
    elif AI_PROVIDER == "azure":
        return _chiedi_azure(prompt, max_tokens)
    else:
        return ""


def _chiedi_claude(prompt: str, max_tokens: int) -> str:
    try:
        import anthropic
        from config import CLAUDE_API_KEY, CLAUDE_MODEL
        client = anthropic.Anthropic(api_key=CLAUDE_API_KEY)
        response = client.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=max_tokens,
            messages=[{"role": "user", "content": prompt}]
        )
        return response.content[0].text.strip()
    except Exception as e:
        print(f"[AVVISO] Claude API non disponibile: {e}")
        return ""


def _chiedi_azure(prompt: str, max_tokens: int) -> str:
    try:
        from openai import AzureOpenAI
        from config import (AZURE_OPENAI_ENDPOINT, AZURE_OPENAI_API_KEY,
                            AZURE_OPENAI_VERSION, AZURE_DEPLOYMENT_NAME)
        client = AzureOpenAI(
            azure_endpoint=AZURE_OPENAI_ENDPOINT,
            api_key=AZURE_OPENAI_API_KEY,
            api_version=AZURE_OPENAI_VERSION,
        )
        response = client.chat.completions.create(
            model=AZURE_DEPLOYMENT_NAME,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=max_tokens,
            temperature=0,
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        print(f"[AVVISO] Azure OpenAI non disponibile: {e}")
        return ""
