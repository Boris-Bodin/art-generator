"""Tests du modèle de formulaire de paramètres (ui.param_form), sans toolkit."""

from __future__ import annotations

import pytest

from art_generator.ui import param_form


def test_describe_infers_kinds():
    params = {"flag": True, "count": 3, "gain": 0.5, "label": "x"}
    kinds = {f.path[-1]: f.kind for f in param_form.describe(params)}
    # bool avant int : True ne doit pas être vu comme un entier.
    assert kinds == {"flag": "bool", "count": "int", "gain": "float", "label": "str"}


def test_describe_flattens_nested_dict_into_dotted_paths():
    params = {"emitter": {"type": "ring", "radius": 0.4}}
    by_label = {f.label: f for f in param_form.describe(params, family="particles")}
    assert set(by_label) == {"emitter.type", "emitter.radius"}
    assert by_label["emitter.type"].kind == "choice"
    assert by_label["emitter.type"].choices == ("point", "disk", "ring", "line")
    assert by_label["emitter.radius"].kind == "float"


def test_describe_uses_family_specific_choices():
    fractal = param_form.describe({"variant": "julia"}, family="fractal")[0]
    assert fractal.kind == "choice"
    assert fractal.choices == ("mandelbrot", "julia")
    attractor = param_form.describe({"variant": "clifford"}, family="attractor")[0]
    assert attractor.choices == ("clifford", "dejong", "custom")


def test_describe_falls_back_to_json_for_sequences():
    field = param_form.describe({"stops": [1, 2, 3]})[0]
    assert field.kind == "json"


def test_coerce_converts_by_kind():
    assert param_form.coerce("int", " 4 ") == 4
    assert param_form.coerce("float", "0.25") == 0.25
    assert param_form.coerce("bool", True) is True
    assert param_form.coerce("json", "[1, 2]") == [1, 2]
    assert param_form.coerce("str", "julia") == "julia"


def test_coerce_raises_on_invalid_number():
    with pytest.raises(ValueError):
        param_form.coerce("int", "abc")


def test_assemble_round_trips_through_describe():
    params = {
        "variant": "julia",
        "max_iter": 180,
        "cx": -0.4,
        "emitter": {"type": "disk", "radius": 0.3},
    }
    fields = param_form.describe(params, family="fractal")
    rebuilt = param_form.assemble(params, [(f.path, f.value) for f in fields])
    assert rebuilt == params


def test_assemble_preserves_untouched_keys():
    params = {"a": 1, "nested": {"keep": 2, "edit": 3}}
    rebuilt = param_form.assemble(params, [(("nested", "edit"), 9)])
    assert rebuilt == {"a": 1, "nested": {"keep": 2, "edit": 9}}
    assert params["nested"]["edit"] == 3  # l'original n'est pas muté
