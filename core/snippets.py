"""Generate copy-ready .env blocks and provider-native code snippets."""

from __future__ import annotations

import json
import re
from textwrap import dedent
from typing import Any

from .utils import sanitize_env_prefix

CAPABILITY_LABELS = {
    "chat": "文本对话",
    "vision": "视觉理解",
    "embedding": "向量 Embedding",
    "rerank": "重排 Rerank",
    "image": "图像生成",
    "audio": "语音",
}

CAPABILITY_SUFFIX = {
    "chat": "MODEL",
    "vision": "VISION_MODEL",
    "embedding": "EMBEDDING_MODEL",
    "rerank": "RERANK_MODEL",
    "image": "IMAGE_MODEL",
    "audio": "AUDIO_MODEL",
}

SUPPORTED_FORMATS: dict[str, set[str]] = {
    "openai_chat": {"env", "python", "curl", "js"},
    "openai_embedding": {"env", "python", "curl", "js"},
    "openai_image": {"env", "python", "curl", "js"},
    "dashscope_multimodal": {"env", "python"},
    "dashscope_embedding": {"env", "python"},
    "dashscope_rerank": {"env", "python"},
    "dashscope_image": {"env", "python"},
    "anthropic_messages": {"env", "python", "curl", "js"},
    "gemini_generate": {"env", "python", "curl", "js"},
    "gemini_embedding": {"env", "python", "curl", "js"},
    "zhipu_rerank": {"env", "python", "curl", "js"},
    # Fetched models whose call shape is not known yet are still recorded,
    # but only the .env block is offered until the user picks a style.
    "unsupported": {"env"},
}

FORMAT_LABELS = {
    "env": ".env",
    "python": "Python",
    "curl": "cURL",
    "js": "JavaScript",
}

_NEEDS_BASE = {
    "openai_chat",
    "openai_embedding",
    "openai_image",
    "anthropic_messages",
    "gemini_generate",
    "gemini_embedding",
    "zhipu_rerank",
}


class SnippetError(ValueError):
    pass


def supported_formats(style: str) -> list[str]:
    order = ["env", "python", "curl", "js"]
    allowed = SUPPORTED_FORMATS.get(style, {"env", "python"})
    return [item for item in order if item in allowed]


def _safe_prefix(key: dict[str, Any], provider: dict[str, Any]) -> str:
    return sanitize_env_prefix(
        key.get("env_prefix", ""), fallback=provider.get("env_prefix", "API")
    )


def _base_url(provider: dict[str, Any], model: dict[str, Any]) -> str:
    return (model.get("base_url") or provider.get("default_base_url") or "").rstrip("/")


def _secret_value(
    key: dict[str, Any], include_secret: bool, placeholder: str = "<YOUR_API_KEY>"
) -> str:
    if include_secret:
        secret = key.get("secret", "")
        if not secret:
            raise SnippetError("无法读取这个 Key，请重新输入后再生成。")
        return secret
    return key.get("hint") or placeholder


def _py_key_expr(prefix: str, key: dict[str, Any], include_secret: bool, direct_key: bool) -> str:
    if direct_key:
        if include_secret and key.get("secret"):
            return json.dumps(key["secret"], ensure_ascii=False)
        return json.dumps("<YOUR_API_KEY>")
    return f"os.environ['{prefix}_API_KEY']"


def _js_key_expr(prefix: str, key: dict[str, Any], include_secret: bool, direct_key: bool) -> str:
    if direct_key:
        if include_secret and key.get("secret"):
            return json.dumps(key["secret"], ensure_ascii=False)
        return json.dumps("<YOUR_API_KEY>")
    return f"process.env.{prefix}_API_KEY"


def _curl_key_expr(prefix: str, key: dict[str, Any], include_secret: bool, direct_key: bool) -> str:
    if direct_key:
        return _secret_value(key, include_secret)
    return f"${prefix}_API_KEY"


def _python_messages(capability: str) -> str:
    # Keep this on one line: it is inserted into a dedented template and a
    # multi-line value would defeat textwrap.dedent().
    if capability == "vision":
        return (
            '[{"role": "user", "content": ['
            '{"type": "text", "text": "描述这张图片。"}, '
            '{"type": "image_url", "image_url": '
            '{"url": "https://example.com/image.jpg"}}]}]'
        )
    return '[{"role": "user", "content": "你好，简单介绍一下你自己。"}]'


def _dashscope_messages(capability: str) -> str:
    if capability == "vision":
        return (
            '[{"role": "user", "content": ['
            '{"image": "https://example.com/image.jpg"}, '
            '{"text": "描述这张图片。"}]}]'
        )
    return (
        '[{"role": "user", "content": '
        '[{"text": "你好，简单介绍一下你自己。"}]}]'
    )


def _anthropic_messages(capability: str) -> str:
    if capability == "vision":
        return (
            '[{"role": "user", "content": ['
            '{"type": "text", "text": "描述这张图片。"}, '
            '{"type": "image", "source": {"type": "url", '
            '"url": "https://example.com/image.jpg"}}]}]'
        )
    return '[{"role": "user", "content": "你好，简单介绍一下你自己。"}]'


def _indent_header(header: str, spaces: int = 12) -> str:
    """Indent continuation lines so textwrap.dedent() sees one common indent."""
    if not header:
        return ""
    lines = header.rstrip("\n").splitlines()
    if len(lines) == 1:
        return lines[0] + "\n"
    pad = " " * spaces
    return lines[0] + "\n" + "\n".join(pad + line for line in lines[1:]) + "\n"


def generate_snippet(
    provider: dict[str, Any],
    key: dict[str, Any],
    models: list[dict[str, Any]],
    fmt: str,
    include_secret: bool = False,
    direct_key: bool = False,
    include_comments: bool = False,
) -> str:
    if not models:
        raise SnippetError("请至少选择一个模型。")
    if fmt not in FORMAT_LABELS:
        raise SnippetError(f"不支持的输出格式：{fmt}")

    if fmt == "env":
        return _env_block(provider, key, models, include_secret, include_comments)

    parts: list[str] = []
    for model in models:
        style = model.get("api_style", "openai_chat")
        if fmt not in SUPPORTED_FORMATS.get(style, {"env", "python"}):
            raise SnippetError(
                f"{model.get('display_name') or model.get('model_id')} 暂不支持 {FORMAT_LABELS[fmt]} 模板。"
            )
        parts.append(
            _code_block(
                provider,
                key,
                model,
                fmt,
                include_secret=include_secret,
                direct_key=direct_key,
                include_comments=include_comments,
            )
        )
    return "\n\n".join(part for part in parts if part.strip())


def _env_block(
    provider: dict[str, Any],
    key: dict[str, Any],
    models: list[dict[str, Any]],
    include_secret: bool,
    include_comments: bool,
) -> str:
    prefix = _safe_prefix(key, provider)
    secret = _secret_value(key, include_secret)
    lines: list[str] = []
    if include_comments:
        lines.append(f"# {provider.get('name', 'API')} · {len(models)} 个调用能力")
        lines.append(f"# 生成时间：{key.get('_now', '')}".rstrip())

    base_models = [m for m in models if m.get("api_style") in _NEEDS_BASE]
    bases: list[str] = []
    for model in base_models:
        base = _base_url(provider, model)
        if base and base not in bases:
            bases.append(base)

    if len(bases) == 1:
        lines.append(f"{prefix}_API_BASE={bases[0]}")
    elif len(bases) > 1:
        for index, model in enumerate(base_models):
            base = _base_url(provider, model)
            suffix = CAPABILITY_SUFFIX.get(model.get("capability", "chat"), "MODEL")
            var = f"{prefix}_{suffix}_BASE" if index else f"{prefix}_API_BASE"
            lines.append(f"{var}={base}")

    lines.append(f"{prefix}_API_KEY={secret}")

    emitted: set[str] = set()
    for model in models:
        capability = model.get("capability", "chat")
        suffix = CAPABILITY_SUFFIX.get(capability, "MODEL")
        var = f"{prefix}_{suffix}"
        counter = 1
        while var in emitted:
            counter += 1
            var = f"{prefix}_{suffix}_{counter}"
        emitted.add(var)
        if include_comments:
            label = CAPABILITY_LABELS.get(capability, capability)
            lines.append(f"# {label} · {model.get('display_name') or model.get('model_id')}")
        lines.append(f"{var}={model.get('model_id', '')}")

    return "\n".join(lines)


def _code_block(
    provider: dict[str, Any],
    key: dict[str, Any],
    model: dict[str, Any],
    fmt: str,
    *,
    include_secret: bool,
    direct_key: bool,
    include_comments: bool,
) -> str:
    style = model.get("api_style", "openai_chat")
    prefix = _safe_prefix(key, provider)
    base = _base_url(provider, model)
    model_id = model.get("model_id", "")
    capability = model.get("capability", "chat")

    if fmt == "python":
        return _python_block(
            provider,
            key,
            model,
            style,
            capability,
            base,
            model_id,
            prefix,
            include_secret,
            direct_key,
            include_comments,
        )
    if fmt == "curl":
        return _curl_block(
            provider,
            key,
            model,
            style,
            capability,
            base,
            model_id,
            prefix,
            include_secret,
            direct_key,
            include_comments,
        )
    if fmt == "js":
        return _js_block(
            provider,
            key,
            model,
            style,
            capability,
            base,
            model_id,
            prefix,
            include_secret,
            direct_key,
            include_comments,
        )
    raise SnippetError(f"不支持的输出格式：{fmt}")


def _python_block(
    provider: dict[str, Any],
    key: dict[str, Any],
    model: dict[str, Any],
    style: str,
    capability: str,
    base: str,
    model_id: str,
    prefix: str,
    include_secret: bool,
    direct_key: bool,
    include_comments: bool,
) -> str:
    key_expr = _py_key_expr(prefix, key, include_secret, direct_key)
    model_literal = json.dumps(model_id, ensure_ascii=False)
    base_literal = json.dumps(base, ensure_ascii=False)
    header = ""
    if include_comments:
        header = (
            f"# {provider.get('name', 'API')} · "
            f"{model.get('display_name') or model_id} ({model_id})\n"
            f"# pip install openai\n"
        )
    header = _indent_header(header)

    if style == "openai_chat":
        messages = _python_messages(capability)
        return dedent(
            f"""\
            {header}
            import os
            from openai import OpenAI

            client = OpenAI(
                api_key={key_expr},
                base_url={base_literal},
            )

            response = client.chat.completions.create(
                model={model_literal},
                messages={messages},
            )

            print(response.choices[0].message.content)
            """
        ).strip()

    if style == "openai_embedding":
        return dedent(
            f"""\
            {header}
            import os
            from openai import OpenAI

            client = OpenAI(
                api_key={key_expr},
                base_url={base_literal},
            )

            response = client.embeddings.create(
                model={model_literal},
                input=["第一段文本", "第二段文本"],
            )

            print(response.data[0].embedding[:8])
            """
        ).strip()

    if style == "openai_image":
        return dedent(
            f"""\
            {header}
            import os
            from openai import OpenAI

            client = OpenAI(
                api_key={key_expr},
                base_url={base_literal},
            )

            response = client.images.generate(
                model={model_literal},
                prompt="一只在窗台上晒太阳的橘猫，水彩风格",
                size="1024x1024",
            )

            image = response.data[0]
            print(image.url or image.b64_json)
            """
        ).strip()

    if style == "dashscope_multimodal":
        messages = _dashscope_messages(capability)
        return dedent(
            f"""\
            {header.replace('# pip install openai', '# pip install dashscope')}
            import os
            import dashscope
            from dashscope import MultiModalConversation

            dashscope.api_key = {key_expr}

            messages = {messages}

            response = MultiModalConversation.call(
                model={model_literal},
                messages=messages,
            )

            print(response.output.choices[0].message.content)
            """
        ).strip()

    if style == "dashscope_embedding":
        return dedent(
            f"""\
            {header.replace('# pip install openai', '# pip install dashscope')}
            import os
            from dashscope import TextEmbedding

            response = TextEmbedding.call(
                model={model_literal},
                input=["第一段文本", "第二段文本"],
            )

            print(response.output["embeddings"][0]["embedding"][:8])
            """
        ).strip()

    if style == "dashscope_rerank":
        return dedent(
            f"""\
            {header.replace('# pip install openai', '# pip install dashscope')}
            import os
            from dashscope import TextReRank

            response = TextReRank.call(
                model={model_literal},
                query="如何申请退款？",
                documents=[
                    "退款需要在订单页提交申请。",
                    "今天天气不错。",
                ],
                top_n=2,
            )

            print(response.output)
            """
        ).strip()

    if style == "dashscope_image":
        return dedent(
            f"""\
            {header.replace('# pip install openai', '# pip install dashscope')}
            import os
            from dashscope import ImageSynthesis

            response = ImageSynthesis.call(
                model={model_literal},
                prompt="一只在窗台上晒太阳的橘猫，水彩风格",
                n=1,
                size="1024*1024",
            )

            print(response.output)
            """
        ).strip()

    if style == "anthropic_messages":
        messages = _anthropic_messages(capability)
        return dedent(
            f"""\
            {header.replace('# pip install openai', '# pip install anthropic')}
            import os
            from anthropic import Anthropic

            client = Anthropic(api_key={key_expr})

            message = client.messages.create(
                model={model_literal},
                max_tokens=1024,
                messages={messages},
            )

            print(message.content[0].text)
            """
        ).strip()

    if style == "gemini_generate":
        if capability == "vision":
            contents = (
                '[types.Part.from_text(text="描述这张图片。"), '
                'types.Part.from_bytes(data=open("image.jpg", "rb").read(), '
                'mime_type="image/jpeg")]'
            )
            extra_import = "from google.genai import types\n"
        else:
            contents = '"你好，简单介绍一下你自己。"'
            extra_import = ""
        return dedent(
            f"""\
            {header.replace('# pip install openai', '# pip install google-genai')}
            import os
            from google import genai
            {extra_import}
            client = genai.Client(api_key={key_expr})

            response = client.models.generate_content(
                model={model_literal},
                contents={contents},
            )

            print(response.text)
            """
        ).strip()

    if style == "gemini_embedding":
        return dedent(
            f"""\
            {header.replace('# pip install openai', '# pip install google-genai')}
            import os
            from google import genai

            client = genai.Client(api_key={key_expr})

            response = client.models.embed_content(
                model={model_literal},
                contents=["第一段文本", "第二段文本"],
            )

            print(response.embeddings[0].values[:8])
            """
        ).strip()

    if style == "zhipu_rerank":
        return dedent(
            f"""\
            {header.replace('# pip install openai', '# pip install requests')}
            import os
            import requests

            response = requests.post(
                {json.dumps(base + "/rerank", ensure_ascii=False)},
                headers={{"Authorization": "Bearer " + {key_expr}}},
                json={{
                    "model": {model_literal},
                    "query": "如何申请退款？",
                    "documents": ["退款需要在订单页申请。", "今天天气不错。"],
                }},
                timeout=30,
            )
            response.raise_for_status()
            print(response.json())
            """
        ).strip()

    raise SnippetError(f"{model_id} 暂不支持 Python 模板。")


def _curl_block(
    provider: dict[str, Any],
    key: dict[str, Any],
    model: dict[str, Any],
    style: str,
    capability: str,
    base: str,
    model_id: str,
    prefix: str,
    include_secret: bool,
    direct_key: bool,
    include_comments: bool,
) -> str:
    key_expr = _curl_key_expr(prefix, key, include_secret, direct_key)
    model_literal = json.dumps(model_id, ensure_ascii=False)
    header = ""
    if include_comments:
        header = f"# {provider.get('name', 'API')} · {model.get('display_name') or model_id}\n"

    if style == "openai_chat":
        url = f"{base}/chat/completions"
        messages = (
            '[{"role":"user","content":[{"type":"text","text":"描述这张图片。"},'
            '{"type":"image_url","image_url":{"url":"https://example.com/image.jpg"}}]}]'
            if capability == "vision"
            else '[{"role":"user","content":"你好，简单介绍一下你自己。"}]'
        )
        return (
            f'{header}curl "{url}" \\\n'
            f'  -H "Content-Type: application/json" \\\n'
            f'  -H "Authorization: Bearer {key_expr}" \\\n'
            f"  -d '{{\n"
            f'    "model": {model_literal},\n'
            f'    "messages": {messages}\n'
            f"  }}'"
        )

    if style == "openai_embedding":
        url = f"{base}/embeddings"
        return (
            f'{header}curl "{url}" \\\n'
            f'  -H "Content-Type: application/json" \\\n'
            f'  -H "Authorization: Bearer {key_expr}" \\\n'
            f"  -d '{{\"model\": {model_literal}, \"input\": [\"第一段文本\", \"第二段文本\"]}}'"
        )

    if style == "openai_image":
        url = f"{base}/images/generations"
        return (
            f'{header}curl "{url}" \\\n'
            f'  -H "Content-Type: application/json" \\\n'
            f'  -H "Authorization: Bearer {key_expr}" \\\n'
            f"  -d '{{\"model\": {model_literal}, "
            f"\"prompt\": \"一只在窗台上晒太阳的橘猫，水彩风格\", \"size\": \"1024x1024\"}}'"
        )

    if style == "anthropic_messages":
        url = f"{base}/v1/messages"
        content = (
            '[{"type":"text","text":"描述这张图片。"},'
            '{"type":"image","source":{"type":"url","url":"https://example.com/image.jpg"}}]'
            if capability == "vision"
            else '"你好，简单介绍一下你自己。"'
        )
        return (
            f'{header}curl "{url}" \\\n'
            f'  -H "x-api-key: {key_expr}" \\\n'
            f'  -H "anthropic-version: 2023-06-01" \\\n'
            f'  -H "content-type: application/json" \\\n'
            f'  -d \'{{\n'
            f'    "model": {model_literal},\n'
            f'    "max_tokens": 1024,\n'
            f'    "messages": [{{"role": "user", "content": {content}}}]\n'
            f"  }}'"
        )

    if style == "gemini_generate":
        url = f"{base}/v1beta/models/{model_id}:generateContent"
        parts = (
            '[{"text":"描述这张图片。"},{"inline_data":{"mime_type":"image/jpeg","data":"<BASE64>"}}]'
            if capability == "vision"
            else '[{"text":"你好，简单介绍一下你自己。"}]'
        )
        return (
            f'{header}curl "{url}?key={key_expr}" \\\n'
            f'  -H "Content-Type: application/json" \\\n'
            f"  -d '{{\"contents\": [{{\"parts\": {parts}}}]}}'"
        )

    if style == "gemini_embedding":
        url = f"{base}/v1beta/models/{model_id}:embedContent"
        return (
            f'{header}curl "{url}?key={key_expr}" \\\n'
            f'  -H "Content-Type: application/json" \\\n'
            f"  -d '{{\"content\": {{\"parts\": [{{\"text\": \"第一段文本\"}}]}}}}'"
        )

    if style == "zhipu_rerank":
        url = f"{base}/rerank"
        return (
            f'{header}curl "{url}" \\\n'
            f'  -H "Authorization: Bearer {key_expr}" \\\n'
            f'  -H "Content-Type: application/json" \\\n'
            f"  -d '{{"
            f"\"model\": {model_literal}, "
            f"\"query\": \"如何申请退款？\", "
            f"\"documents\": [\"退款需要在订单页申请。\", \"今天天气不错。\"]"
            f"}}'"
        )

    raise SnippetError(f"{model_id} 暂不支持 cURL 模板。")


def _js_block(
    provider: dict[str, Any],
    key: dict[str, Any],
    model: dict[str, Any],
    style: str,
    capability: str,
    base: str,
    model_id: str,
    prefix: str,
    include_secret: bool,
    direct_key: bool,
    include_comments: bool,
) -> str:
    key_expr = _js_key_expr(prefix, key, include_secret, direct_key)
    model_literal = json.dumps(model_id, ensure_ascii=False)
    header = ""
    if include_comments:
        header = (
            f"// {provider.get('name', 'API')} · {model.get('display_name') or model_id}\n"
            f"// Node.js 18+\n"
        )
    header = _indent_header(header)

    if style == "openai_chat":
        url = f"{base}/chat/completions"
        messages = (
            '[{"role":"user","content":[{"type":"text","text":"描述这张图片。"},'
            '{"type":"image_url","image_url":{"url":"https://example.com/image.jpg"}}]}]'
            if capability == "vision"
            else '[{"role":"user","content":"你好，简单介绍一下你自己。"}]'
        )
        return dedent(
            f"""\
            {header}
            const response = await fetch({json.dumps(url)}, {{
              method: "POST",
              headers: {{
                "Content-Type": "application/json",
                "Authorization": `Bearer ${{ {key_expr} }}`,
              }},
              body: JSON.stringify({{
                model: {model_literal},
                messages: {messages},
              }}),
            }});

            const data = await response.json();
            console.log(data.choices[0].message.content);
            """
        ).strip()

    if style == "openai_embedding":
        url = f"{base}/embeddings"
        return dedent(
            f"""\
            {header}
            const response = await fetch({json.dumps(url)}, {{
              method: "POST",
              headers: {{
                "Content-Type": "application/json",
                "Authorization": `Bearer ${{ {key_expr} }}`,
              }},
              body: JSON.stringify({{
                model: {model_literal},
                input: ["第一段文本", "第二段文本"],
              }}),
            }});

            const data = await response.json();
            console.log(data.data[0].embedding.slice(0, 8));
            """
        ).strip()

    if style == "openai_image":
        url = f"{base}/images/generations"
        return dedent(
            f"""\
            {header}
            const response = await fetch({json.dumps(url)}, {{
              method: "POST",
              headers: {{
                "Content-Type": "application/json",
                "Authorization": `Bearer ${{ {key_expr} }}`,
              }},
              body: JSON.stringify({{
                model: {model_literal},
                prompt: "一只在窗台上晒太阳的橘猫，水彩风格",
                size: "1024x1024",
              }}),
            }});

            const data = await response.json();
            console.log(data.data[0].url || data.data[0].b64_json);
            """
        ).strip()

    if style == "anthropic_messages":
        url = f"{base}/v1/messages"
        content = (
            '[{"type":"text","text":"描述这张图片。"},'
            '{"type":"image","source":{"type":"url","url":"https://example.com/image.jpg"}}]'
            if capability == "vision"
            else '"你好，简单介绍一下你自己。"'
        )
        return dedent(
            f"""\
            {header}
            const response = await fetch({json.dumps(url)}, {{
              method: "POST",
              headers: {{
                "Content-Type": "application/json",
                "x-api-key": {key_expr},
                "anthropic-version": "2023-06-01",
              }},
              body: JSON.stringify({{
                model: {model_literal},
                max_tokens: 1024,
                messages: [{{ role: "user", content: {content} }}],
              }}),
            }});

            const data = await response.json();
            console.log(data.content[0].text);
            """
        ).strip()

    if style == "gemini_generate":
        url = f"{base}/v1beta/models/{model_id}:generateContent"
        parts = (
            '[{"text":"描述这张图片。"},{"inline_data":{"mime_type":"image/jpeg","data":"<BASE64>"}}]'
            if capability == "vision"
            else '[{"text":"你好，简单介绍一下你自己。"}]'
        )
        return dedent(
            f"""\
            {header}
            const response = await fetch(
              {json.dumps(url)} + "?key=" + encodeURIComponent({key_expr}),
              {{
                method: "POST",
                headers: {{ "Content-Type": "application/json" }},
                body: JSON.stringify({{
                  contents: [{{ parts: {parts} }}],
                }}),
              }},
            );

            const data = await response.json();
            console.log(data.candidates[0].content.parts[0].text);
            """
        ).strip()

    if style == "gemini_embedding":
        url = f"{base}/v1beta/models/{model_id}:embedContent"
        return dedent(
            f"""\
            {header}
            const response = await fetch(
              {json.dumps(url)} + "?key=" + encodeURIComponent({key_expr}),
              {{
                method: "POST",
                headers: {{ "Content-Type": "application/json" }},
                body: JSON.stringify({{
                  content: {{ parts: [{{ text: "第一段文本" }}] }},
                }}),
              }},
            );

            const data = await response.json();
            console.log(data.embedding.values.slice(0, 8));
            """
        ).strip()

    if style == "zhipu_rerank":
        url = f"{base}/rerank"
        return dedent(
            f"""\
            {header}
            const response = await fetch({json.dumps(url)}, {{
              method: "POST",
              headers: {{
                "Content-Type": "application/json",
                "Authorization": `Bearer ${{ {key_expr} }}`,
              }},
              body: JSON.stringify({{
                model: {model_literal},
                query: "如何申请退款？",
                documents: ["退款需要在订单页申请。", "今天天气不错。"],
              }}),
            }});

            const data = await response.json();
            console.log(data);
            """
        ).strip()

    raise SnippetError(f"{model_id} 暂不支持 JavaScript 模板。")
