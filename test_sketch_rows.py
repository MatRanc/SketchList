'''Self-check for sketch_rows.build_rows. No Fusion needed: run `python3 test_sketch_rows.py`.'''
import sketch_rows


class O:
    '''Duck-typed stand-in for any Fusion object (geometry, entity, collection).'''
    def __init__(self, **kw):
        self.__dict__.update(kw)


def demo():
    fmt = lambda v: f'{v:.2f}'
    pt = lambda x, y: O(geometry=O(x=x, y=y))
    line = O(startSketchPoint=pt(0, 0), endSketchPoint=pt(5, 2))

    sketch = O(
        sketchPoints=[pt(0, 0), pt(5, 2)],
        sketchCurves=O(
            sketchLines=[line],
            sketchArcs=[O(centerSketchPoint=pt(8, 0), radius=3)],
            sketchCircles=[], sketchEllipses=[], sketchFittedSplines=[],
            sketchControlPointSplines=[], sketchConicCurves=[],
        ),
    )

    rows, entities = sketch_rows.build_rows(sketch, fmt)

    assert [r['label'] for r in rows] == [
        'Point 1 — (0.00, 0.00)',
        'Point 2 — (5.00, 2.00)',
        'Line 1 — (0.00, 0.00)→(5.00, 2.00)',
        'Arc 1 — c(8.00, 0.00) r=3.00',
    ], rows

    # ids cover every row and map back to the real object a click would select.
    assert set(entities) == {r['id'] for r in rows}
    assert entities[2] is line, 'id 2 (third row) must be the line'
    print('ok')


if __name__ == '__main__':
    demo()
