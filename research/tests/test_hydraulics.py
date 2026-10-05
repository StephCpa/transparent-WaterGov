import unittest
from copy import deepcopy
from transparent_eval.hydraulics import total_head, extract_section, exit_ratio


def section():
    # H=10-x. Rectangle width 2 and height 1. Right edge is explicitly selected.
    return {"unit_id":"ANALYTIC-U1","case_id":"ANALYTIC-LINEAR",
            "model_version":"manufactured-field-v1","crs":"local_x_z",
            "vertical_datum":"local_z_zero","source_ref":"analytic://H=10-x",
            "coordinate_units":"m","conductivity_units":"m/s","field_kind":"total_head_m",
            "nodes":[{"id":key,"x":x,"z":z,"value":10-x} for key,x,z in [("a",0,0),("b",2,0),("c",2,1),("d",0,1)]],
            "elements":[{"id":"t1","node_ids":["a","b","c"],"material_id":"sand","conductivity":[2e-5,0,2e-5]},
                        {"id":"t2","node_ids":["a","c","d"],"material_id":"sand","conductivity":[2e-5,0,2e-5]}],
            "exit_edges":[["b","c"]]}


class HydraulicsTests(unittest.TestCase):
    def test_head_conventions(self):
        self.assertAlmostEqual(total_head(19.62,3,"pore_pressure_kpa"),5)
        self.assertEqual(total_head(2,3,"pressure_head_m"),5)
        self.assertEqual(total_head(5,3,"total_head_m"),5)

    def test_exact_linear_gradient_flux_and_orientation(self):
        s=section()
        for reverse in (False,True):
            if reverse:
                for e in s["elements"]:e["node_ids"].reverse()
            out=extract_section(s)
            self.assertEqual(out["elements"]["t1"]["gradient"],[-1,0])
            self.assertEqual(out["exit_edges"][0]["outward_normal"],[1,0])
            self.assertAlmostEqual(out["selected_boundary_flux_m2_s"],2e-5)

    def test_hydrostatic_total_head_has_zero_flux(self):
        s=section();s["field_kind"]="pressure_head_m"
        for n in s["nodes"]:n["value"]=10-n["z"]
        out=extract_section(s)
        self.assertEqual(out["selected_boundary_flux_m2_s"],0)

    def test_head_datum_shift_preserves_gradient(self):
        s=section();a=extract_section(s)
        for n in s["nodes"]:n["z"]+=100;n["value"]+=100
        b=extract_section(s)
        self.assertEqual(a["elements"]["t1"]["gradient"],b["elements"]["t1"]["gradient"])
        self.assertEqual(a["exit_edges"][0]["pressure_heads_m"],b["exit_edges"][0]["pressure_heads_m"])

    def test_ratio_uncertainty_and_provenance(self):
        r=exit_ratio(extract_section(section()),[.5,1],"synthetic://limit",normal_criterion_confirmed=True)
        self.assertEqual(r["value"],[1,2]);self.assertEqual(r["peak_element"],"t1")

    def test_ratio_requires_applicability(self):
        with self.assertRaises(ValueError):exit_ratio(extract_section(section()),[1,1],"ref")

    def test_internal_or_duplicate_exit_rejected(self):
        for edges in ([["a","c"]],[["b","c"],["c","b"]]):
            s=section();s["exit_edges"]=edges
            with self.assertRaises(ValueError):extract_section(s)

    def test_anisotropy_not_silently_converted_to_normal_criterion(self):
        s=section();s["elements"][0]["conductivity"]=[2e-5,1e-6,1e-5]
        out=extract_section(s)
        self.assertAlmostEqual(out["elements"]["t1"]["darcy_flux"][1],1e-6)
        with self.assertRaises(ValueError):exit_ratio(out,[1,1],"ref",normal_criterion_confirmed=True)

    def test_no_cross_material_smoothing(self):
        s=section();s["elements"][1]["conductivity"]=[1e-6,0,1e-6]
        s["elements"][1]["material_id"]="silt"
        out=extract_section(s)
        self.assertAlmostEqual(out["elements"]["t1"]["darcy_flux"][0],2e-5)
        self.assertAlmostEqual(out["elements"]["t2"]["darcy_flux"][0],1e-6)

    def test_degenerate_triangle_rejected(self):
        s=section();s["nodes"][2]["z"]=0
        with self.assertRaises(ValueError):extract_section(s)

    def test_pressure_input_matches_total_head(self):
        s=section();a=extract_section(s)
        s["field_kind"]="pore_pressure_kpa"
        for n in s["nodes"]:n["value"]=(n["value"]-n["z"])*9.81
        b=extract_section(s)
        for x,y in zip(a["elements"]["t1"]["gradient"],b["elements"]["t1"]["gradient"]):self.assertAlmostEqual(x,y)

    def test_closed_boundary_linear_flux_balances(self):
        s=section();s["exit_edges"]=[["a","b"],["b","c"],["c","d"],["d","a"]]
        self.assertAlmostEqual(extract_section(s)["selected_boundary_flux_m2_s"],0)

    def test_layered_exact_solution_keeps_gradient_jump_and_flux_continuity(self):
        s=section();q=2/(1/1e-5+1/5e-5);middle=2-q/1e-5
        s["nodes"]=[{"id":f"{i}:{j}","x":i,"z":j,"value":[2,middle,0][i]} for i in range(3) for j in range(2)]
        s["elements"]=[]
        for i,k in [(0,1e-5),(1,5e-5)]:
            a,b,c,d=f"{i}:0",f"{i+1}:0",f"{i+1}:1",f"{i}:1"
            for suffix,ids in [("a",[a,b,c]),("b",[a,c,d])]:
                s["elements"].append({"id":f"{i}{suffix}","node_ids":ids,"material_id":f"layer{i}","conductivity":[k,0,k]})
        s["exit_edges"]=[["2:0","2:1"]]
        out=extract_section(s)
        for e in out["elements"].values():self.assertAlmostEqual(e["darcy_flux"][0],q)
        self.assertAlmostEqual(out["elements"]["0a"]["gradient"][0]/out["elements"]["1a"]["gradient"][0],5)


if __name__=="__main__":unittest.main()
