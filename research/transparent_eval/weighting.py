"""Small transparent weighting tools; no fitted engineering weights are supplied."""
from math import isclose, sqrt
from .core import number


def _simplex(weights):
    if not weights or any(number(w, "weight") < 0 for w in weights):
        raise ValueError("nonnegative finite weights required")
    if not isclose(sum(weights), 1, abs_tol=1e-10):
        raise ValueError("weights must sum to one")


def combine(subjective, objective, eta):
    _simplex(subjective)
    _simplex(objective)
    if len(subjective) != len(objective) or not 0 <= number(eta, "eta") <= 1:
        raise ValueError("incompatible weight vectors or invalid eta")
    return [eta*a + (1-eta)*b for a,b in zip(subjective, objective)]


def critic(response_rows, independent_group_ids):
    """CRITIC on fixed-anchor, adverse-oriented responses, not per-batch min/max.

    Returns a weighting candidate. This adaptation must be named in the method.
    One representative row per independent group is required here.
    """
    n = len(response_rows)
    if n < 3 or len(independent_group_ids) != n or len(set(independent_group_ids)) != n:
        raise ValueError("at least three distinct independent groups required for computation")
    if any(not g for g in independent_group_ids):
        raise ValueError("group IDs cannot be empty")
    p = len(response_rows[0])
    if p < 2 or any(len(row) != p for row in response_rows):
        raise ValueError("rectangular matrix with at least two indicators required")
    if any(not 0 <= number(x, "response") <= 1 for row in response_rows for x in row):
        raise ValueError("CRITIC input must already be normalized adverse response")
    cols = list(zip(*response_rows))
    centered = [[x-sum(col)/n for x in col] for col in cols]
    ss = [sum(x*x for x in col) for col in centered]
    active = [i for i,s in enumerate(ss) if s > 1e-15]
    info = [0.0]*p
    for i in active:
        conflict = 0.0
        for j in active:
            corr = sum(a*b for a,b in zip(centered[i], centered[j])) / sqrt(ss[i]*ss[j])
            conflict += 1-max(-1, min(1, corr))
        info[i] = sqrt(ss[i]/(n-1))*conflict
    if sum(info) <= 1e-12:
        raise ValueError("objective weights not identifiable: constant or redundant data")
    return {"weights": [v/sum(info) for v in info], "information": info,
            "constant_columns": [i for i in range(p) if i not in active],
            "n_independent_groups": n,
            "normalization": "fixed_anchor_adverse_response"}


def ahp(matrix, random_index=None, tolerance=1e-12, max_iterations=10000):
    """Principal-eigenvector AHP; RI is explicitly sourced by the caller."""
    n = len(matrix)
    if n < 2 or any(len(row) != n for row in matrix):
        raise ValueError("square comparison matrix of size >=2 required")
    for i in range(n):
        for j in range(n):
            a = number(matrix[i][j], "pairwise comparison")
            if a <= 0 or not isclose(a*matrix[j][i], 1, rel_tol=1e-9):
                raise ValueError("positive reciprocal comparison matrix required")
        if not isclose(matrix[i][i], 1, abs_tol=1e-12):
            raise ValueError("diagonal must equal one")
    w = [1/n]*n
    for iteration in range(max_iterations):
        aw = [sum(a*b for a,b in zip(row,w)) for row in matrix]
        new = [v/sum(aw) for v in aw]
        error = max(abs(a-b) for a,b in zip(new,w))
        w = new
        if error < tolerance:
            break
    else:
        raise ValueError("AHP iteration failed to converge")
    aw = [sum(a*b for a,b in zip(row,w)) for row in matrix]
    lam = sum(a/b for a,b in zip(aw,w))/n
    ci = max(0.0, (lam-n)/(n-1))
    if random_index is not None and number(random_index, "random_index") <= 0:
        raise ValueError("RI must be positive; omit for no consistency ratio")
    return {"weights": w, "lambda_max": lam, "consistency_index": ci,
            "consistency_ratio": ci/random_index if random_index is not None else None,
            "iterations": iteration+1}
