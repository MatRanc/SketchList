'''Pure sketch -> (rows, id->entity) logic.

No adsk imports, so it can be unit-tested with duck-typed fakes (see
test_sketch_rows.py). Everything Fusion-specific (units, selection) stays in
SketchList.py.
'''


def build_rows(sketch, fmt):
    '''Return (rows, entities).

    rows     : list of {'id': int, 'label': str} in display order.
    entities : dict id -> entity, aligned with rows by id (a clicked row's id
               looks the entity back up for selection).
    fmt      : callable(float) -> str, formats an internal-unit length.
    '''
    rows, entities = [], {}

    def pt(p):
        return f'({fmt(p.x)}, {fmt(p.y)})'

    def add(label, entity):
        i = len(entities)
        entities[i] = entity
        rows.append({'id': i, 'label': label})

    for i, p in enumerate(sketch.sketchPoints, 1):
        add(f'Point {i} — {pt(p.geometry)}', p)

    c = sketch.sketchCurves
    for i, l in enumerate(c.sketchLines, 1):
        add(f'Line {i} — {pt(l.startSketchPoint.geometry)}→{pt(l.endSketchPoint.geometry)}', l)
    for i, a in enumerate(c.sketchArcs, 1):
        add(f'Arc {i} — c{pt(a.centerSketchPoint.geometry)} r={fmt(a.radius)}', a)
    for i, cir in enumerate(c.sketchCircles, 1):
        add(f'Circle {i} — c{pt(cir.centerSketchPoint.geometry)} r={fmt(cir.radius)}', cir)
    for i, e in enumerate(c.sketchEllipses, 1):
        add(f'Ellipse {i} — c{pt(e.centerSketchPoint.geometry)}', e)
    for i, s in enumerate(c.sketchFittedSplines, 1):
        add(f'Spline {i}', s)
    for i, cp in enumerate(c.sketchControlPointSplines, 1):
        add(f'Spline (CP) {i}', cp)
    for i, cn in enumerate(c.sketchConicCurves, 1):
        add(f'Conic {i}', cn)

    return rows, entities
