# -*- coding: utf-8 -*-
from __future__ import annotations

import base64
import json
import re
from typing import Any, Dict


ANALYSIS_PROMPT = r"""
你是一位大學靜力學與材料力學教師。請仔細讀取這張「截面面積慣性矩」題目照片，
辨識題目文字、尺寸標註、座標軸、孔洞、陰影範圍與要求計算的物理量。

你的工作不只是 OCR，而是將題目轉換成可由程式驗算的組合截面資料。
只能輸出一個合法 JSON 物件，不要輸出 Markdown 程式碼框，也不要在 JSON 前後加入說明。

規則：
1. 不可猜測看不清楚的尺寸。看不清楚時使用 null，並在 warnings 說明。
2. 所有尺寸與 x、y 必須使用同一長度單位，unit 填 mm、cm、m 或 in。
3. 若題目沒有指定座標原點，建立方便計算的全域座標：
   x=0 設在整個截面的最左側；y=0 設在整個截面的最下側；
   x 向右為正，y 向上為正。
4. components 中的 x、y 必須是「該子截面自身形心」的全域座標，不是左下角。
5. 優先將組合截面拆成不重疊的矩形與圓形。孔洞 sign=-1，實體 sign=1。
6. 支援的 shape 只能是：
   矩形、圓形、I 型鋼、T 型截面、中空矩形、中空圓管。
7. 尺寸欄位：
   矩形 params={"b":寬度,"h":高度}
   圓形 params={"d":直徑}
   I 型鋼 params={"B":翼板寬,"H":總高度,"tw":腹板厚,"tf":翼板厚}
   T 型截面 params={"B":翼板寬,"H":總高度,"tw":腹板厚,"tf":翼板厚}
   中空矩形 params={"B":外寬,"H":外高,"b":內寬,"h":內高}
   中空圓管 params={"D":外徑,"d":內徑}
8. 若輪廓無法用上述形狀精確表示，不要硬套。將 can_auto_build=false 並在 warnings 說明。
9. confidence 為 0 到 1。只有必要尺寸和位置都清楚時，can_auto_build 才能是 true。
10. requested_quantities 可包含 centroid、Ix、Iy、kx、ky、other。
11. 若題目要求指定軸而不是整體形心軸，請在 target_axes 與 warnings 說明。
12. recognized_text 忠實抄錄照片文字；不清楚的內容用 [?]，不可自行補寫。
13. problem_summary、decomposition_reason、assumptions、warnings 使用繁體中文。
14. 不要將 AI 自己算出的 Ix、Iy 當標準答案；數值會由本地公式引擎重新計算。

JSON 格式：
{
  "recognized_text": "照片中的題目文字",
  "problem_summary": "題目要求與已知條件摘要",
  "unit": "mm",
  "requested_quantities": ["centroid", "Ix", "Iy"],
  "target_axes": "整體形心 x、y 軸",
  "origin_definition": "x=0 位於...，y=0 位於...",
  "decomposition_reason": "如何拆分截面及原因",
  "can_auto_build": true,
  "confidence": 0.95,
  "components": [
    {
      "name": "上翼板",
      "shape": "矩形",
      "sign": 1,
      "x": 60.0,
      "y": 130.0,
      "angle": 0,
      "params": {"b": 120.0, "h": 20.0},
      "source": "由圖中的尺寸取得"
    }
  ],
  "assumptions": ["假設所有尺寸單位均為 mm"],
  "warnings": []
}
"""


def _extract_json(text: str) -> Dict[str, Any]:
    cleaned = text.strip()
    cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s*```$", "", cleaned)

    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start >= 0 and end > start:
            return json.loads(cleaned[start:end + 1])
        raise ValueError("AI 回傳內容不是合法 JSON。")


def _normalize_result(data: Dict[str, Any]) -> Dict[str, Any]:
    defaults = {
        "recognized_text": "",
        "problem_summary": "",
        "unit": "mm",
        "requested_quantities": [],
        "target_axes": "整體形心 x、y 軸",
        "origin_definition": "",
        "decomposition_reason": "",
        "can_auto_build": False,
        "confidence": 0.0,
        "components": [],
        "assumptions": [],
        "warnings": [],
    }
    result = {**defaults, **(data or {})}
    for key in ("components", "assumptions", "warnings", "requested_quantities"):
        result[key] = result.get(key) or []

    try:
        result["confidence"] = max(0.0, min(1.0, float(result.get("confidence", 0))))
    except (TypeError, ValueError):
        result["confidence"] = 0.0

    if not isinstance(result.get("can_auto_build"), bool):
        result["can_auto_build"] = str(result.get("can_auto_build")).lower() == "true"

    return result


def analyze_with_gemini(
    image_bytes: bytes,
    mime_type: str,
    api_key: str,
    model: str = "gemini-3.5-flash",
) -> Dict[str, Any]:
    try:
        from google import genai
        from google.genai import types
    except ImportError as exc:
        raise RuntimeError("伺服器尚未安裝 google-genai。") from exc

    client = genai.Client(api_key=api_key)
    image_part = types.Part.from_bytes(data=image_bytes, mime_type=mime_type)
    config = types.GenerateContentConfig(
        temperature=0.1,
        response_mime_type="application/json",
    )
    response = client.models.generate_content(
        model=model,
        contents=[image_part, ANALYSIS_PROMPT],
        config=config,
    )
    text = getattr(response, "text", "")
    if not text:
        raise RuntimeError("Gemini 沒有回傳可讀取的結果。")
    return _normalize_result(_extract_json(text))


def analyze_with_openai(
    image_bytes: bytes,
    mime_type: str,
    api_key: str,
    model: str = "gpt-5.5",
) -> Dict[str, Any]:
    try:
        from openai import OpenAI
    except ImportError as exc:
        raise RuntimeError("伺服器尚未安裝 openai。") from exc

    encoded = base64.b64encode(image_bytes).decode("utf-8")
    data_url = f"data:{mime_type};base64,{encoded}"
    client = OpenAI(api_key=api_key)

    response = client.responses.create(
        model=model,
        input=[{
            "role": "user",
            "content": [
                {"type": "input_text", "text": ANALYSIS_PROMPT},
                {"type": "input_image", "image_url": data_url, "detail": "high"},
            ],
        }],
    )
    text = getattr(response, "output_text", "")
    if not text:
        raise RuntimeError("OpenAI 沒有回傳可讀取的結果。")
    return _normalize_result(_extract_json(text))


def analyze_image(
    image_bytes: bytes,
    mime_type: str,
    provider: str,
    api_key: str,
    model: str,
) -> Dict[str, Any]:
    if not api_key.strip():
        raise ValueError("沒有可用的 API Key。")

    provider_lower = provider.strip().lower()
    if provider_lower.startswith("gemini") or provider_lower.startswith("google"):
        return analyze_with_gemini(
            image_bytes, mime_type, api_key.strip(),
            model.strip() or "gemini-3.5-flash",
        )
    if provider_lower.startswith("openai") or provider_lower.startswith("gpt"):
        return analyze_with_openai(
            image_bytes, mime_type, api_key.strip(),
            model.strip() or "gpt-5.5",
        )
    raise ValueError(f"未知 AI 服務：{provider}")
