from geometry_engine import self_test as geometry_test, solve_composite
from symbolic_engine import self_test as symbolic_test, solve_cartesian

assert geometry_test()
assert symbolic_test()

# 10-15/16: triangle + rectangle - circular hole
r = solve_composite([
    {"name":"左三角形","kind":"polygon","sign":1,"vertices":[[0,0],[300,0],[300,200]]},
    {"name":"右矩形","kind":"rectangle","sign":1,"b":300,"h":200,"x":450,"y":100},
    {"name":"圓孔","kind":"circle","sign":-1,"r":75,"x":450,"y":100},
])
assert r["A"] > 0 and r["Ix_origin"] > 0 and r["Iy_origin"] > 0

# 10-17: T section
r2 = solve_composite([
    {"name":"翼板","kind":"rectangle","sign":1,"b":150,"h":20,"x":0,"y":160},
    {"name":"腹板","kind":"rectangle","sign":1,"b":20,"h":150,"x":0,"y":75},
])
assert abs(r2["xbar"]) < 1e-9

# Earlier UI parabola y²=(b²/a)x, symmetric region 0 <= x <= a
r3 = solve_cartesian({
    "mode":"cartesian","orientation":"vertical",
    "lower_bound":"0","upper_bound":"a",
    "lower_function":"-b*sqrt(x/a)","upper_function":"b*sqrt(x/a)",
    "variables":{"a":None,"b":None},"axis_x":"0","axis_y":"0"
})
assert "a" in r3["results"]["A"]["sympy"] and "b" in r3["results"]["A"]["sympy"]

print("ALL TESTS PASSED")


from geometry_engine import (
    textbook_10_21_22_solution,
    validate_textbook_10_21_22,
)

textbook = textbook_10_21_22_solution()
validation = validate_textbook_10_21_22(textbook, relative_tolerance=1e-9)
assert validation["passed"]
assert abs(textbook["A"] - 15625.0) < 1e-9
assert abs(textbook["xbar"]) < 1e-9
assert abs(textbook["ybar"] - 22.5) < 1e-9
assert abs(textbook["Ix_centroid"] - 34.407552083333336e6) < 1e-5
assert abs(textbook["Iy_origin"] - 121.90755208333333e6) < 1e-5
print("textbook 10-21/22 benchmark: PASS")


from ai_service import _normalize, _extract_json

top_level_array = [
    {
        "problem_id": "10-21",
        "mode": "composite",
        "unit": "mm",
        "components": [],
    }
]
normalized = _normalize(top_level_array)
assert len(normalized["problems"]) == 1
assert normalized["problems"][0]["problem_id"] == "10-21"

nested_array = {
    "recognized_text": "test",
    "problems": [[
        {"problem_id": "10-21", "mode": "composite"},
        {"problem_id": "10-22", "mode": "composite"},
    ]],
}
normalized_nested = _normalize(nested_array)
assert len(normalized_nested["problems"]) == 2

single_problem_object = {
    "recognized_text": "test",
    "problem": {"problem_id": "10-9", "mode": "polar"},
}
normalized_single = _normalize(single_problem_object)
assert len(normalized_single["problems"]) == 1
assert normalized_single["problems"][0]["problem_id"] == "10-9"

parsed_array = _extract_json(
    '前置文字\\n[{"problem_id":"10-10","mode":"cartesian"}]\\n'
)
assert isinstance(parsed_array, list)
print("robust Gemini JSON schema parser: PASS")
