# -*- coding: utf-8 -*-
from __future__ import annotations

import io
import json
import math
from typing import Any, Dict, List, Tuple

import matplotlib.pyplot as plt
from matplotlib.patches import Circle, Polygon
import pandas as pd
from PIL import Image, ImageEnhance, ImageOps
import streamlit as st

from ai_service import analyze_image
from section_engine import (
    SHAPE_PARAMS,
    InertiaCalculator,
    SectionComponent,
    build_teaching_text,
    format_number,
)


st.set_page_config(
    page_title="AI 截面慣性矩教學系統",
    page_icon="📐",
    layout="wide",
    initial_sidebar_state="expanded",
)


COLUMN_ORDER = [
    "編號", "名稱", "形狀", "性質", "x", "y", "θ",
    "b", "h", "B", "H", "tw", "tf", "d", "D",
]

DEFAULT_ROWS = [
    {
        "編號": 1, "名稱": "矩形 1", "形狀": "矩形", "性質": "實體",
        "x": 50.0, "y": 25.0, "θ": 0.0,
        "b": 100.0, "h": 50.0,
        "B": None, "H": None, "tw": None, "tf": None, "d": None, "D": None,
    }
]


def init_state() -> None:
    defaults = {
        "ai_result": None,
        "component_df": pd.DataFrame(DEFAULT_ROWS, columns=COLUMN_ORDER),
        "calculation": None,
        "analysis_count": 0,
        "processed_image": None,
        "processed_mime": "image/jpeg",
        "image_rotation": 0,
        "enhance_image": False,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def read_secret(name: str, default: Any = None) -> Any:
    try:
        return st.secrets.get(name, default)
    except Exception:
        return default


def require_password() -> None:
    password = str(read_secret("APP_PASSWORD", "") or "")
    if not password:
        return

    if st.session_state.get("authenticated"):
        return

    st.title("🔒 AI 截面慣性矩教學系統")
    entered = st.text_input("請輸入使用密碼", type="password")
    if st.button("進入系統", type="primary", use_container_width=True):
        if entered == password:
            st.session_state.authenticated = True
            st.rerun()
        else:
            st.error("密碼錯誤。")
    st.stop()


def prepare_image(uploaded_file) -> Tuple[bytes, str, Image.Image]:
    image = Image.open(uploaded_file)
    image = ImageOps.exif_transpose(image).convert("RGB")

    rotation = int(st.session_state.image_rotation) % 360
    if rotation:
        image = image.rotate(rotation, expand=True)

    if st.session_state.enhance_image:
        image = ImageOps.autocontrast(image)
        image = ImageEnhance.Contrast(image).enhance(1.2)
        image = ImageEnhance.Sharpness(image).enhance(1.35)

    max_side = 2200
    if max(image.size) > max_side:
        image.thumbnail((max_side, max_side), Image.Resampling.LANCZOS)

    output = io.BytesIO()
    image.save(output, format="JPEG", quality=92, optimize=True)
    return output.getvalue(), "image/jpeg", image


def ai_components_to_dataframe(result: Dict[str, Any]) -> pd.DataFrame:
    rows = []
    for index, item in enumerate(result.get("components") or [], start=1):
        params = item.get("params") or {}
        sign = item.get("sign", 1)
        try:
            is_hole = float(sign) < 0
        except (TypeError, ValueError):
            is_hole = str(sign).lower() in {"孔洞", "hole", "-"}

        row = {
            "編號": index,
            "名稱": item.get("name") or f"子截面 {index}",
            "形狀": SectionComponent.normalize_shape(item.get("shape", "")),
            "性質": "孔洞" if is_hole else "實體",
            "x": item.get("x", 0),
            "y": item.get("y", 0),
            "θ": item.get("angle", 0),
            "b": params.get("b"),
            "h": params.get("h"),
            "B": params.get("B"),
            "H": params.get("H"),
            "tw": params.get("tw"),
            "tf": params.get("tf"),
            "d": params.get("d"),
            "D": params.get("D"),
        }
        rows.append(row)

    return pd.DataFrame(rows, columns=COLUMN_ORDER)


def dataframe_to_components(df: pd.DataFrame) -> List[SectionComponent]:
    components = []
    errors = []

    for position, (_, row) in enumerate(df.iterrows(), start=1):
        shape = SectionComponent.normalize_shape(row.get("形狀", ""))
        if shape not in SHAPE_PARAMS:
            errors.append(f"第 {position} 列：不支援的形狀「{shape}」。")
            continue

        params = {}
        for key in SHAPE_PARAMS[shape]:
            value = row.get(key)
            if pd.isna(value) or str(value).strip() == "":
                errors.append(f"第 {position} 列「{row.get('名稱', '')}」缺少尺寸 {key}。")
                continue
            try:
                params[key] = float(value)
            except (TypeError, ValueError):
                errors.append(f"第 {position} 列的尺寸 {key} 不是數值。")

        try:
            component = SectionComponent(
                cid=position,
                name=str(row.get("名稱") or f"子截面 {position}"),
                shape=shape,
                sign=-1 if str(row.get("性質", "實體")) == "孔洞" else 1,
                x=float(row.get("x", 0)),
                y=float(row.get("y", 0)),
                angle=float(row.get("θ", 0) or 0),
                params=params,
            )
            component.validate()
            components.append(component)
        except Exception as exc:
            errors.append(f"第 {position} 列：{exc}")

    if errors:
        raise ValueError("\n".join(errors))
    return components


def component_local_polygons(component: SectionComponent):
    p = component.params

    if component.shape == "矩形":
        b, h = p["b"], p["h"]
        return [([(-b/2, -h/2), (b/2, -h/2), (b/2, h/2), (-b/2, h/2)], False)]

    if component.shape == "I 型鋼":
        B, H, tw, tf = p["B"], p["H"], p["tw"], p["tf"]
        points = [
            (-B/2, H/2), (B/2, H/2), (B/2, H/2-tf),
            (tw/2, H/2-tf), (tw/2, -H/2+tf),
            (B/2, -H/2+tf), (B/2, -H/2),
            (-B/2, -H/2), (-B/2, -H/2+tf),
            (-tw/2, -H/2+tf), (-tw/2, H/2-tf),
            (-B/2, H/2-tf),
        ]
        return [(points, False)]

    if component.shape == "T 型截面":
        B, H, tw, tf = p["B"], p["H"], p["tw"], p["tf"]
        hw = H - tf
        af, aw = B * tf, tw * hw
        y_centroid = (af * (H - tf/2) + aw * (hw/2)) / (af + aw)
        points_from_bottom = [
            (-tw/2, 0), (tw/2, 0), (tw/2, H-tf),
            (B/2, H-tf), (B/2, H),
            (-B/2, H), (-B/2, H-tf), (-tw/2, H-tf),
        ]
        return [([(x, y-y_centroid) for x, y in points_from_bottom], False)]

    if component.shape == "中空矩形":
        B, H, b, h = p["B"], p["H"], p["b"], p["h"]
        outer = [(-B/2, -H/2), (B/2, -H/2), (B/2, H/2), (-B/2, H/2)]
        inner = [(-b/2, -h/2), (b/2, -h/2), (b/2, h/2), (-b/2, h/2)]
        return [(outer, False), (inner, True)]

    return []


def rotate_points(points, degrees: float):
    angle = math.radians(degrees)
    cos_value = math.cos(angle)
    sin_value = math.sin(angle)
    return [
        (x*cos_value - y*sin_value, x*sin_value + y*cos_value)
        for x, y in points
    ]


def draw_section(components: List[SectionComponent], result: Dict[str, Any] | None):
    fig, ax = plt.subplots(figsize=(8, 6))
    ax.set_aspect("equal", adjustable="box")
    palette = ["#d9eaf7", "#e4f3df", "#fff0cf", "#eadff4", "#dff3f1", "#f6dfdf"]

    for index, component in enumerate(components):
        facecolor = palette[index % len(palette)] if component.sign == 1 else "white"
        edgecolor = "#315f7d" if component.sign == 1 else "#b23b3b"
        linestyle = "-" if component.sign == 1 else "--"

        if component.shape in ("圓形", "中空圓管"):
            diameter = component.params["d"] if component.shape == "圓形" else component.params["D"]
            ax.add_patch(Circle(
                (component.x, component.y),
                diameter / 2,
                facecolor=facecolor,
                edgecolor=edgecolor,
                linewidth=2,
                linestyle=linestyle,
            ))
            if component.shape == "中空圓管":
                ax.add_patch(Circle(
                    (component.x, component.y),
                    component.params["d"] / 2,
                    facecolor="white",
                    edgecolor=edgecolor,
                    linewidth=2,
                ))
        else:
            for points, is_inner in component_local_polygons(component):
                points = rotate_points(points, component.angle)
                points = [(x + component.x, y + component.y) for x, y in points]
                ax.add_patch(Polygon(
                    points,
                    closed=True,
                    facecolor="white" if is_inner else facecolor,
                    edgecolor=edgecolor,
                    linewidth=2,
                    linestyle=linestyle if not is_inner else "-",
                ))

        ax.plot(component.x, component.y, marker="+", markersize=9, color="#222222")
        ax.annotate(str(component.cid), (component.x, component.y), xytext=(5, 5), textcoords="offset points")

    if result:
        ax.axhline(result["ybar"], color="#d1495b", linewidth=1.8, linestyle="--", label="整體形心 x 軸")
        ax.axvline(result["xbar"], color="#00798c", linewidth=1.8, linestyle="--", label="整體形心 y 軸")
        ax.plot(result["xbar"], result["ybar"], "ko", markersize=5)
        ax.annotate(
            f"G ({format_number(result['xbar'])}, {format_number(result['ybar'])})",
            (result["xbar"], result["ybar"]),
            xytext=(8, 8),
            textcoords="offset points",
        )
        ax.legend(loc="best")

    ax.autoscale_view()
    ax.margins(0.15)
    ax.grid(True, alpha=0.18)
    ax.set_xlabel("x")
    ax.set_ylabel("y")
    ax.set_title("截面配置與整體形心軸")
    fig.tight_layout()
    return fig


def result_to_csv(result: Dict[str, Any]) -> bytes:
    frame = pd.DataFrame(result["rows"])
    output = io.StringIO()
    frame.to_csv(output, index=False)
    summary = pd.DataFrame([{
        "總面積 A": result["A_total"],
        "xbar": result["xbar"],
        "ybar": result["ybar"],
        "Ix": result["Ix_total"],
        "Iy": result["Iy_total"],
        "kx": result["kx"],
        "ky": result["ky"],
    }])
    output.write("\n")
    summary.to_csv(output, index=False)
    return output.getvalue().encode("utf-8-sig")


def show_ai_summary(result: Dict[str, Any]) -> None:
    confidence = float(result.get("confidence", 0))
    status = "可自動建立" if result.get("can_auto_build") else "需人工確認"

    c1, c2, c3 = st.columns(3)
    c1.metric("AI 信心度", f"{confidence:.0%}")
    c2.metric("辨識狀態", status)
    c3.metric("長度單位", result.get("unit", "mm"))

    st.subheader("題目辨識")
    st.write(result.get("recognized_text") or "未辨識到題目文字。")

    st.subheader("題意與拆分方式")
    st.write(result.get("problem_summary") or "無")
    st.info(result.get("decomposition_reason") or "無拆分說明。")

    warnings = result.get("warnings") or []
    assumptions = result.get("assumptions") or []
    if warnings:
        st.warning("\n".join(f"• {item}" for item in warnings))
    if assumptions:
        with st.expander("AI 採用的假設"):
            for item in assumptions:
                st.write(f"• {item}")


def sidebar_settings() -> Tuple[str, str, str]:
    st.sidebar.header("AI 與網站設定")

    gemini_secret = str(read_secret("GEMINI_API_KEY", "") or "")
    openai_secret = str(read_secret("OPENAI_API_KEY", "") or "")
    available = []
    if gemini_secret:
        available.append("Gemini")
    if openai_secret:
        available.append("OpenAI / GPT")
    if not available:
        available = ["Gemini", "OpenAI / GPT"]

    provider = st.sidebar.selectbox("AI 服務", available)
    default_model = "gemini-3.5-flash" if provider == "Gemini" else "gpt-5.5"
    model = st.sidebar.text_input("模型名稱", value=default_model)

    server_key = gemini_secret if provider == "Gemini" else openai_secret
    allow_user_key = bool(read_secret("ALLOW_USER_API_KEY", True))

    if server_key:
        st.sidebar.success("網站已設定伺服器端 API Key，使用者不會看到金鑰。")
        api_key = server_key
    elif allow_user_key:
        st.sidebar.warning("網站尚未設定內建金鑰。")
        api_key = st.sidebar.text_input("請輸入自己的 API Key", type="password")
    else:
        st.sidebar.error("網站管理員尚未設定 API Key。")
        api_key = ""

    max_uses = int(read_secret("MAX_ANALYSES_PER_SESSION", 5) or 5)
    st.sidebar.caption(
        f"本次瀏覽器工作階段已解析 {st.session_state.analysis_count}/{max_uses} 次。"
    )
    st.sidebar.divider()
    st.sidebar.caption(
        "AI 負責讀圖與拆解；數值答案由本地公式引擎重新計算。"
    )
    return provider, model, api_key


def render_upload_tab(provider: str, model: str, api_key: str) -> None:
    st.header("① 上傳題目照片")
    st.write("手機或電腦都能使用。照片請包含完整圖形、尺寸線與題目文字。")

    uploaded = st.file_uploader(
        "選擇或拍攝題目圖片",
        type=["jpg", "jpeg", "png", "webp", "bmp"],
        accept_multiple_files=False,
    )

    if uploaded is None:
        st.info("上傳照片後，系統會使用 AI 辨識題目並建立可編輯的截面資料。")
        return

    controls = st.columns([1, 1, 1, 4])
    if controls[0].button("↶ 左轉 90°", use_container_width=True):
        st.session_state.image_rotation = (st.session_state.image_rotation + 90) % 360
    if controls[1].button("↷ 右轉 90°", use_container_width=True):
        st.session_state.image_rotation = (st.session_state.image_rotation - 90) % 360
    st.session_state.enhance_image = controls[2].toggle(
        "自動增強",
        value=st.session_state.enhance_image,
    )

    try:
        image_bytes, mime_type, image = prepare_image(uploaded)
        st.session_state.processed_image = image_bytes
        st.session_state.processed_mime = mime_type
        st.image(image, caption="目前送交 AI 分析的圖片", use_container_width=True)
    except Exception as exc:
        st.error(f"圖片處理失敗：{exc}")
        return

    max_uses = int(read_secret("MAX_ANALYSES_PER_SESSION", 5) or 5)
    disabled = not api_key or st.session_state.analysis_count >= max_uses

    if st.button(
        "🔍 開始 AI 解析題目",
        type="primary",
        use_container_width=True,
        disabled=disabled,
    ):
        if st.session_state.analysis_count >= max_uses:
            st.error("本次工作階段已達解析次數上限。")
            return

        with st.spinner("AI 正在讀取題目文字、尺寸與截面配置……"):
            try:
                result = analyze_image(
                    image_bytes=image_bytes,
                    mime_type=mime_type,
                    provider=provider,
                    api_key=api_key,
                    model=model,
                )
                st.session_state.ai_result = result
                st.session_state.analysis_count += 1
                if result.get("components"):
                    st.session_state.component_df = ai_components_to_dataframe(result)
                st.session_state.calculation = None
                st.success("解析完成。請到「確認截面與計算」頁籤核對資料。")
            except Exception as exc:
                st.error(f"AI 解析失敗：{exc}")

    if not api_key:
        st.warning("目前沒有可用的 API Key，管理員需在 Streamlit Secrets 設定金鑰。")

    if st.session_state.ai_result:
        st.divider()
        show_ai_summary(st.session_state.ai_result)


def render_calculation_tab() -> None:
    st.header("② 確認截面資料並計算")
    st.warning("AI 可能讀錯模糊尺寸。計算前請對照原圖確認每列尺寸、x、y 與孔洞正負號。")

    result = st.session_state.ai_result
    if result:
        with st.expander("查看 AI 題意摘要", expanded=False):
            show_ai_summary(result)

    unit_default = result.get("unit", "mm") if result else "mm"
    unit = st.selectbox("長度單位", ["mm", "cm", "m", "in"], index=["mm", "cm", "m", "in"].index(unit_default) if unit_default in ["mm", "cm", "m", "in"] else 0)

    column_config = {
        "編號": st.column_config.NumberColumn("編號", disabled=True, width="small"),
        "名稱": st.column_config.TextColumn("名稱", required=True),
        "形狀": st.column_config.SelectboxColumn(
            "形狀",
            options=list(SHAPE_PARAMS.keys()),
            required=True,
        ),
        "性質": st.column_config.SelectboxColumn(
            "性質",
            options=["實體", "孔洞"],
            required=True,
        ),
        "x": st.column_config.NumberColumn("形心 x", format="%.6f"),
        "y": st.column_config.NumberColumn("形心 y", format="%.6f"),
        "θ": st.column_config.NumberColumn("旋轉角 θ°", format="%.3f"),
        "b": st.column_config.NumberColumn("b", format="%.6f"),
        "h": st.column_config.NumberColumn("h", format="%.6f"),
        "B": st.column_config.NumberColumn("B", format="%.6f"),
        "H": st.column_config.NumberColumn("H", format="%.6f"),
        "tw": st.column_config.NumberColumn("tw", format="%.6f"),
        "tf": st.column_config.NumberColumn("tf", format="%.6f"),
        "d": st.column_config.NumberColumn("d", format="%.6f"),
        "D": st.column_config.NumberColumn("D", format="%.6f"),
    }

    edited = st.data_editor(
        st.session_state.component_df,
        column_config=column_config,
        column_order=COLUMN_ORDER,
        num_rows="dynamic",
        hide_index=True,
        use_container_width=True,
        key="component_editor",
    )
    edited = edited.copy()
    edited["編號"] = range(1, len(edited) + 1)
    st.session_state.component_df = edited

    st.caption(
        "矩形用 b、h；圓形用 d；I 型鋼／T 型截面用 B、H、tw、tf；"
        "中空矩形用 B、H、b、h；中空圓管用 D、d。"
    )

    left, right = st.columns([1, 1])
    calculate_clicked = left.button(
        "🧮 套用平行軸定理並計算",
        type="primary",
        use_container_width=True,
    )
    if right.button("載入單一矩形測試資料", use_container_width=True):
        st.session_state.component_df = pd.DataFrame(DEFAULT_ROWS, columns=COLUMN_ORDER)
        st.session_state.calculation = None
        st.rerun()

    if calculate_clicked:
        try:
            components = dataframe_to_components(edited)
            result_calc = InertiaCalculator.calculate(components)
            st.session_state.calculation = {
                "result": result_calc,
                "components": [component.to_dict() for component in components],
                "unit": unit,
            }
            st.success("計算完成。")
        except Exception as exc:
            st.error(str(exc))

    calculation = st.session_state.calculation
    if not calculation:
        return

    result_calc = calculation["result"]
    components = [
        SectionComponent(**item)
        for item in calculation["components"]
    ]
    unit = calculation["unit"]

    st.divider()
    st.subheader("計算結果")
    metrics = st.columns(7)
    metrics[0].metric("總面積 A", f"{format_number(result_calc['A_total'])} {unit}²")
    metrics[1].metric("x̄", f"{format_number(result_calc['xbar'])} {unit}")
    metrics[2].metric("ȳ", f"{format_number(result_calc['ybar'])} {unit}")
    metrics[3].metric("Ix", f"{format_number(result_calc['Ix_total'])} {unit}⁴")
    metrics[4].metric("Iy", f"{format_number(result_calc['Iy_total'])} {unit}⁴")
    metrics[5].metric("kx", f"{format_number(result_calc['kx'])} {unit}")
    metrics[6].metric("ky", f"{format_number(result_calc['ky'])} {unit}")

    preview_col, summary_col = st.columns([1.2, 1])
    with preview_col:
        figure = draw_section(components, result_calc)
        st.pyplot(figure, use_container_width=True)
        plt.close(figure)
    with summary_col:
        st.markdown("### 最終答案")
        st.latex(r"\bar{x}=\frac{\sum A_i x_i}{\sum A_i},\qquad \bar{y}=\frac{\sum A_i y_i}{\sum A_i}")
        st.latex(r"I_x=\sum\left(I_{x,c}+A_i d_y^2\right),\qquad I_y=\sum\left(I_{y,c}+A_i d_x^2\right)")
        st.write(f"- **A = {format_number(result_calc['A_total'])} {unit}²**")
        st.write(f"- **x̄ = {format_number(result_calc['xbar'])} {unit}**")
        st.write(f"- **ȳ = {format_number(result_calc['ybar'])} {unit}**")
        st.write(f"- **Ix = {format_number(result_calc['Ix_total'])} {unit}⁴**")
        st.write(f"- **Iy = {format_number(result_calc['Iy_total'])} {unit}⁴**")
        st.write(f"- **kx = {format_number(result_calc['kx'])} {unit}**")
        st.write(f"- **ky = {format_number(result_calc['ky'])} {unit}**")

    project = {
        "unit": unit,
        "ai_result": st.session_state.ai_result,
        "components": calculation["components"],
        "result": result_calc,
    }
    download_col1, download_col2 = st.columns(2)
    download_col1.download_button(
        "下載完整專案 JSON",
        data=json.dumps(project, ensure_ascii=False, indent=2),
        file_name="截面慣性矩專案.json",
        mime="application/json",
        use_container_width=True,
    )
    download_col2.download_button(
        "下載逐步計算 CSV",
        data=result_to_csv(result_calc),
        file_name="截面慣性矩逐步計算.csv",
        mime="text/csv",
        use_container_width=True,
    )


def render_steps_tab() -> None:
    st.header("③ 完整解題過程與驗算表")
    calculation = st.session_state.calculation
    if not calculation:
        st.info("請先到「確認截面與計算」完成計算。")
        return

    result = calculation["result"]
    unit = calculation["unit"]
    frame = pd.DataFrame(result["rows"])

    numeric_columns = [
        "A", "±A", "xi", "yi", "±Axi", "±Ayi",
        "±Ix,c(θ)", "±Iy,c(θ)", "Δx", "Δy",
        "±AΔy²", "±AΔx²", "Ix,i", "Iy,i",
    ]
    display_frame = frame.drop(columns=["公式"]).copy()
    for column in numeric_columns:
        display_frame[column] = display_frame[column].map(format_number)

    st.dataframe(display_frame, use_container_width=True, hide_index=True)
    st.markdown(build_teaching_text(result, unit))


def render_about_tab() -> None:
    st.header("使用說明")
    st.markdown(
        """
### 操作流程

1. 上傳或直接拍攝題目照片。
2. AI 辨識題目文字、尺寸、座標與孔洞。
3. 到「確認截面與計算」核對 AI 建立的資料。
4. 按下計算，系統以本地公式引擎求出形心、Ix、Iy、kx、ky。
5. 查看逐步驗算表，或下載 JSON、CSV。

### 公開網站版本

部署完成後，其他人只要開啟網址即可使用，不必安裝 Python。
API Key 應放在 Streamlit Secrets，不可直接寫在程式碼或上傳到 GitHub。

### 注意

AI 對模糊尺寸、斜拍照片、重疊尺寸線及不規則曲線可能辨識錯誤。
本地公式計算正確的前提，是截面尺寸與位置輸入正確。
        """
    )


init_state()
require_password()
provider, model, api_key = sidebar_settings()

st.title("📐 AI 拍照解析－截面慣性矩輔助教學系統")
st.caption("上傳題目照片，AI 自動辨識與拆分截面，再由本地公式引擎完成精確驗算。")

tab_upload, tab_calc, tab_steps, tab_about = st.tabs([
    "① 拍照上傳與 AI 解析",
    "② 確認截面與計算",
    "③ 完整步驟",
    "使用說明",
])

with tab_upload:
    render_upload_tab(provider, model, api_key)
with tab_calc:
    render_calculation_tab()
with tab_steps:
    render_steps_tab()
with tab_about:
    render_about_tab()
