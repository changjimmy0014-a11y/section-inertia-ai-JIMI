# -*- coding: utf-8 -*-
from __future__ import annotations

import math
from dataclasses import dataclass, asdict
from typing import Any, Dict, List, Tuple


SHAPE_PARAMS = {
    "矩形": ("b", "h"),
    "圓形": ("d",),
    "I 型鋼": ("B", "H", "tw", "tf"),
    "T 型截面": ("B", "H", "tw", "tf"),
    "中空矩形": ("B", "H", "b", "h"),
    "中空圓管": ("D", "d"),
}

SHAPE_ALIASES = {
    "rectangle": "矩形", "rect": "矩形", "矩形": "矩形",
    "circle": "圓形", "solid_circle": "圓形", "圓": "圓形", "圓形": "圓形",
    "i": "I 型鋼", "i_section": "I 型鋼", "i-beam": "I 型鋼",
    "i型鋼": "I 型鋼", "I型鋼": "I 型鋼", "I 型鋼": "I 型鋼",
    "t": "T 型截面", "t_section": "T 型截面",
    "t型": "T 型截面", "T型": "T 型截面", "T 型截面": "T 型截面",
    "hollow_rectangle": "中空矩形", "rectangular_tube": "中空矩形",
    "box": "中空矩形", "中空矩形": "中空矩形",
    "hollow_circle": "中空圓管", "circular_tube": "中空圓管",
    "pipe": "中空圓管", "中空圓管": "中空圓管",
}


@dataclass
class SectionComponent:
    cid: int
    name: str
    shape: str
    sign: int
    x: float
    y: float
    angle: float
    params: Dict[str, float]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @staticmethod
    def normalize_shape(shape: str) -> str:
        raw = str(shape).strip()
        return SHAPE_ALIASES.get(raw, SHAPE_ALIASES.get(raw.lower(), raw))

    @classmethod
    def from_ai_dict(cls, item: Dict[str, Any], cid: int) -> "SectionComponent":
        shape = cls.normalize_shape(item.get("shape", ""))
        sign_raw = item.get("sign", 1)
        if isinstance(sign_raw, str):
            sign = -1 if sign_raw.strip().lower() in {
                "-1", "-", "hole", "void", "cutout", "孔洞"
            } else 1
        else:
            sign = -1 if float(sign_raw) < 0 else 1

        params = {
            str(key): float(value)
            for key, value in (item.get("params") or {}).items()
            if value is not None and str(value).strip() != ""
        }
        comp = cls(
            cid=cid,
            name=str(item.get("name") or f"子截面 {cid}"),
            shape=shape,
            sign=sign,
            x=float(item.get("x", 0)),
            y=float(item.get("y", 0)),
            angle=float(item.get("angle", 0) or 0),
            params=params,
        )
        comp.validate()
        return comp

    def validate(self) -> None:
        if self.shape not in SHAPE_PARAMS:
            raise ValueError(f"不支援的截面類型：{self.shape}")
        if self.sign not in (1, -1):
            raise ValueError(f"{self.name}：性質必須為實體或孔洞。")

        for key in SHAPE_PARAMS[self.shape]:
            if key not in self.params:
                raise ValueError(f"{self.name} 缺少尺寸 {key}。")
            value = float(self.params[key])
            if not math.isfinite(value) or value <= 0:
                raise ValueError(f"{self.name} 的尺寸 {key} 必須大於 0。")

        p = self.params
        if self.shape == "I 型鋼":
            if p["tw"] >= p["B"] or 2 * p["tf"] >= p["H"]:
                raise ValueError(f"{self.name}：I 型鋼需滿足 tw < B 且 2tf < H。")
        elif self.shape == "T 型截面":
            if p["tw"] >= p["B"] or p["tf"] >= p["H"]:
                raise ValueError(f"{self.name}：T 型截面需滿足 tw < B 且 tf < H。")
        elif self.shape == "中空矩形":
            if p["b"] >= p["B"] or p["h"] >= p["H"]:
                raise ValueError(f"{self.name}：內寬、內高必須小於外寬、外高。")
        elif self.shape == "中空圓管" and p["d"] >= p["D"]:
            raise ValueError(f"{self.name}：內徑 d 必須小於外徑 D。")

    def area_and_centroidal_inertia(self) -> Tuple[float, float, float, str]:
        self.validate()
        p = self.params

        if self.shape == "矩形":
            b, h = p["b"], p["h"]
            area = b * h
            ix = b * h**3 / 12
            iy = h * b**3 / 12
            formula = (
                f"A=bh={b:g}×{h:g}={area:.8g}；"
                f"Ix,c=bh³/12={ix:.8g}；Iy,c=hb³/12={iy:.8g}"
            )

        elif self.shape == "圓形":
            d = p["d"]
            area = math.pi * d**2 / 4
            ix = iy = math.pi * d**4 / 64
            formula = f"A=πd²/4={area:.8g}；Ix,c=Iy,c=πd⁴/64={ix:.8g}"

        elif self.shape == "I 型鋼":
            B, H, tw, tf = p["B"], p["H"], p["tw"], p["tf"]
            hw = H - 2 * tf
            af = B * tf
            aw = tw * hw
            area = 2 * af + aw
            df = H / 2 - tf / 2
            ix = 2 * (B * tf**3 / 12 + af * df**2) + tw * hw**3 / 12
            iy = 2 * (tf * B**3 / 12) + hw * tw**3 / 12
            formula = (
                f"A=2Btf+tw(H−2tf)={area:.8g}；"
                f"Ix,c=2[Btf³/12+(Btf)({df:.8g})²]+tw(H−2tf)³/12={ix:.8g}；"
                f"Iy,c=2(tfB³/12)+(H−2tf)tw³/12={iy:.8g}"
            )

        elif self.shape == "T 型截面":
            B, H, tw, tf = p["B"], p["H"], p["tw"], p["tf"]
            hw = H - tf
            af, aw = B * tf, tw * hw
            area = af + aw
            yf, yw = H - tf / 2, hw / 2
            y_local = (af * yf + aw * yw) / area
            ix = (
                B * tf**3 / 12 + af * (yf - y_local)**2
                + tw * hw**3 / 12 + aw * (yw - y_local)**2
            )
            iy = tf * B**3 / 12 + hw * tw**3 / 12
            formula = (
                f"A=Btf+tw(H−tf)={area:.8g}；"
                f"截面自身形心距底部={y_local:.8g}；"
                f"Ix,c=Σ(I0+AΔy²)={ix:.8g}；Iy,c={iy:.8g}"
            )

        elif self.shape == "中空矩形":
            B, H, b, h = p["B"], p["H"], p["b"], p["h"]
            area = B * H - b * h
            ix = (B * H**3 - b * h**3) / 12
            iy = (H * B**3 - h * b**3) / 12
            formula = (
                f"A=BH−bh={area:.8g}；"
                f"Ix,c=(BH³−bh³)/12={ix:.8g}；"
                f"Iy,c=(HB³−hb³)/12={iy:.8g}"
            )

        elif self.shape == "中空圓管":
            D, d = p["D"], p["d"]
            area = math.pi * (D**2 - d**2) / 4
            ix = iy = math.pi * (D**4 - d**4) / 64
            formula = (
                f"A=π(D²−d²)/4={area:.8g}；"
                f"Ix,c=Iy,c=π(D⁴−d⁴)/64={ix:.8g}"
            )

        else:
            raise ValueError("未知截面類型。")

        return area, ix, iy, formula

    def rotated_centroidal_inertia(self) -> Tuple[float, float]:
        _, ix, iy, _ = self.area_and_centroidal_inertia()
        theta = math.radians(self.angle)
        average = (ix + iy) / 2
        difference = (ix - iy) / 2
        return (
            average + difference * math.cos(2 * theta),
            average - difference * math.cos(2 * theta),
        )


class InertiaCalculator:
    @staticmethod
    def calculate(components: List[SectionComponent]) -> Dict[str, Any]:
        if not components:
            raise ValueError("請先建立至少一個子截面。")

        base = []
        total_area = total_ax = total_ay = 0.0

        for comp in components:
            area, ixc, iyc, formula = comp.area_and_centroidal_inertia()
            ixc_rot, iyc_rot = comp.rotated_centroidal_inertia()
            signed_area = comp.sign * area
            total_area += signed_area
            total_ax += signed_area * comp.x
            total_ay += signed_area * comp.y
            base.append((comp, area, signed_area, ixc, iyc, ixc_rot, iyc_rot, formula))

        if total_area <= 1e-12:
            raise ValueError("組合後總面積必須大於 0，請檢查孔洞與尺寸。")

        xbar = total_ax / total_area
        ybar = total_ay / total_area
        total_ix = total_iy = 0.0
        rows = []

        for comp, area, signed_area, ixc, iyc, ixc_rot, iyc_rot, formula in base:
            dx = comp.x - xbar
            dy = comp.y - ybar
            signed_ixc = comp.sign * ixc_rot
            signed_iyc = comp.sign * iyc_rot
            parallel_ix = signed_area * dy**2
            parallel_iy = signed_area * dx**2
            ix_part = signed_ixc + parallel_ix
            iy_part = signed_iyc + parallel_iy
            total_ix += ix_part
            total_iy += iy_part

            rows.append({
                "編號": comp.cid,
                "名稱": comp.name,
                "類型": comp.shape,
                "性質": "實體" if comp.sign == 1 else "孔洞",
                "A": area,
                "±A": signed_area,
                "xi": comp.x,
                "yi": comp.y,
                "±Axi": signed_area * comp.x,
                "±Ayi": signed_area * comp.y,
                "±Ix,c(θ)": signed_ixc,
                "±Iy,c(θ)": signed_iyc,
                "Δx": dx,
                "Δy": dy,
                "±AΔy²": parallel_ix,
                "±AΔx²": parallel_iy,
                "Ix,i": ix_part,
                "Iy,i": iy_part,
                "公式": formula,
            })

        if total_ix <= 0 or total_iy <= 0:
            raise ValueError("計算後 Ix 或 Iy 不為正，請檢查孔洞是否超出實體。")

        return {
            "A_total": total_area,
            "xbar": xbar,
            "ybar": ybar,
            "Ix_total": total_ix,
            "Iy_total": total_iy,
            "kx": math.sqrt(total_ix / total_area),
            "ky": math.sqrt(total_iy / total_area),
            "rows": rows,
        }


def format_number(value: float) -> str:
    value = float(value)
    if value == 0:
        return "0"
    if abs(value) >= 1e6 or abs(value) < 1e-3:
        return f"{value:.6e}"
    return f"{value:.6f}".rstrip("0").rstrip(".")


def build_teaching_text(result: Dict[str, Any], unit: str = "mm") -> str:
    rows = result["rows"]
    lines = ["## 步驟 1：各子截面的面積與自身形心慣性矩"]
    for row in rows:
        lines.extend([
            f"\n### #{row['編號']} {row['名稱']}（{row['性質']}，{row['類型']}）",
            row["公式"],
        ])

    area_terms = " + ".join(f"({format_number(row['±A'])})" for row in rows)
    ax_terms = " + ".join(f"({format_number(row['±Axi'])})" for row in rows)
    ay_terms = " + ".join(f"({format_number(row['±Ayi'])})" for row in rows)

    lines.extend([
        "\n## 步驟 2：求組合截面形心",
        f"**A = Σ(±Ai) = {area_terms} = {format_number(result['A_total'])} {unit}²**",
        f"**x̄ = Σ(±Ai·xi)/A = [{ax_terms}]/{format_number(result['A_total'])}"
        f" = {format_number(result['xbar'])} {unit}**",
        f"**ȳ = Σ(±Ai·yi)/A = [{ay_terms}]/{format_number(result['A_total'])}"
        f" = {format_number(result['ybar'])} {unit}**",
        "\n## 步驟 3：平行軸定理求 Ix",
        "**Ix = Σ ±[Ix,c(θ) + Ai(yi−ȳ)²]**",
    ])
    for row in rows:
        lines.append(
            f"- #{row['編號']}：Ix,i = ({format_number(row['±Ix,c(θ)'])})"
            f" + ({format_number(row['±AΔy²'])})"
            f" = {format_number(row['Ix,i'])} {unit}⁴"
        )
    ix_terms = " + ".join(f"({format_number(row['Ix,i'])})" for row in rows)
    lines.append(f"**Ix = {ix_terms} = {format_number(result['Ix_total'])} {unit}⁴**")

    lines.extend([
        "\n## 步驟 4：平行軸定理求 Iy",
        "**Iy = Σ ±[Iy,c(θ) + Ai(xi−x̄)²]**",
    ])
    for row in rows:
        lines.append(
            f"- #{row['編號']}：Iy,i = ({format_number(row['±Iy,c(θ)'])})"
            f" + ({format_number(row['±AΔx²'])})"
            f" = {format_number(row['Iy,i'])} {unit}⁴"
        )
    iy_terms = " + ".join(f"({format_number(row['Iy,i'])})" for row in rows)
    lines.append(f"**Iy = {iy_terms} = {format_number(result['Iy_total'])} {unit}⁴**")

    lines.extend([
        "\n## 步驟 5：轉動半徑",
        f"**kx = √(Ix/A) = {format_number(result['kx'])} {unit}**",
        f"**ky = √(Iy/A) = {format_number(result['ky'])} {unit}**",
        "\n## 驗算提醒",
        "- Ix 的平行軸距離使用垂直距離 Δy；Iy 使用水平距離 Δx。",
        "- 孔洞的面積、一次矩、自身慣性矩與平行軸項都要以負號扣除。",
        "- 面積單位是長度²，面積慣性矩單位是長度⁴，轉動半徑單位是長度。",
    ])
    return "\n\n".join(lines)


def self_test() -> bool:
    rect = SectionComponent(1, "矩形", "矩形", 1, 0, 0, 0, {"b": 100, "h": 50})
    result = InertiaCalculator.calculate([rect])
    assert abs(result["A_total"] - 5000) < 1e-8
    assert abs(result["Ix_total"] - 100 * 50**3 / 12) < 1e-6
    assert abs(result["Iy_total"] - 50 * 100**3 / 12) < 1e-6

    upper = SectionComponent(1, "上", "矩形", 1, 0, 30, 0, {"b": 20, "h": 10})
    lower = SectionComponent(2, "下", "矩形", 1, 0, -30, 0, {"b": 20, "h": 10})
    symmetric = InertiaCalculator.calculate([upper, lower])
    assert abs(symmetric["ybar"]) < 1e-12

    plate = SectionComponent(1, "板", "矩形", 1, 0, 0, 0, {"b": 100, "h": 100})
    hole = SectionComponent(2, "孔", "圓形", -1, 0, 0, 0, {"d": 20})
    perforated = InertiaCalculator.calculate([plate, hole])
    assert perforated["A_total"] > 0
    return True
