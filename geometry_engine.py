# -*- coding: utf-8 -*-
from __future__ import annotations

import math
from dataclasses import dataclass, asdict
from typing import Any, Dict, List, Sequence, Tuple


@dataclass
class PrimitiveResult:
    name: str
    kind: str
    sign: int
    area_abs: float
    area: float
    cx: float
    cy: float
    ixc_abs: float
    iyc_abs: float
    ixyc_abs: float
    ixc: float
    iyc: float
    ixyc: float
    source: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def _float(value: Any, label: str) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{label} 必須是數值。") from exc
    if not math.isfinite(result):
        raise ValueError(f"{label} 必須是有限數值。")
    return result


def _positive(value: Any, label: str) -> float:
    result = _float(value, label)
    if result <= 0:
        raise ValueError(f"{label} 必須大於 0。")
    return result


def rotate_centroidal_moments(ix: float, iy: float, ixy: float, angle_deg: float) -> Tuple[float, float, float]:
    theta = math.radians(angle_deg)
    c, s = math.cos(theta), math.sin(theta)
    ix_g = ix*c*c + iy*s*s + 2*ixy*s*c
    iy_g = iy*c*c + ix*s*s - 2*ixy*s*c
    ixy_g = (iy-ix)*s*c + ixy*(c*c-s*s)
    return ix_g, iy_g, ixy_g


def polygon_properties(vertices: Sequence[Sequence[float]]) -> Tuple[float, float, float, float, float, float]:
    if len(vertices) < 3:
        raise ValueError("多邊形至少需要 3 個頂點。")
    pts = [(_float(p[0], "頂點 x"), _float(p[1], "頂點 y")) for p in vertices]
    if pts[0] != pts[-1]:
        pts.append(pts[0])
    cs = cxs = cys = ixs = iys = ixys = 0.0
    for (x0, y0), (x1, y1) in zip(pts[:-1], pts[1:]):
        cr = x0*y1 - x1*y0
        cs += cr
        cxs += (x0+x1)*cr
        cys += (y0+y1)*cr
        ixs += (y0*y0+y0*y1+y1*y1)*cr
        iys += (x0*x0+x0*x1+x1*x1)*cr
        ixys += (2*x0*y0+x0*y1+x1*y0+2*x1*y1)*cr
    signed_area = cs/2
    if abs(signed_area) < 1e-12:
        raise ValueError("多邊形面積為 0。")
    cx = cxs/(6*signed_area)
    cy = cys/(6*signed_area)
    orientation = 1 if signed_area > 0 else -1
    area = abs(signed_area)
    ix0 = orientation*ixs/12
    iy0 = orientation*iys/12
    ixy0 = orientation*ixys/24
    return area, cx, cy, ix0-area*cy**2, iy0-area*cx**2, ixy0-area*cx*cy


def _sign(component: Dict[str, Any]) -> int:
    raw = component.get("sign", 1)
    if isinstance(raw, str):
        return -1 if raw.lower() in {"-1", "-", "hole", "void", "孔洞"} else 1
    return -1 if float(raw) < 0 else 1


def rectangle_result(c: Dict[str, Any], sign: int) -> PrimitiveResult:
    name = str(c.get("name") or "矩形")
    b, h = _positive(c.get("b"), f"{name} b"), _positive(c.get("h"), f"{name} h")
    cx, cy = _float(c.get("x", 0), f"{name} x"), _float(c.get("y", 0), f"{name} y")
    angle = _float(c.get("angle", 0), f"{name} angle")
    area = b*h
    ix, iy, ixy = rotate_centroidal_moments(b*h**3/12, h*b**3/12, 0, angle)
    return PrimitiveResult(name, "rectangle", sign, area, sign*area, cx, cy, ix, iy, ixy, sign*ix, sign*iy, sign*ixy, str(c.get("source") or ""))


def circle_result(c: Dict[str, Any], sign: int) -> PrimitiveResult:
    name = str(c.get("name") or "圓形")
    r = _positive(c.get("r") if c.get("r") is not None else float(c.get("d"))/2, f"{name} r")
    cx, cy = _float(c.get("x", 0), f"{name} x"), _float(c.get("y", 0), f"{name} y")
    area = math.pi*r*r
    ii = math.pi*r**4/4
    return PrimitiveResult(name, "circle", sign, area, sign*area, cx, cy, ii, ii, 0, sign*ii, sign*ii, 0, str(c.get("source") or ""))


def ellipse_result(c: Dict[str, Any], sign: int) -> PrimitiveResult:
    name = str(c.get("name") or "橢圓")
    a, b = _positive(c.get("a"), f"{name} a"), _positive(c.get("b"), f"{name} b")
    cx, cy = _float(c.get("x", 0), f"{name} x"), _float(c.get("y", 0), f"{name} y")
    angle = _float(c.get("angle", 0), f"{name} angle")
    area = math.pi*a*b
    ix, iy, ixy = rotate_centroidal_moments(math.pi*a*b**3/4, math.pi*a**3*b/4, 0, angle)
    return PrimitiveResult(name, "ellipse", sign, area, sign*area, cx, cy, ix, iy, ixy, sign*ix, sign*iy, sign*ixy, str(c.get("source") or ""))


def polygon_result(c: Dict[str, Any], sign: int) -> PrimitiveResult:
    name = str(c.get("name") or "多邊形")
    area, cx, cy, ix, iy, ixy = polygon_properties(c.get("vertices") or [])
    return PrimitiveResult(name, "polygon", sign, area, sign*area, cx, cy, ix, iy, ixy, sign*ix, sign*iy, sign*ixy, str(c.get("source") or ""))


def sector_result(c: Dict[str, Any], sign: int) -> PrimitiveResult:
    name = str(c.get("name") or "圓形扇形")
    ro = _positive(c.get("r_outer", c.get("r")), f"{name} r_outer")
    ri = _float(c.get("r_inner", 0), f"{name} r_inner")
    if ri < 0 or ri >= ro:
        raise ValueError(f"{name} 需滿足 0 ≤ r_inner < r_outer。")
    t1, t2 = _float(c.get("theta1"), f"{name} theta1"), _float(c.get("theta2"), f"{name} theta2")
    if str(c.get("angle_unit", "rad")).lower().startswith("deg"):
        t1, t2 = math.radians(t1), math.radians(t2)
    if t2 <= t1:
        raise ValueError(f"{name} 需滿足 theta2 > theta1。")
    x0, y0 = _float(c.get("center_x", 0), f"{name} center_x"), _float(c.get("center_y", 0), f"{name} center_y")
    dt, r2, r3, r4 = t2-t1, ro**2-ri**2, ro**3-ri**3, ro**4-ri**4
    area = 0.5*r2*dt
    cxr = (r3/3*(math.sin(t2)-math.sin(t1)))/area
    cyr = (r3/3*(-math.cos(t2)+math.cos(t1)))/area
    ix0 = r4/4*(dt/2-(math.sin(2*t2)-math.sin(2*t1))/4)
    iy0 = r4/4*(dt/2+(math.sin(2*t2)-math.sin(2*t1))/4)
    ixy0 = r4/8*(math.sin(t2)**2-math.sin(t1)**2)
    ix, iy, ixy = ix0-area*cyr**2, iy0-area*cxr**2, ixy0-area*cxr*cyr
    return PrimitiveResult(name, "circular_sector", sign, area, sign*area, x0+cxr, y0+cyr, ix, iy, ixy, sign*ix, sign*iy, sign*ixy, str(c.get("source") or ""))


def build_primitive(c: Dict[str, Any]) -> PrimitiveResult:
    kind = str(c.get("kind") or c.get("shape") or "").strip().lower()
    aliases = {
        "矩形":"rectangle", "rectangle":"rectangle", "圓形":"circle", "circle":"circle",
        "橢圓":"ellipse", "ellipse":"ellipse", "多邊形":"polygon", "polygon":"polygon",
        "三角形":"polygon", "triangle":"polygon", "梯形":"polygon", "trapezoid":"polygon",
        "圓形扇形":"circular_sector", "扇形":"circular_sector", "sector":"circular_sector", "circular_sector":"circular_sector",
    }
    kind = aliases.get(kind, kind)
    sign = _sign(c)
    if kind == "rectangle": return rectangle_result(c, sign)
    if kind == "circle": return circle_result(c, sign)
    if kind == "ellipse": return ellipse_result(c, sign)
    if kind == "polygon": return polygon_result(c, sign)
    if kind == "circular_sector": return sector_result(c, sign)
    raise ValueError(f"不支援的元件：{kind}")


def rotated_axis_moment(ix: float, iy: float, ixy: float, angle_deg: float) -> Dict[str, float]:
    t = math.radians(angle_deg); c, s = math.cos(t), math.sin(t)
    return {
        "Ix_theta": ix*c*c+iy*s*s-2*ixy*s*c,
        "Iy_theta": ix*s*s+iy*c*c+2*ixy*s*c,
        "Ixy_theta": (iy-ix)*s*c+ixy*(c*c-s*s),
    }


def solve_composite(components: Sequence[Dict[str, Any]], axis_x: float = 0.0, axis_y: float = 0.0, rotated_axis_angle_deg: float = 0.0) -> Dict[str, Any]:
    primitives = [build_primitive(c) for c in components]
    if not primitives: raise ValueError("沒有可計算元件。")
    area = sum(p.area for p in primitives)
    if area <= 1e-12: raise ValueError("總面積必須大於 0。")
    cx = sum(p.area*p.cx for p in primitives)/area
    cy = sum(p.area*p.cy for p in primitives)/area
    rows=[]; ixc=iyc=ixyc=ix0=iy0=ixy0=ixa=iya=0.0
    for p in primitives:
        dx, dy = p.cx-cx, p.cy-cy
        px = p.ixc+p.area*dy**2; py=p.iyc+p.area*dx**2; pxy=p.ixyc+p.area*dx*dy
        ixc+=px; iyc+=py; ixyc+=pxy
        ix0+=p.ixc+p.area*p.cy**2; iy0+=p.iyc+p.area*p.cx**2; ixy0+=p.ixyc+p.area*p.cx*p.cy
        ixa+=p.ixc+p.area*(p.cy-axis_y)**2; iya+=p.iyc+p.area*(p.cx-axis_x)**2
        rows.append({"名稱":p.name,"類型":p.kind,"性質":"實體" if p.sign==1 else "孔洞","A":p.area,"xᵢ":p.cx,"yᵢ":p.cy,"A·xᵢ":p.area*p.cx,"A·yᵢ":p.area*p.cy,"Ix,cᵢ":p.ixc,"Iy,cᵢ":p.iyc,"Ixy,cᵢ":p.ixyc,"Δx":dx,"Δy":dy,"AΔy²":p.area*dy**2,"AΔx²":p.area*dx**2,"AΔxΔy":p.area*dx*dy,"Ix' 貢獻":px,"Iy' 貢獻":py,"Ixy' 貢獻":pxy,"來源":p.source})
    rotated = rotated_axis_moment(ixc, iyc, ixyc, rotated_axis_angle_deg)
    return {"mode":"composite","A":area,"xbar":cx,"ybar":cy,"Ix_origin":ix0,"Iy_origin":iy0,"Ixy_origin":ixy0,"Ix_centroid":ixc,"Iy_centroid":iyc,"Ixy_centroid":ixyc,"J_origin":ix0+iy0,"J_centroid":ixc+iyc,"kx_centroid":math.sqrt(ixc/area),"ky_centroid":math.sqrt(iyc/area),"axis_x":axis_x,"axis_y":axis_y,"Ix_axis_y":ixa,"Iy_axis_x":iya,"rotated_axis_angle_deg":rotated_axis_angle_deg,**rotated,"rows":rows,"primitives":[p.to_dict() for p in primitives],"components":list(components)}


def self_test() -> bool:
    r=solve_composite([{"name":"R","kind":"rectangle","b":100,"h":50,"x":0,"y":0}])
    assert abs(r["A"]-5000)<1e-9
    assert abs(r["Ix_centroid"]-100*50**3/12)<1e-6
    t=solve_composite([{"name":"T","kind":"polygon","vertices":[[0,0],[300,0],[300,200]]}])
    assert abs(t["A"]-30000)<1e-6 and abs(t["xbar"]-200)<1e-6
    s=solve_composite([{"name":"Q","kind":"circular_sector","r_outer":1,"theta1":0,"theta2":math.pi/2}])
    assert abs(s["A"]-math.pi/4)<1e-9
    return True
