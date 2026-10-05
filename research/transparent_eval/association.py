"""Candidate association in an already registered linear levee reference.

No image geolocation, automatic event clustering or engineering confirmation.
Closed spatial intervals preserve ambiguous segment boundaries. Hydraulic time
windows are half-open and must be supplied by the upstream calculation owner.
"""
from .core import interval, require_text, timestamp


def associate(events, units, contexts, as_of):
    """Return one record per available event, retaining all candidate links.

    `event_id` identifies an immutable observation assertion, not an entire
    evolving incident. Repeated identical assertions collapse; conflicting IDs
    are rejected. Updates and resolutions require new assertion IDs upstream.
    """
    cutoff = timestamp(as_of)
    unit_map = {}
    for unit in units:
        uid = unit['unit_id']
        require_text(uid, 'unit_id')
        if uid in unit_map:
            raise ValueError('duplicate unit_id')
        for key in ('reference_id', 'geometry_version'):
            require_text(unit[key], key)
        bounds = interval(unit['chainage_m'])
        if bounds[0] == bounds[1]:
            raise ValueError('unit must have positive length')
        unit_map[uid] = (unit, bounds)

    context_map = {}
    for context in contexts:
        cid = context['context_id']
        require_text(cid, 'context_id')
        if cid in context_map:
            raise ValueError('duplicate context_id')
        if context['unit_id'] not in unit_map:
            raise ValueError('context references unknown unit')
        for key in ('model_version', 'basis_ref'):
            require_text(context[key], key)
        start, end = timestamp(context['valid_from']), timestamp(context['valid_to'])
        available = timestamp(context['available_at'])
        if end <= start:
            raise ValueError('empty context time window')
        context_map[cid] = (context, start, end, available)

    unique = {}
    for event in events:
        eid = event['event_id']
        require_text(eid, 'event_id')
        if eid in unique and unique[eid] != event:
            raise ValueError('conflicting immutable event_id')
        unique[eid] = event

    records, unavailable = [], []
    for eid, event in unique.items():
        observed = timestamp(event['observed_at'])
        received = timestamp(event['received_at'])
        if received < observed:
            raise ValueError('receipt precedes observation')
        if observed > cutoff or received > cutoff:
            unavailable.append(eid)
            continue
        for key in ('reference_id', 'geometry_version', 'source_ref'):
            require_text(event[key], key)
        location = interval(event['chainage_m'])
        links, candidates = [], []
        compatible = False
        for uid, (unit, bounds) in unit_map.items():
            if any(event[k] != unit[k] for k in ('reference_id', 'geometry_version')):
                continue
            compatible = True
            if location[0] <= bounds[1] and bounds[0] <= location[1]:
                candidates.append(uid)
                for cid, (ctx, start, end, available) in context_map.items():
                    if ctx['unit_id'] == uid and start <= observed < end and available <= cutoff:
                        links.append({'unit_id': uid, 'context_id': cid,
                                      'model_version': ctx['model_version'],
                                      'basis_ref': ctx['basis_ref']})
        candidates.sort()
        links.sort(key=lambda x: (x['unit_id'], x['context_id']))
        # One intersecting unit is insufficient if uncertainty extends beyond it.
        contained = len(candidates) == 1 and (
            unit_map[candidates[0]][1][0] <= location[0] <= location[1]
            <= unit_map[candidates[0]][1][1])
        if not compatible:
            status = 'reference_mismatch'
        elif not candidates:
            status = 'outside_units'
        elif not contained:
            status = 'spatial_ambiguity'
        elif not links:
            status = 'no_available_context'
        elif len(links) > 1:
            status = 'context_ambiguity'
        else:
            status = 'unique_candidate'
        records.append({'event_id': eid, 'observed_at': event['observed_at'],
                        'received_at': event['received_at'], 'source_ref': event['source_ref'],
                        'reference_id': event['reference_id'],
                        'geometry_version': event['geometry_version'],
                        'chainage_m': list(location), 'candidate_units': candidates,
                        'candidate_links': links, 'status': status})
    return {'as_of': as_of, 'records': sorted(records, key=lambda x: x['event_id']),
            'unavailable_event_ids': sorted(unavailable),
            'interpretation': 'candidate links only; no diagnosis or event multiplication'}
