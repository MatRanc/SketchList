# Author-Mathieu
# Description-Lists every point, line and curve in the active sketch. Click one to select it.

# =============================================================================
# SketchList
#
# A small dockable palette that appears while you are editing a sketch and lists
# every entity in it (points, lines, arcs, circles, ...). Each row is labelled
# with an auto index and its coordinates; clicking a row selects that geometry
# in the viewport. The list refreshes itself as you draw or delete.
#
# Built from FusionAddinTemplate (palette + Python<->JS messaging scaffolding).
# Copyright (c) 2026 Mathieu. MIT licensed - see LICENSE-MIT.
# thomasa88lib (in ./thomasa88lib) is (c) 2020 Thomas Axelsson, MIT licensed.
# =============================================================================

import adsk.core
import adsk.fusion
import adsk.cam
import json
import os

NAME = 'Sketch List'
FILE_DIR = os.path.dirname(os.path.realpath(__file__))

from .thomasa88lib import utils
from .thomasa88lib import events
from .thomasa88lib import error
from .thomasa88lib import manifest
from .thomasa88lib import settings
from . import sketch_rows

import importlib
importlib.reload(utils)
importlib.reload(events)
importlib.reload(error)
importlib.reload(manifest)
importlib.reload(settings)
importlib.reload(sketch_rows)

# Unique IDs, prefixed so they never collide with other add-ins.
ID_PREFIX = 'sketchList_'
CMD_ID = ID_PREFIX + 'showPalette'
PALETTE_ID = ID_PREFIX + 'palette'
PANEL_ID = 'SolidScriptsAddinsPanel'  # The "ADD-INS" panel on the Design Solid tab.

app: adsk.core.Application = None
ui: adsk.core.UserInterface = None

error_catcher = error.ErrorCatcher(msgbox_in_debug=False)
events_manager = events.EventsManager(error_catcher)
manifest_data = manifest.read()

# id -> sketch entity, rebuilt on every scan. The HTML sends back the id of a
# clicked row and we look the entity up here to select it.
# ponytail: in-memory index, rebuilt each scan. Fine because we rescan on every
# command. Switch to entityToken only if rows must survive doc reloads.
current_entities = {}


# =============================================================================
# Lifecycle
# =============================================================================

def run(context):
    '''Called by Fusion when the add-in starts (Run, or on startup).'''
    global app, ui
    with error_catcher:
        app = adsk.core.Application.get()
        ui = app.userInterface

        _remove_ui()

        cmd_def = ui.commandDefinitions.addButtonDefinition(
            CMD_ID,
            'Toggle Sketch List',
            'Show or hide the list of entities in the active sketch.',
            'resources/command')
        events_manager.add_handler(cmd_def.commandCreated,
                                   callback=command_created_handler)

        panel = ui.allToolbarPanels.itemById(PANEL_ID)
        if panel and not panel.controls.itemById(CMD_ID):
            panel.controls.addCommand(cmd_def)

        # Auto show/hide and refresh the list as the user enters/leaves a sketch
        # and as they draw or delete geometry. commandTerminated fires after
        # every command, so a fresh line or a deletion shows up right away.
        events_manager.add_handler(ui.commandTerminated,
                                   callback=command_terminated_handler)

        print(f'{NAME} v{manifest_data["version"]} running')


def stop(context):
    '''Called by Fusion when the add-in stops. Tear down everything run() made.'''
    with error_catcher:
        events_manager.clean_up()
        _remove_ui()
        print(f'{NAME} stopped')


def _remove_ui():
    '''Delete the palette, control and command definition if they exist.'''
    palette = ui.palettes.itemById(PALETTE_ID)
    if palette:
        palette.deleteMe()

    panel = ui.allToolbarPanels.itemById(PANEL_ID)
    if panel:
        control = panel.controls.itemById(CMD_ID)
        if control:
            control.deleteMe()

    cmd_def = ui.commandDefinitions.itemById(CMD_ID)
    if cmd_def:
        cmd_def.deleteMe()


# =============================================================================
# Sketch reading
# =============================================================================

def get_active_sketch():
    '''The sketch currently being edited, or None.'''
    design = adsk.fusion.Design.cast(app.activeProduct)
    if not design:
        return None
    return adsk.fusion.Sketch.cast(design.activeEditObject)


def scan_sketch(sketch):
    '''Build the rows for the active sketch and refresh the id->entity map.

    Labelling/iteration lives in the adsk-free sketch_rows.build_rows so it can
    be unit-tested; here we just supply the Fusion units formatter.
    '''
    global current_entities
    um = adsk.fusion.Design.cast(app.activeProduct).unitsManager
    # Convert internal cm to the document's length unit and drop float noise
    # (round kills e-16 "zeros", 'g' trims trailing zeros) so a compact box reads
    # "2.5" not "2.5000000000000009".
    # ponytail: 4 decimals in doc units is plenty for sketch coords; bump if a
    # micron-scale design ever needs it.
    fmt = lambda v: format(round(um.convert(v, um.internalUnits, um.defaultLengthUnits), 4), 'g')
    rows, current_entities = sketch_rows.build_rows(sketch, fmt)
    return rows


# =============================================================================
# Palette (HTML UI)
# =============================================================================

def show_palette():
    '''Create the palette if needed, then make it visible.'''
    palette = ui.palettes.itemById(PALETTE_ID)
    if not palette:
        palette = ui.palettes.add(
            PALETTE_ID,
            'Sketch List',
            'palette.html',
            True,   # isVisible
            True,   # showCloseButton
            True,   # isResizable
            300,    # width  (~matches the Sketch Palette so it lines up under it)
            320,    # height
            True)   # useNewWebBrowser (modern Qt browser)
        # When it comes up floating (first run, or you left it floating), tuck it
        # flush-right directly under the Sketch Palette. If you've docked it to an
        # edge instead, Fusion restores that and we leave your placement alone.
        if palette.dockingState == adsk.core.PaletteDockingStates.PaletteDockStateFloating:
            _position_under_sketch_palette(palette, 300, 320)
        events_manager.add_handler(palette.incomingFromHTML,
                                   callback=palette_incoming_from_html_handler)
    else:
        palette.isVisible = True


def _position_under_sketch_palette(palette, w, h):
    '''Best-effort: tuck the floating box flush-right, directly under the Sketch
    Palette.

    setPosition is relative to the Fusion window's top-left. Fusion exposes no
    window size, no palette position, and no Sketch-Palette geometry, so these
    are estimates from the viewport plus fixed offsets.
    ponytail: hand-tuned constants — a sane default, not exact. It's draggable if
    it lands a bit off; say the word and I'll nudge the numbers.
    '''
    try:
        vp = app.activeViewport
        browser_w = 260              # left browser panel, approx
        top_bars = 130               # toolbar + tabs above the viewport, approx
        right_margin = 12            # match the Sketch Palette's gap from the edge
        sketch_palette_bottom = 560  # approx y of the Sketch Palette's lower edge
        window_w = browser_w + vp.width
        window_h = top_bars + vp.height
        x = max(0, window_w - w - right_margin)
        # Sit just under the palette, but never run off the bottom of the window.
        y = max(0, min(sketch_palette_bottom, window_h - h - 12))
        palette.setPosition(int(x), int(y))
    except Exception:
        pass  # positioning is cosmetic; never block showing the list


def _scan_rows():
    '''Rows for the active sketch, or [] when no sketch is open.'''
    sketch = get_active_sketch()
    return scan_sketch(sketch) if sketch else []


def refresh_palette():
    '''Push the current rows to the page (for live updates while editing).'''
    palette = ui.palettes.itemById(PALETTE_ID)
    if not palette or not palette.isVisible:
        return
    palette.sendInfoToHTML('setEntities', json.dumps({'rows': _scan_rows()}))


def palette_incoming_from_html_handler(args: adsk.core.HTMLEventArgs):
    '''Messages from palette.html.  'ready' -> first fill, 'select' -> pick.'''
    action = args.action
    data = json.loads(args.data) if args.data else {}

    if action == 'ready':
        # Return the rows directly. You must NOT call sendInfoToHTML from inside
        # an incomingFromHTML handler — Fusion drops it, which was the "open the
        # sketch twice before it fills" bug. The page renders from this reply.
        args.returnData = json.dumps({'rows': _scan_rows()})
    elif action == 'select':
        ent = current_entities.get(data.get('id'))
        if ent:
            col = adsk.core.ObjectCollection.create()
            # ponytail: direct add; a sketch is edited in its own context so no
            # createForAssemblyContext needed. Add it (see VerticalTimeline) only
            # if selecting in multi-instance component sketches misbehaves.
            col.add(ent)
            ui.activeSelections.all = col
        args.returnData = 'ok'


# =============================================================================
# Auto show / hide / refresh as the user moves in and out of sketches.
# =============================================================================

def command_terminated_handler(args):
    '''Fires after every command. Keep the palette in step with sketch edit mode.'''
    sketch = get_active_sketch()
    palette = ui.palettes.itemById(PALETTE_ID)
    if sketch:
        if not palette:
            show_palette()        # create + dock on first sketch entry
        elif not palette.isVisible:
            palette.isVisible = True
        refresh_palette()         # picks up anything just drawn or deleted
    elif palette and palette.isVisible:
        palette.isVisible = False  # left sketch edit -> hide
    # ponytail: no debounce — commandTerminated is low-frequency for sketch
    # edits. Add DirectName's deferred-scan pattern only if huge sketches lag.


# =============================================================================
# Command (toolbar button) — manual toggle, mirrors the auto behaviour.
# =============================================================================

def command_created_handler(args: adsk.core.CommandCreatedEventArgs):
    events_manager.add_handler(args.command.execute,
                               callback=command_execute_handler)


def command_execute_handler(args: adsk.core.CommandEventArgs):
    palette = ui.palettes.itemById(PALETTE_ID)
    if palette and palette.isVisible:
        palette.isVisible = False
    else:
        show_palette()
        refresh_palette()
