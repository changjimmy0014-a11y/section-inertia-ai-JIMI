# -*- coding: utf-8 -*-
from __future__ import annotations

import io
import json
import math
from typing import Any, Dict, Tuple

import matplotlib.pyplot as plt
from matplotlib.patches import Circle, Ellipse, Polygon, Wedge
import pandas as pd
from PIL import Image, ImageEnhance, ImageOps
import streamlit as st

from ai_service import analyze_images
from geometry_engine import solve_composite, validate_textbook_10_21_22
from symbolic_engine import solve_symbolic

st.set_page_config(page_title="AI 截面慣性矩全題型教學系統",page_icon="📐",layout="wide",initial_sidebar_state="expanded")


def init_state():
    defaults={"analysis":None,"selected_problem":0,"solution":None,"analysis_count":0,"rotation":{},"enhance":True,"edited_problem_json":""}
    for k,v in defaults.items():
        if k not in st.session_state: st.session_state[k]=v


def secret(name,default=None):
    try: return st.secrets.get(name,default)
    except Exception: return default


def fmt(v):
    if v is None: return "—"
    try: n=float(v)
    except Exception: return str(v)
    if n==0: return "0"
    if abs(n)>=1e6 or abs(n)<1e-3: return f"{n:.6e}"
    return f"{n:.6f}".rstrip("0").rstrip(".")


def prepare_image(uploaded,rotation,enhance)->Tuple[bytes,str,Image.Image]:
    image=ImageOps.exif_transpose(Image.open(uploaded)).convert("RGB")
    if rotation: image=image.rotate(rotation,expand=True)
    if enhance:
        image=ImageOps.autocontrast(image); image=ImageEnhance.Contrast(image).enhance(1.15); image=ImageEnhance.Sharpness(image).enhance(1.25)
    if max(image.size)>2400: image.thumbnail((2400,2400),Image.Resampling.LANCZOS)
    buf=io.BytesIO(); image.save(buf,format="JPEG",quality=93,optimize=True)
    return buf.getvalue(),"image/jpeg",image


def sidebar():
    st.sidebar.header("AI 與網站設定")
    key=str(secret("GEMINI_API_KEY","") or "")
    model=st.sidebar.text_input("Gemini 模型",value=str(secret("GEMINI_MODEL","gemini-3.5-flash")))
    if key: st.sidebar.success("已使用伺服器端 API Key，使用者看不到金鑰。")
    elif bool(secret("ALLOW_USER_API_KEY",True)): key=st.sidebar.text_input("Gemini API Key",type="password")
    else: st.sidebar.error("管理員尚未設定 Gemini API Key。")
    max_count=int(secret("MAX_ANALYSES_PER_SESSION",5) or 5)
    st.sidebar.caption(f"本次工作階段已解析 {st.session_state.analysis_count}/{max_count} 次。")
    st.sidebar.divider()
    verify=bool(secret("ENABLE_AI_VERIFICATION",True))
    fallbacks=str(secret("GEMINI_FALLBACK_MODELS","gemini-3.1-flash-lite-preview,gemini-2.5-flash"))
    st.sidebar.caption("二次幾何審查：" + ("已啟用" if verify else "未啟用"))
    st.sidebar.caption("備用模型：" + fallbacks)
    st.sidebar.markdown("**本地引擎支援**\n- 組合截面、孔洞、多邊形\n- T/U/工字型梁\n- 曲線陰影直角座標積分\n- 極座標扇形積分\n- 原始軸、形心軸、指定軸\n- Ix、Iy、Ixy、J、kx、ky")
    return key,model,verify,[x.strip() for x in fallbacks.split(",") if x.strip()]


def render_upload(api_key,model,verify,fallback_models):
    st.header("① 上傳題目照片")
    st.write("可一次上傳多張，例如題目文字與共用圖形分開拍。系統會辨識多個題號。")
    files=st.file_uploader("拍攝或選擇題目圖片",type=["jpg","jpeg","png","webp","bmp"],accept_multiple_files=True)
    if not files:
        st.info("支援組合截面、曲線積分、圓形扇形、T/U 型梁及圓孔題目。")
        return
    prepared=[]; cols=st.columns(min(3,len(files)))
    for i,f in enumerate(files):
        k=f.name+str(f.size); rot=st.session_state.rotation.get(k,0)
        with cols[i%len(cols)]:
            st.caption(f.name); c1,c2=st.columns(2)
            if c1.button("左轉",key=f"L{k}",use_container_width=True): st.session_state.rotation[k]=(rot+90)%360; st.rerun()
            if c2.button("右轉",key=f"R{k}",use_container_width=True): st.session_state.rotation[k]=(rot-90)%360; st.rerun()
            data,mime,img=prepare_image(f,rot,st.session_state.enhance); st.image(img,use_container_width=True); prepared.append((data,mime))
    st.session_state.enhance=st.toggle("自動增強照片",value=st.session_state.enhance)
    max_count=int(secret("MAX_ANALYSES_PER_SESSION",5) or 5)
    if st.button("🔍 AI 辨識題目並建立解題模型",type="primary",use_container_width=True,disabled=(not api_key or st.session_state.analysis_count>=max_count)):
        with st.spinner("正在辨識題號、尺寸、陰影範圍、曲線與指定軸……"):
            try:
                a=analyze_images(prepared,api_key,model,fallback_models=fallback_models,enable_verification=verify); st.session_state.analysis=a; st.session_state.selected_problem=0; st.session_state.solution=None; st.session_state.analysis_count+=1
                ps=a.get("problems") or []
                if ps: st.session_state.edited_problem_json=json.dumps(ps[0],ensure_ascii=False,indent=2)
                st.success(f"辨識完成，共找到 {len(ps)} 個題目。")
            except Exception as exc: st.error(f"AI 解析失敗：{exc}")


def problem_editor():
    a=st.session_state.analysis
    if not a or not a.get("problems"): return None
    ps=a["problems"]; labels=[f"{p.get('problem_id')}｜{p.get('title','')}" for p in ps]
    idx=st.selectbox("選擇要解的題目",range(len(ps)),format_func=lambda i:labels[i],index=min(st.session_state.selected_problem,len(ps)-1))
    if idx!=st.session_state.selected_problem:
        st.session_state.selected_problem=idx; st.session_state.solution=None; st.session_state.edited_problem_json=json.dumps(ps[idx],ensure_ascii=False,indent=2); st.rerun()
    p=ps[idx]; c1,c2,c3=st.columns(3); c1.metric("題型",p.get("mode","")); c2.metric("信心度",f"{float(p.get('confidence',0)):.0%}"); c3.metric("單位",p.get("unit","symbolic"))
    st.write(p.get("recognized_text") or ""); st.info(p.get("reasoning_summary") or "無模型說明。")
    if p.get("warnings"): st.warning("\n".join(f"• {x}" for x in p["warnings"]))
    if p.get("geometry_audit"):
        with st.expander("幾何尺寸鏈與板件稽核", expanded=True):
            st.json(p.get("geometry_audit"))
    meta=(a.get("analysis_meta") or {})
    if meta.get("deterministic_repairs"):
        st.success("已啟用課本題型幾何校正：補齊遺漏板件並驗證尺寸鏈。")
    with st.expander("進階：檢查或修正 AI 建立的解題 JSON"):
        edited=st.text_area("修改後按套用",value=st.session_state.edited_problem_json,height=520)
        if st.button("套用 JSON 修改"):
            try:
                parsed=json.loads(edited); ps[idx]=parsed; st.session_state.edited_problem_json=json.dumps(parsed,ensure_ascii=False,indent=2); st.session_state.solution=None; st.rerun()
            except Exception as exc: st.error(f"JSON 格式錯誤：{exc}")
    return ps[idx]


def solve_problem(p):
    if not p.get("can_solve",False): raise ValueError("AI 判定照片資訊不足。請補拍完整尺寸、曲線邊界或指定軸。")
    mode=str(p.get("mode") or "").lower()
    if mode=="composite":
        return solve_composite(p.get("components") or [],axis_x=float(p.get("axis_x") or 0),axis_y=float(p.get("axis_y") or 0),rotated_axis_angle_deg=float(p.get("rotated_axis_angle_deg") or 0))
    if mode in {"cartesian","cartesian_vertical","cartesian_horizontal","polar","sector","polar_region"}: return solve_symbolic(p)
    raise ValueError(f"尚不支援題型：{mode}")


def draw_composite(solution):
    fig,ax=plt.subplots(figsize=(8,5.5)); colors=["#cfe5f5","#dcefd5","#f9e8bd","#e8daf4","#d7efed"]
    for i,c in enumerate(solution.get("components") or []):
        kind=str(c.get("kind") or ""); sign=-1 if float(c.get("sign",1))<0 else 1; fc=colors[i%len(colors)] if sign==1 else "white"; ec="#245f76" if sign==1 else "#b23b3b"; ls="-" if sign==1 else "--"
        if kind=="rectangle":
            b,h=float(c["b"]),float(c["h"]); x,y=float(c.get("x",0)),float(c.get("y",0)); ang=float(c.get("angle",0)); pts=[(-b/2,-h/2),(b/2,-h/2),(b/2,h/2),(-b/2,h/2)]; t=math.radians(ang); pts=[(x+px*math.cos(t)-py*math.sin(t),y+px*math.sin(t)+py*math.cos(t)) for px,py in pts]; ax.add_patch(Polygon(pts,closed=True,facecolor=fc,edgecolor=ec,linewidth=2,linestyle=ls))
        elif kind=="circle":
            r=float(c["r"]) if c.get("r") is not None else float(c["d"])/2; ax.add_patch(Circle((float(c.get("x",0)),float(c.get("y",0))),r,facecolor=fc,edgecolor=ec,linewidth=2,linestyle=ls))
        elif kind=="ellipse":
            ax.add_patch(Ellipse((float(c.get("x",0)),float(c.get("y",0))),2*float(c["a"]),2*float(c["b"]),angle=float(c.get("angle",0)),facecolor=fc,edgecolor=ec,linewidth=2,linestyle=ls))
        elif kind in {"polygon","triangle","trapezoid"}: ax.add_patch(Polygon(c.get("vertices") or [],closed=True,facecolor=fc,edgecolor=ec,linewidth=2,linestyle=ls))
        elif kind in {"circular_sector","sector"}:
            a1,a2=float(c["theta1"]),float(c["theta2"])
            if not str(c.get("angle_unit","rad")).lower().startswith("deg"): a1,a2=math.degrees(a1),math.degrees(a2)
            ax.add_patch(Wedge((float(c.get("center_x",0)),float(c.get("center_y",0))),float(c.get("r_outer",c.get("r"))),a1,a2,width=float(c.get("r_outer",c.get("r")))-float(c.get("r_inner",0)),facecolor=fc,edgecolor=ec,linewidth=2,linestyle=ls))
    ax.axhline(solution["ybar"],color="#d1495b",linestyle="--",label="形心 x' 軸"); ax.axvline(solution["xbar"],color="#00798c",linestyle="--",label="形心 y' 軸"); ax.axhline(solution["axis_y"],color="#777",linestyle=":",label="指定 x 軸"); ax.axvline(solution["axis_x"],color="#444",linestyle=":",label="指定 y 軸"); ax.plot(solution["xbar"],solution["ybar"],"ko"); ax.autoscale_view(); ax.margins(.15); ax.set_aspect("equal",adjustable="datalim"); ax.grid(alpha=.2); ax.legend(); ax.set_xlabel("x"); ax.set_ylabel("y"); fig.tight_layout(); return fig


def render_composite(p,s):
    u=p.get("unit",""); st.subheader("計算結果")
    vals=[("A",s["A"],f"{u}²"),("x̄",s["xbar"],u),("ȳ",s["ybar"],u),("Ix 原始軸",s["Ix_origin"],f"{u}⁴"),("Iy 原始軸",s["Iy_origin"],f"{u}⁴"),("Jₒ",s["J_origin"],f"{u}⁴")]
    cols=st.columns(6)
    for col,(lab,v,suf) in zip(cols,vals): col.metric(lab,f"{fmt(v)} {suf}")
    vals2=[("Ix′",s["Ix_centroid"],f"{u}⁴"),("Iy′",s["Iy_centroid"],f"{u}⁴"),("Ixy′",s["Ixy_centroid"],f"{u}⁴"),("kx",s["kx_centroid"],u),("ky",s["ky_centroid"],u),("Jc",s["J_centroid"],f"{u}⁴")]
    cols=st.columns(6)
    for col,(lab,v,suf) in zip(cols,vals2): col.metric(lab,f"{fmt(v)} {suf}")
    st.markdown("### 題目指定軸"); st.write(f"- 水平軸 y={s['axis_y']}：**Ix={fmt(s['Ix_axis_y'])} {u}⁴**"); st.write(f"- 垂直軸 x={s['axis_x']}：**Iy={fmt(s['Iy_axis_x'])} {u}⁴**")
    if str(p.get("problem_id")) in {"10-21","10-22","10-21/22"}:
        validation=validate_textbook_10_21_22(s)
        st.markdown("### 與課本答案核對")
        st.write("- 10-21：**ȳ = 22.5 mm；Ix′ = 34.4×10⁶ mm⁴**")
        st.write("- 10-22：**Iy = 122×10⁶ mm⁴**")
        if validation["passed"]:
            st.success("本地計算與課本答案一致（允許課本四捨五入誤差）。")
        else:
            st.error("計算結果與課本答案不一致，請檢查 AI 建立的板件與尺寸。")
        check_rows=[]
        for key,item in validation["checks"].items():
            check_rows.append({
                "項目":key,
                "程式值":item["actual"],
                "基準值":item["expected"],
                "相對誤差":item["relative_error"],
                "通過":item["passed"],
            })
        st.dataframe(pd.DataFrame(check_rows),use_container_width=True,hide_index=True)
    l,r=st.columns([1,1.5])
    with l:
        fig=draw_composite(s); st.pyplot(fig,use_container_width=True); plt.close(fig)
    with r: st.dataframe(pd.DataFrame(s["rows"]),use_container_width=True,hide_index=True)
    st.latex(r"\bar{x}=\frac{\sum A_ix_i}{\sum A_i},\quad \bar{y}=\frac{\sum A_iy_i}{\sum A_i}"); st.latex(r"I_{x'}=\sum(I_{x,c_i}+A_i(y_i-\bar y)^2)"); st.latex(r"I_{y'}=\sum(I_{y,c_i}+A_i(x_i-\bar x)^2)")


def render_symbolic(p,s):
    st.subheader("積分模型"); st.json(s["setup"]); st.subheader("精確答案")
    order=[("A","面積 A"),("xbar","形心 x̄"),("ybar","形心 ȳ"),("Ix_origin","Ix 原始 x 軸"),("Iy_origin","Iy 原始 y 軸"),("Ix_target","Ix 指定水平軸"),("Iy_target","Iy 指定垂直軸"),("Ix_centroid","Ix′ 形心軸"),("Iy_centroid","Iy′ 形心軸"),("Ixy_origin","Ixy"),("J_origin","J"),("kx_centroid","kx"),("ky_centroid","ky")]
    for k,label in order:
        if k in s["results"]:
            item=s["results"][k]; st.markdown(f"**{label}**"); st.latex(item["latex"])
            if item.get("numeric") is not None: st.caption(f"數值：{fmt(item['numeric'])}")
    st.subheader("積分式")
    for label,latex in s.get("integrals",{}).items(): st.markdown(f"**{label}**"); st.latex(latex)
    st.info("符號角度（例如 α）以弧度處理；度數會轉成 π/180。")


def render_solve():
    st.header("② 選擇題目、確認模型並計算"); p=problem_editor()
    if not p: st.info("請先完成 AI 辨識。"); return
    if st.button("🧮 使用本地公式引擎精確計算",type="primary",use_container_width=True):
        with st.spinner("正在建立積分式／套用平行軸定理……"):
            try: st.session_state.solution={"problem":p,"result":solve_problem(p)}; st.success("計算完成。")
            except Exception as exc: st.error(str(exc))
    solved=st.session_state.solution
    if not solved or solved["problem"].get("problem_id")!=p.get("problem_id"): return
    if solved["result"].get("mode")=="composite": render_composite(p,solved["result"])
    else: render_symbolic(p,solved["result"])


def render_steps():
    st.header("③ 完整解題步驟"); solved=st.session_state.solution
    if not solved: st.info("請先完成計算。"); return
    p,s=solved["problem"],solved["result"]; st.markdown(f"## {p.get('problem_id')} {p.get('title','')}"); st.write(p.get("reasoning_summary") or "")
    if s.get("mode")=="composite":
        st.markdown("1. 拆成不重疊基本面積，孔洞用負面積。\n2. 求各面積、形心、自身形心慣性矩。\n3. 求整體形心。\n4. 套用平行軸定理。\n5. 加總並求 J、kx、ky。")
        st.dataframe(pd.DataFrame(s["rows"]),use_container_width=True,hide_index=True)
        st.latex(r"A=\sum s_iA_i"); st.latex(r"I_x=\sum s_i(I_{x,c_i}+A_id_y^2)"); st.latex(r"I_y=\sum s_i(I_{y,c_i}+A_id_x^2)")
    else:
        if s["mode"]=="cartesian": st.markdown("垂直條帶：dA=[y上−y下]dx；水平條帶：dA=[x右−x左]dy。Ix=∫y²dA，Iy=∫x²dA。")
        else: st.markdown("極座標：dA=r dr dθ，x=r cosθ，y=r sinθ。")
        for label,latex in s.get("integrals",{}).items(): st.markdown(f"**{label}**"); st.latex(latex)
        for k,item in s["results"].items(): st.write(f"**{k}**"); st.latex(item["latex"])


def render_export():
    st.header("匯出與更新")
    if st.session_state.analysis: st.download_button("下載 AI 辨識 JSON",json.dumps(st.session_state.analysis,ensure_ascii=False,indent=2),"題目辨識模型.json","application/json",use_container_width=True)
    if st.session_state.solution: st.download_button("下載完整解題 JSON",json.dumps(st.session_state.solution,ensure_ascii=False,indent=2,default=str),"截面慣性矩完整解答.json","application/json",use_container_width=True)
    st.markdown("新版 ZIP 解壓後，覆蓋 GitHub Repository 的同名檔案並 Commit。Streamlit 會自動重部署，原分享網址不變。")


def render_help():
    st.header("支援題型與限制")
    st.markdown("""
### 已支援
- 原始 x/y 軸與形心 x′/y′ 軸的 Ix、Iy
- 平行軸定理、Ixy、J、kx、ky
- 矩形、圓、橢圓、多邊形、三角形、梯形、扇形
- 孔洞與組合面積
- T 型、U 型、工字型、多矩形梁
- 直角座標曲線陰影積分
- 極座標扇形與環形扇形
- 一張照片多題號選擇
- 兩階段 AI 幾何審查、503 自動重試與備用模型
- 課本 10-21/10-22 尺寸鏈與標準答案自動驗證

### 目前不支援
- 三維剛體質量慣性矩
- 扭轉常數與塑性截面模數
- 缺少完整邊界、尺寸或指定軸的照片
""")

init_state(); api_key,model,verify,fallback_models=sidebar()
st.title("📐 AI 拍照解析－截面慣性矩全題型教學系統 v2.1")
st.caption("組合截面、曲線陰影積分、圓形扇形、T/U 型梁、指定軸與形心軸。")
t1,t2,t3,t4,t5=st.tabs(["① 拍照與 AI 辨識","② 確認模型與計算","③ 完整步驟","匯出","使用說明"])
with t1: render_upload(api_key,model,verify,fallback_models)
with t2: render_solve()
with t3: render_steps()
with t4: render_export()
with t5: render_help()
