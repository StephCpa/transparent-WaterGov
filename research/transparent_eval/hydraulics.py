"""Extract section-field evidence from explicit linear triangular elements.

This is a postprocessor, not a seepage solver. Coordinates are x,z in metres;
z increases upwards. Element conductivity is in m/s. No cross-material smoothing.
"""
from collections import defaultdict
from math import hypot
from .core import number, require_text, interval


def total_head(value, z, kind, gamma_water=9.81):
    value, z = number(value, "head/pressure"), number(z, "elevation")
    if kind == "total_head_m":
        return value
    if kind == "pressure_head_m":
        return value + z
    if kind == "pore_pressure_kpa":
        gamma_water = number(gamma_water, "water unit weight kN/m3")
        if gamma_water <= 0:
            raise ValueError("positive water unit weight required")
        return value / gamma_water + z
    raise ValueError("unknown head/pressure convention")


def extract_section(section):
    for field in ("unit_id", "case_id", "model_version", "crs", "vertical_datum", "source_ref"):
        require_text(section[field], field)
    if section["coordinate_units"] != "m" or section["conductivity_units"] != "m/s":
        raise ValueError("explicit SI coordinates and conductivity required")
    nodes = {}
    for row in section["nodes"]:
        key = row["id"]
        require_text(key, "node ID")
        if key in nodes:
            raise ValueError("duplicate node ID")
        x,z = number(row["x"],"x"),number(row["z"],"z")
        H = total_head(row["value"],z,section["field_kind"],section.get("gamma_water",9.81))
        nodes[key] = (x,z,H)
    elements, edges, shapes = {}, defaultdict(list), set()
    for element in section["elements"]:
        eid, ids = element["id"], element["node_ids"]
        require_text(eid,"element ID")
        require_text(element["material_id"],"material ID")
        if eid in elements or len(ids)!=3 or len(set(ids))!=3 or any(i not in nodes for i in ids):
            raise ValueError("invalid triangle IDs")
        shape=tuple(sorted(ids))
        if shape in shapes:
            raise ValueError("duplicate triangle geometry/connectivity")
        shapes.add(shape)
        a,b,c = [nodes[i] for i in ids]
        dx1,dz1,dx2,dz2=b[0]-a[0],b[1]-a[1],c[0]-a[0],c[1]-a[1]
        det=dx1*dz2-dx2*dz1
        scale=max(hypot(dx1,dz1),hypot(dx2,dz2),hypot(c[0]-b[0],c[1]-b[1]))
        if scale==0 or abs(det) <= 1e-12*scale*scale:
            raise ValueError("degenerate or severely ill-conditioned triangle")
        gx=((b[2]-a[2])*dz2-(c[2]-a[2])*dz1)/det
        gz=(dx1*(c[2]-a[2])-dx2*(b[2]-a[2]))/det
        k=element["conductivity"]
        if len(k)!=3:
            raise ValueError("conductivity must be [Kxx,Kxz,Kzz]")
        xx,xz,zz=[number(v,"conductivity") for v in k]
        if xx<=0 or zz<=0 or xx*zz-xz*xz<=0:
            raise ValueError("symmetric positive definite conductivity required")
        qx,qz=-(xx*gx+xz*gz),-(xz*gx+zz*gz)
        elements[eid]={"node_ids":ids,"material_id":element["material_id"],
                       "gradient":[gx,gz],"gradient_magnitude":hypot(gx,gz),
                       "darcy_flux":[qx,qz],"area_m2":abs(det)/2,
                       "isotropic":abs(xz)<=1e-12*max(xx,zz) and abs(xx-zz)<=1e-12*max(xx,zz)}
        for i,j in ((0,1),(1,2),(2,0)):
            edges[tuple(sorted([ids[i],ids[j]]))].append(eid)
    if not elements or any(len(v)>2 for v in edges.values()):
        raise ValueError("empty or non-manifold section")
    exits, seen = [], set()
    for edge in section["exit_edges"]:
        if len(edge)!=2:
            raise ValueError("two node IDs per boundary edge required")
        key=tuple(sorted(edge))
        if key in seen or len(edges.get(key,[]))!=1:
            raise ValueError("exit must be a unique external boundary edge")
        seen.add(key)
        eid=edges[key][0]; el=elements[eid]
        a,b=[nodes[i] for i in key]
        other=next(i for i in el["node_ids"] if i not in key)
        c=nodes[other]
        dx,dz=b[0]-a[0],b[1]-a[1]; length=hypot(dx,dz)
        nx,nz=dz/length,-dx/length
        # Flip if the candidate normal points toward the triangle interior.
        if nx*(c[0]-(a[0]+b[0])/2)+nz*(c[1]-(a[1]+b[1])/2)>0:
            nx,nz=-nx,-nz
        gx,gz=el["gradient"];qx,qz=el["darcy_flux"]
        exits.append({"node_ids":list(key),"element_id":eid,"material_id":el["material_id"],
                      "outward_normal":[nx,nz],"length_m":length,
                      "outward_head_gradient":-(gx*nx+gz*nz),
                      "gradient_magnitude":el["gradient_magnitude"],
                      "outward_darcy_flux_m_s":qx*nx+qz*nz,
                      "pressure_heads_m":[a[2]-a[1],b[2]-b[1]],"isotropic":el["isotropic"]})
    if not exits:
        raise ValueError("explicit exit-region selection required")
    return {**{k:section[k] for k in ("unit_id","case_id","model_version","source_ref","crs","vertical_datum")},
            "elements":elements,"exit_edges":exits,
            "selected_boundary_flux_m2_s":sum(e["outward_darcy_flux_m_s"]*e["length_m"] for e in exits),
            "interpretation":"piecewise-linear section postprocessing; not solver or engineering validation"}


def exit_ratio(extraction, allowable_interval, criterion_ref, *, normal_criterion_confirmed=False):
    """An opt-in ratio, only for an explicitly applicable normal-gradient criterion.

    Denominator uncertainty is propagated; discretization/head error is NOT included.
    """
    require_text(criterion_ref,"allowable-gradient reference")
    if normal_criterion_confirmed is not True:
        raise ValueError("normal-gradient criterion applicability must be established")
    lo,hi=interval(allowable_interval)
    if lo<=0:
        raise ValueError("allowable gradient must be positive")
    edges=extraction["exit_edges"]
    if any(not e["isotropic"] for e in edges):
        raise ValueError("anisotropic boundary requires an explicitly derived criterion")
    outward=[e for e in edges if e["outward_darcy_flux_m_s"]>0]
    if not outward:
        raise ValueError("selected region contains no outward seepage; do not substitute zero risk")
    peak=max(outward,key=lambda e:e["outward_head_gradient"])
    gradient=peak["outward_head_gradient"]
    return {"indicator_id":"exit_gradient_ratio","unit":"1",
            "value":[gradient/hi,gradient/lo],"criterion_ref":criterion_ref,
            "peak_edge":peak["node_ids"],"peak_element":peak["element_id"],
            "gradient":gradient,"allowable_interval":[lo,hi],
            "source_ref":extraction["source_ref"],
            "unit_id":extraction["unit_id"],"case_id":extraction["case_id"],
            "model_version":extraction["model_version"],
            "uncertainty_scope":"allowable-gradient interval only; field and mesh errors excluded"}
