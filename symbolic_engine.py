# -*- coding: utf-8 -*-
from __future__ import annotations

import re
from typing import Any, Dict, Iterable, Mapping
import sympy as sp

ALLOWED_FUNCTIONS = {
    "sqrt": sp.sqrt, "sin": sp.sin, "cos": sp.cos, "tan": sp.tan,
    "asin": sp.asin, "acos": sp.acos, "atan": sp.atan,
    "exp": sp.exp, "log": sp.log, "pi": sp.pi, "Abs": sp.Abs,
}


def _symbols(names: Iterable[str]) -> Dict[str, sp.Symbol]:
    all_names = {str(n).strip() for n in names if str(n).strip()}
    all_names.update({"x", "y", "r", "theta"})
    return {n: sp.Symbol(n, real=True) for n in all_names}


def _expr(text: Any, symbols: Dict[str, sp.Symbol]) -> sp.Expr:
    raw = str(text).strip()
    if not raw:
        raise ValueError("缺少積分邊界或函數。")
    if "__" in raw or any(w in raw for w in ["import", "exec", "eval", "open(", "os.", "sys."]):
        raise ValueError("運算式含有不允許內容。")
    if not re.fullmatch(r"[0-9A-Za-z_+\-*/^().,\s]+", raw):
        raise ValueError(f"運算式含不支援字元：{raw}")
    try:
        return sp.sympify(raw.replace("^", "**"), locals={**ALLOWED_FUNCTIONS, **symbols})
    except Exception as exc:
        raise ValueError(f"無法解析運算式：{raw}") from exc


def _subs(values: Mapping[str, Any], symbols: Dict[str, sp.Symbol], degree_vars=()) -> Dict[sp.Symbol, sp.Expr]:
    result = {}; degree_vars=set(degree_vars or [])
    for name, value in (values or {}).items():
        if value is None or str(value).strip()=="": continue
        symbol = symbols.setdefault(str(name), sp.Symbol(str(name), real=True))
        val = _expr(value, symbols)
        if str(name) in degree_vars: val = val*sp.pi/180
        result[symbol] = val
    return result


def _simp(e): return sp.factor(sp.simplify(sp.trigsimp(e)))


def _num(e):
    if getattr(e, "free_symbols", set()): return None
    try:
        v=complex(sp.N(e, 14))
        return float(v.real) if abs(v.imag)<1e-10 else None
    except Exception: return None


def _ser(e):
    e=_simp(e)
    return {"sympy":str(e),"latex":sp.latex(e),"numeric":_num(e)}


def solve_cartesian(p: Dict[str, Any]) -> Dict[str, Any]:
    orientation=str(p.get("orientation") or "vertical").lower()
    syms=_symbols((p.get("variables") or {}).keys()); x,y=syms["x"],syms["y"]
    sub=_subs(p.get("variables") or {}, syms, p.get("angle_variables_degrees") or [])
    axis_x=_expr(p.get("axis_x", "0"), syms).subs(sub)
    axis_y=_expr(p.get("axis_y", "0"), syms).subs(sub)
    if orientation.startswith("v"):
        lo=_expr(p.get("lower_function"),syms).subs(sub); up=_expr(p.get("upper_function"),syms).subs(sub)
        a=_expr(p.get("lower_bound"),syms).subs(sub); b=_expr(p.get("upper_bound"),syms).subs(sub)
        h=up-lo; A=sp.integrate(h,(x,a,b)); Qy=sp.integrate(x*h,(x,a,b)); Qx=sp.integrate((up**2-lo**2)/2,(x,a,b))
        Ix0=sp.integrate((up**3-lo**3)/3,(x,a,b)); Iy0=sp.integrate(x**2*h,(x,a,b)); Ixy0=sp.integrate(x*(up**2-lo**2)/2,(x,a,b))
        Ixt=sp.integrate(((up-axis_y)**3-(lo-axis_y)**3)/3,(x,a,b)); Iyt=sp.integrate((x-axis_x)**2*h,(x,a,b)); Ixyt=sp.integrate((x-axis_x)*((up-axis_y)**2-(lo-axis_y)**2)/2,(x,a,b))
        setup={"orientation":"vertical","dA":f"({sp.sstr(up)}-({sp.sstr(lo)})) dx","bounds":[sp.sstr(a),sp.sstr(b)],"lower_function":sp.sstr(lo),"upper_function":sp.sstr(up)}
        area_integral=sp.Integral(h,(x,a,b))
    elif orientation.startswith("h"):
        left=_expr(p.get("left_function"),syms).subs(sub); right=_expr(p.get("right_function"),syms).subs(sub)
        a=_expr(p.get("lower_bound"),syms).subs(sub); b=_expr(p.get("upper_bound"),syms).subs(sub)
        w=right-left; A=sp.integrate(w,(y,a,b)); Qx=sp.integrate(y*w,(y,a,b)); Qy=sp.integrate((right**2-left**2)/2,(y,a,b))
        Ix0=sp.integrate(y**2*w,(y,a,b)); Iy0=sp.integrate((right**3-left**3)/3,(y,a,b)); Ixy0=sp.integrate(y*(right**2-left**2)/2,(y,a,b))
        Ixt=sp.integrate((y-axis_y)**2*w,(y,a,b)); Iyt=sp.integrate(((right-axis_x)**3-(left-axis_x)**3)/3,(y,a,b)); Ixyt=sp.integrate((y-axis_y)*((right-axis_x)**2-(left-axis_x)**2)/2,(y,a,b))
        setup={"orientation":"horizontal","dA":f"({sp.sstr(right)}-({sp.sstr(left)})) dy","bounds":[sp.sstr(a),sp.sstr(b)],"left_function":sp.sstr(left),"right_function":sp.sstr(right)}
        area_integral=sp.Integral(w,(y,a,b))
    else: raise ValueError("orientation 必須是 vertical 或 horizontal。")
    A=_simp(A)
    if A==0: raise ValueError("積分後面積為 0。")
    xb=_simp(Qy/A); yb=_simp(Qx/A); Ixc=_simp(Ix0-A*yb**2); Iyc=_simp(Iy0-A*xb**2); Ixyc=_simp(Ixy0-A*xb*yb)
    results={"A":A,"Qx":Qx,"Qy":Qy,"xbar":xb,"ybar":yb,"Ix_origin":Ix0,"Iy_origin":Iy0,"Ixy_origin":Ixy0,"Ix_centroid":Ixc,"Iy_centroid":Iyc,"Ixy_centroid":Ixyc,"J_origin":_simp(Ix0+Iy0),"J_centroid":_simp(Ixc+Iyc),"Ix_target":Ixt,"Iy_target":Iyt,"Ixy_target":Ixyt,"axis_x":axis_x,"axis_y":axis_y,"kx_centroid":_simp(sp.sqrt(Ixc/A)),"ky_centroid":_simp(sp.sqrt(Iyc/A))}
    return {"mode":"cartesian","setup":setup,"results":{k:_ser(v) for k,v in results.items()},"variables":{str(k):str(v) for k,v in sub.items()},"integrals":{"A":sp.latex(area_integral),"Ix":sp.latex(_simp(Ix0)),"Iy":sp.latex(_simp(Iy0))}}


def solve_polar(p: Dict[str, Any]) -> Dict[str, Any]:
    syms=_symbols((p.get("variables") or {}).keys()); th=syms["theta"]
    sub=_subs(p.get("variables") or {},syms,p.get("angle_variables_degrees") or [])
    t1=_expr(p.get("theta_min"),syms).subs(sub); t2=_expr(p.get("theta_max"),syms).subs(sub)
    ri=_expr(p.get("r_inner","0"),syms).subs(sub); ro=_expr(p.get("r_outer"),syms).subs(sub)
    ax=_expr(p.get("axis_x","0"),syms).subs(sub); ay=_expr(p.get("axis_y","0"),syms).subs(sub)
    r2=ro**2-ri**2; r3=ro**3-ri**3; r4=ro**4-ri**4
    A=_simp(sp.integrate(r2/2,(th,t1,t2))); Qy=_simp(sp.integrate(sp.cos(th)*r3/3,(th,t1,t2))); Qx=_simp(sp.integrate(sp.sin(th)*r3/3,(th,t1,t2)))
    if A==0: raise ValueError("極座標積分後面積為 0。")
    xb=_simp(Qy/A); yb=_simp(Qx/A)
    Ix0=_simp(sp.integrate(sp.sin(th)**2*r4/4,(th,t1,t2))); Iy0=_simp(sp.integrate(sp.cos(th)**2*r4/4,(th,t1,t2))); Ixy0=_simp(sp.integrate(sp.sin(th)*sp.cos(th)*r4/4,(th,t1,t2)))
    Ixc=_simp(Ix0-A*yb**2); Iyc=_simp(Iy0-A*xb**2); Ixyc=_simp(Ixy0-A*xb*yb)
    Ixt=_simp(Ix0-2*ay*Qx+ay**2*A); Iyt=_simp(Iy0-2*ax*Qy+ax**2*A); Ixyt=_simp(Ixy0-ax*Qx-ay*Qy+ax*ay*A)
    results={"A":A,"Qx":Qx,"Qy":Qy,"xbar":xb,"ybar":yb,"Ix_origin":Ix0,"Iy_origin":Iy0,"Ixy_origin":Ixy0,"Ix_centroid":Ixc,"Iy_centroid":Iyc,"Ixy_centroid":Ixyc,"J_origin":_simp(Ix0+Iy0),"J_centroid":_simp(Ixc+Iyc),"Ix_target":Ixt,"Iy_target":Iyt,"Ixy_target":Ixyt,"axis_x":ax,"axis_y":ay,"kx_centroid":_simp(sp.sqrt(Ixc/A)),"ky_centroid":_simp(sp.sqrt(Iyc/A))}
    return {"mode":"polar","setup":{"theta_min":sp.sstr(t1),"theta_max":sp.sstr(t2),"r_inner":sp.sstr(ri),"r_outer":sp.sstr(ro),"dA":"r dr dθ"},"results":{k:_ser(v) for k,v in results.items()},"variables":{str(k):str(v) for k,v in sub.items()},"integrals":{"A":sp.latex(sp.Integral(r2/2,(th,t1,t2))),"Ix":sp.latex(sp.Integral(sp.sin(th)**2*r4/4,(th,t1,t2))),"Iy":sp.latex(sp.Integral(sp.cos(th)**2*r4/4,(th,t1,t2)))}}


def solve_symbolic(p: Dict[str, Any]) -> Dict[str, Any]:
    mode=str(p.get("mode") or "").lower()
    if mode in {"cartesian","cartesian_vertical","cartesian_horizontal"}:
        q=dict(p)
        if mode=="cartesian_vertical": q["orientation"]="vertical"
        if mode=="cartesian_horizontal": q["orientation"]="horizontal"
        return solve_cartesian(q)
    if mode in {"polar","sector","polar_region"}: return solve_polar(p)
    raise ValueError(f"不支援符號模式：{mode}")


def self_test() -> bool:
    r=solve_cartesian({"mode":"cartesian","orientation":"horizontal","lower_bound":"-1","upper_bound":"1","left_function":"0","right_function":"1-y^2","variables":{},"axis_x":"0","axis_y":"0"})
    assert abs(r["results"]["A"]["numeric"]-4/3)<1e-10
    assert abs(r["results"]["Ix_origin"]["numeric"]-4/15)<1e-10
    assert abs(r["results"]["Iy_origin"]["numeric"]-32/105)<1e-10
    s=solve_polar({"mode":"polar","theta_min":"-alpha/2","theta_max":"alpha/2","r_inner":"0","r_outer":"r0","variables":{"alpha":None,"r0":None}})
    assert "alpha" in s["results"]["A"]["sympy"] and "r0" in s["results"]["A"]["sympy"]
    return True
