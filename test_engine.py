from section_engine import InertiaCalculator, SectionComponent, self_test

assert self_test()

components = [
    SectionComponent(1, "腹板", "矩形", 1, 0, 70, 0, {"b": 20, "h": 140}),
    SectionComponent(2, "上翼板", "矩形", 1, 0, 150, 0, {"b": 140, "h": 20}),
    SectionComponent(3, "下翼板", "矩形", 1, 0, -10, 0, {"b": 90, "h": 20}),
    SectionComponent(4, "圓孔", "圓形", -1, 0, 65, 0, {"d": 30}),
]
result = InertiaCalculator.calculate(components)
assert result["A_total"] > 0
assert result["Ix_total"] > 0
assert result["Iy_total"] > 0
print("所有計算測試通過。")
