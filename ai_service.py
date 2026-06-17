# -*- coding: utf-8 -*-
from __future__ import annotations

import json
import re
from typing import Any, Dict, Sequence, Tuple

PROMPT = r'''
你是大學靜力學與材料力學教師，也是幾何資料擷取器。請讀取使用者上傳的所有照片。
照片可能包含題目文字與另一張共用圖形，也可能一張圖同時對應兩個題號。

目標：把每個題目轉成可由本地公式引擎精確解題的 JSON。
只能輸出合法 JSON，不要 Markdown，不要額外文字。不可猜測模糊尺寸；模糊時填 null 並在 warnings 說明。
題目要求哪個軸，就保留哪個軸，不能固定改成形心軸。

支援四類：

A. composite：組合面積、梁截面、孔洞。
元件格式：
- rectangle: {"kind":"rectangle","name":"...","sign":1,"b":寬,"h":高,"x":形心x,"y":形心y,"angle":0}
- circle: {"kind":"circle","name":"...","sign":-1,"r":半徑,"x":圓心x,"y":圓心y}
- ellipse: {"kind":"ellipse","name":"...","sign":1,"a":x半軸,"b":y半軸,"x":形心x,"y":形心y,"angle":0}
- polygon: {"kind":"polygon","name":"...","sign":1,"vertices":[[x1,y1],[x2,y2],...]}
- circular_sector: {"kind":"circular_sector","name":"...","sign":1,"center_x":0,"center_y":0,"r_inner":0,"r_outer":100,"theta1":-30,"theta2":30,"angle_unit":"deg"}
元件不可重疊；孔洞 sign=-1。T 型、U 型、工字型與複雜梁拆成不重疊矩形。斜邊梯形可用 polygon，圓孔用負 circle。
axis_x 是指定垂直 y 軸的 x 座標；axis_y 是指定水平 x 軸的 y 座標。

B. cartesian：曲線陰影直角座標積分。
垂直條帶：mode="cartesian", orientation="vertical", lower_bound/upper_bound 是 x 範圍，lower_function/upper_function 是 y(x)。
水平條帶：orientation="horizontal", lower_bound/upper_bound 是 y 範圍，left_function/right_function 是 x(y)。
運算式只能用 + - * / ^、sqrt、sin、cos、tan、pi 和變數。
例：y^2=1-x 且左側為 y 軸，使用 horizontal：y=-1 到 1，left_function="0"，right_function="1-y^2"。
例：y^2=(b^2/a)x，依陰影完整邊界建立函數；圖不完整時 can_solve=false。

C. polar：扇形、圓弧、環形扇形。
格式：theta_min, theta_max, r_inner, r_outer。符號 alpha 預設弧度；度數請寫成如 -30*pi/180。
半徑 r0、總角度 alpha 的扇形使用 theta_min="-alpha/2", theta_max="alpha/2", r_inner="0", r_outer="r0"。

D. unsupported：照片不完整、三維質量慣性矩、扭轉常數或無法精確表示。

每個題目分開列出。若同圖寫 10-10 求 Ix、10-11 求 Iy，建立兩筆 problem，geometry 可相同。
必須涵蓋：
- y²=1−x 曲線陰影，分別求 x/y 軸。
- y²=(b²/a)x 曲線陰影。
- 半徑 r0、夾角 alpha 的扇形。
- 三角形或梯形＋矩形＋圓孔。
- T 型梁、U 型梁、多矩形梁，求形心 x' 軸與 y 軸。
- 原始軸、形心軸、Ixy、J、kx、ky。

輸出：
{
  "recognized_text":"所有可辨識文字",
  "problems":[
    {
      "problem_id":"10-10",
      "title":"陰影面積對 x 軸的慣性矩",
      "recognized_text":"該題文字",
      "mode":"composite | cartesian | polar | unsupported",
      "unit":"mm | m | cm | in | symbolic",
      "requested":["centroid","Ix_origin","Iy_origin","Ix_centroid","Iy_centroid","Ixy","J","kx","ky"],
      "target_axes_description":"題圖上的 x 軸、y 軸或形心 x' 軸",
      "axis_x":"0",
      "axis_y":"0",
      "variables":{"a":null,"b":null,"r0":null,"alpha":null},
      "angle_variables_degrees":[],
      "can_solve":true,
      "confidence":0.95,
      "reasoning_summary":"如何辨識區域與選擇解法",
      "warnings":[],
      "components":[],
      "orientation":"horizontal",
      "lower_bound":"-1",
      "upper_bound":"1",
      "left_function":"0",
      "right_function":"1-y^2",
      "lower_function":null,
      "upper_function":null,
      "theta_min":null,
      "theta_max":null,
      "r_inner":null,
      "r_outer":null
    }
  ]
}

所有 problem 保留完整欄位，不適用可填 null 或空陣列。confidence 介於 0 到 1。不可輸出 AI 自己算的最終 Ix/Iy。
'''


def _extract_json(text: str) -> Dict[str, Any]:
    cleaned=text.strip(); cleaned=re.sub(r"^```(?:json)?\s*","",cleaned,flags=re.I); cleaned=re.sub(r"\s*```$","",cleaned)
    try: return json.loads(cleaned)
    except json.JSONDecodeError:
        a,b=cleaned.find("{"),cleaned.rfind("}")
        if a>=0 and b>a: return json.loads(cleaned[a:b+1])
        raise ValueError("AI 回傳內容不是合法 JSON。")


def _normalize(data: Dict[str, Any]) -> Dict[str, Any]:
    result={"recognized_text":str((data or {}).get("recognized_text") or ""),"problems":[]}
    for i,raw in enumerate((data or {}).get("problems") or [],1):
        p={
            "problem_id":str(raw.get("problem_id") or f"題目 {i}"),"title":str(raw.get("title") or ""),"recognized_text":str(raw.get("recognized_text") or ""),
            "mode":str(raw.get("mode") or "unsupported").lower(),"unit":str(raw.get("unit") or "symbolic"),"requested":raw.get("requested") or [],
            "target_axes_description":str(raw.get("target_axes_description") or ""),"axis_x":"0" if raw.get("axis_x") is None else str(raw.get("axis_x")),"axis_y":"0" if raw.get("axis_y") is None else str(raw.get("axis_y")),
            "variables":raw.get("variables") or {},"angle_variables_degrees":raw.get("angle_variables_degrees") or [],"can_solve":bool(raw.get("can_solve",False)),
            "confidence":0.0,"reasoning_summary":str(raw.get("reasoning_summary") or ""),"warnings":raw.get("warnings") or [],"components":raw.get("components") or [],
            "orientation":raw.get("orientation"),"lower_bound":raw.get("lower_bound"),"upper_bound":raw.get("upper_bound"),"left_function":raw.get("left_function"),"right_function":raw.get("right_function"),
            "lower_function":raw.get("lower_function"),"upper_function":raw.get("upper_function"),"theta_min":raw.get("theta_min"),"theta_max":raw.get("theta_max"),"r_inner":raw.get("r_inner"),"r_outer":raw.get("r_outer")}
        try: p["confidence"]=max(0.0,min(1.0,float(raw.get("confidence",0))))
        except Exception: p["confidence"]=0.0
        result["problems"].append(p)
    return result


def analyze_images(images: Sequence[Tuple[bytes,str]], api_key: str, model: str="gemini-3.5-flash") -> Dict[str, Any]:
    if not api_key.strip(): raise ValueError("沒有可用的 Gemini API Key。")
    if not images: raise ValueError("請至少上傳一張圖片。")
    try:
        from google import genai
        from google.genai import types
    except ImportError as exc: raise RuntimeError("伺服器尚未安裝 google-genai。") from exc
    client=genai.Client(api_key=api_key.strip())
    contents=[types.Part.from_bytes(data=b,mime_type=m) for b,m in images]+[PROMPT]
    config=types.GenerateContentConfig(temperature=0.05,response_mime_type="application/json")
    try:
        response=client.models.generate_content(model=model.strip() or "gemini-3.5-flash",contents=contents,config=config)
    except Exception as exc:
        msg=str(exc)
        if "403" in msg or "PERMISSION_DENIED" in msg:
            raise RuntimeError("Gemini 專案或 API Key 被拒絕存取（403）。請換成可正常使用、未外洩的個人 Google AI Studio API Key。") from exc
        raise
    text=getattr(response,"text","")
    if not text: raise RuntimeError("Gemini 沒有回傳結果。")
    return _normalize(_extract_json(text))
