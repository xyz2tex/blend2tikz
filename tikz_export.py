#!BPY
"""
Name: 'TikZ (.tex)...'
Blender: 245
Group: 'Export'
Tooltip: 'Export selected curves as TikZ paths for use with (La)TeX'
"""

__author__ = 'Kjell Magne Fauske'
__version__ = "1.0"
__url__ = ("Documentation, http://www.fauskes.net/code/blend2tikz/documentation/",
           "Author's homepage, http://www.fauskes.net/",
           "TikZ examples, http://www.fauskes.net/pgftikzexamples/")

__bpydoc__ = """\
This script exports selected curves and empties to TikZ format for use with TeX.
PGF and TikZ is a powerful macro package for creating high quality illustrations
and graphics for use with (La|Con)TeX.

Important: TikZ is primarily for creating 2D illustrations. This script will
therefore only export the X and Y coordinates. However, the Z coordinate is used
to determine draw order. 

Usage:

Select the objects you want to export and invoke the script from the
"File->Export" menu[1]. Alternatively you can load and run the script from
inside Blender.

A dialog box will pop up with various options:<br>

    - Draw: Insert a draw operation in the generated path.<br>
    - Fill: Insert a fill operation in the generated path.<br>
    - Transform: Apply translation and scale transformations.<br>
    - Materials: Export materials assigned to curves.<br>
    - Empties: Export empties as named coordinates.<br>
    - Only properties: Use on the style property of materials if set.<br>
    - Standalone: Create a standalone document.<br>
    - Only code: Generate only code for drawing paths.<br>
    - Clipboard: Copy generated code to the clipboard. <br>

Properties:

If an object is assigned a ID property or game property named 'style' of type
string, its value will be added to the path as an option. You can use the
Help->Property ID browser to set this value, or use the Logic panel to
add a game property. 

Materials:

The exporter has basic support for materials. By default the material's RGB
value is used as fill or draw color. You can also set the alpha value for
transparency effects.

An alternative is to specify style options
directly by putting the values in a 'style' property assigned to the material.
You can use the Help->Property ID browser to set this value.

Issues:<br>

- Only bezier and polyline curves are supported.<br>
- A full Python install is required for clipboard support on Windows. Other platforms
need the standard subprocess module (requires Python 2.4 or later). Additionally:<br>
    * Windows users need to install the PyWin32 module.<br>
    * Unix-like users need the xclip command line tool or the PyGTK_ module installed.<br>
    * OS X users need the pbcopy command line tool installed.<br>

[1] Requires you to put the script in Blender's scripts folder. Blender will
then automatically detect the script.
"""

import Blender
from Blender import sys as bsys
from itertools import izip
import itertools, math
from Blender import Mesh, Mathutils, Registry, Scene, Material, Group
from textwrap import wrap

from string import Template

# Curve types
TYPE_POLY = 0
TYPE_BEZIER = 1
TYPE_NURBS = 4

R2D = 180.0 / math.pi

# Start of configuration section -------

# Templates
standalone_template = r"""
\documentclass{article}
\usepackage{tikz}
%(preamble)s
%(materials)s
\begin{document}
\begin{tikzpicture}
%(pathcode)s
\end{tikzpicture}
\end{document}
"""

fig_template = r"""
%(materials)s
\begin{tikzpicture}
%(pathcode)s
\end{tikzpicture}
"""

REG_KEY = 'tikz_export'

# config options:

STANDALONE = True
CODE_ONLY = False
DRAW_CURVE = True
FILL_CLOSED_CURVE = True
TRANSFORM_CURVE = True
CLIPBOARD_OUTPUT = False
EMPTIES = True
EXPORT_MATERIALS = False
ONLY_PROPERTIES = False
USE_PLOTPATH = False
WRAP_LINES = True

tooltips = {
    'STANDALONE': 'Output a standalone document',
    'DRAW_CURVE':
        'Draw curves',
    'FILL_CLOSED_CURVE':
        'Fill closed curves',
    'TRANSFORM_CURVE':
        'Apply transformations',
    'CLIPBOARD_OUTPUT':
        'Put generated code on clipboard',
    'CODE_ONLY':
        'Output pathcode only',
    'EMPTIES': 'Export empties',
    'EXPORT_MATERIALS': 'Apply materials to curves',
    'ONLY_PROPERTIES':
        'Use only properties for materials with the style property set',
    'USE_PLOTPATH':
        'Use the plot path operations for polylines',
    'WRAP_LINES':
        'Wrap long lines',
}


def update_registry():
    d = {
        'STANDALONE': STANDALONE,
        'DRAW_CURVE': DRAW_CURVE,
        'FILL_CLOSED_CURVE': FILL_CLOSED_CURVE,
        'TRANSFORM_CURVE': TRANSFORM_CURVE,
        'CLIPBOARD_OUTPUT': CLIPBOARD_OUTPUT,
        'CODE_ONLY': CODE_ONLY,
        'EMPTIES': EMPTIES,
        'EXPORT_MATERIALS': EXPORT_MATERIALS,
        'ONLY_PROPERTIES': ONLY_PROPERTIES,
        'USE_PLOTPATH': USE_PLOTPATH,
        'WRAP_LINES': WRAP_LINES,
    }
    Registry.SetKey(REG_KEY, d, True)

# Looking for a saved key in Blender.Registry dict:
rd = Registry.GetKey(REG_KEY, True)

if rd:
    try:
        STANDALONE = rd['STANDALONE']
        DRAW_CURVE = rd['DRAW_CURVE']
        FILL_CLOSED_CURVE = rd['FILL_CLOSED_CURVE']
        TRANSFORM_CURVE = rd['TRANSFORM_CURVE']
        CLIPBOARD_OUTPUT = rd['CLIPBOARD_OUTPUT']
        CODE_ONLY = rd['CODE_ONLY']
        EMPTIES = rd['EMPTIES']
        EXPORT_MATERIALS = rd['EXPORT_MATERIALS']
        ONLY_PROPERTIES = rd['ONLY_PROPERTIES']
        USE_PLOTPATH = rd['USE_PLOTPATH']
        WRAP_LINES = rd['WRAP_LINES']
    except KeyError:
        print "Keyerror"
        update_registry()
else:
    print "update registry"
    update_registry()

# Start of GUI section ------------------------------------------------

from Blender import Draw


def draw_GUI():
    global STANDALONE, DRAW_CURVE, FILL_CLOSED_CURVE, TRANSFORM_CURVE
    global CLIPBOARD_OUTPUT, CODE_ONLY, EMPTIES, EXPORT_MATERIALS
    global ONLY_PROPERTIES
    global USE_PLOTPATH
    global WRAP_LINES

    standalonetog = Draw.Create(STANDALONE)
    codeonlytog = Draw.Create(CODE_ONLY)
    drawcurvetog = Draw.Create(DRAW_CURVE)
    fillcurvetog = Draw.Create(FILL_CLOSED_CURVE)
    transformcurvetog = Draw.Create(TRANSFORM_CURVE)
    clipboardtog = Draw.Create(CLIPBOARD_OUTPUT)
    emptiestog = Draw.Create(EMPTIES)
    materialstog = Draw.Create(EXPORT_MATERIALS)
    onlyproptog = Draw.Create(ONLY_PROPERTIES)
    useplotpathtog = Draw.Create(USE_PLOTPATH)
    wraplinestog = Draw.Create(WRAP_LINES)
    block = []

    #block.append("Export:")
    block.append(("Draw", drawcurvetog, tooltips['DRAW_CURVE']))
    block.append(("Fill", fillcurvetog, tooltips['FILL_CLOSED_CURVE']))
    block.append(("Transform", transformcurvetog, tooltips['TRANSFORM_CURVE']))
    block.append(("Use plot path", useplotpathtog, tooltips['USE_PLOTPATH']))

    block.append("Export:")
    block.append(("Materials", materialstog, tooltips['EXPORT_MATERIALS']))
    block.append(("Empties", emptiestog, tooltips['EMPTIES']))
    block.append("Material options:")
    block.append(("Only properties", onlyproptog, tooltips['ONLY_PROPERTIES']))
    block.append('Ouput options')
    block.append(("Standalone", standalonetog, tooltips['STANDALONE']))
    block.append(("Only code", codeonlytog, tooltips['CODE_ONLY']))
    block.append(("Clipboard", clipboardtog, tooltips['CLIPBOARD_OUTPUT']))
    block.append(("Wrap lines", wraplinestog, tooltips['WRAP_LINES']))

    retval = Blender.Draw.PupBlock("Blend2TikZ options", block)
    if retval:
        # set options
        STANDALONE = standalonetog.val
        DRAW_CURVE = drawcurvetog.val
        FILL_CLOSED_CURVE = fillcurvetog.val
        TRANSFORM_CURVE = transformcurvetog.val
        CLIPBOARD_OUTPUT = clipboardtog.val
        CODE_ONLY = codeonlytog.val
        EMPTIES = emptiestog.val
        EXPORT_MATERIALS = materialstog.val
        ONLY_PROPERTIES = onlyproptog.val
        USE_PLOTPATH = useplotpathtog.val
        WRAP_LINES = wraplinestog.val
        update_registry()
    return retval


# End of GUI section ----------------------

# End of configuration section ---------
X = 0
Y = 1

used_materials = {}

# Utility functions

def nsplit(seq, n=2):
    """Split a sequence into pieces of length n

    If the lengt of the sequence isn't a multiple of n, the rest is discareded.
    Note that nsplit will strings into individual characters.

    Examples:
    >>> nsplit('aabbcc')
    [('a', 'a'), ('b', 'b'), ('c', 'c')]
    >>> nsplit('aabbcc',n=3)
    [('a', 'a', 'b'), ('b', 'c', 'c')]

    # Note that cc is discarded
    >>> nsplit('aabbcc',n=4)
    [('a', 'a', 'b', 'b')]
    """
    return [xy for xy in izip(*[iter(seq)] * n)]


def mreplace(s, chararray, newchararray):
    for a, b in zip(chararray, newchararray):
        s = s.replace(a, b)
    return s


def tikzify(s):
    if s.strip():
        return mreplace(s, r'\,:.', '-+_*')
    else:
        return ""


def copy_to_clipboard(text):
    """Copy text to the clipboard

    Returns True if successful. False otherwise.

    Works on Windows, *nix and Mac. Tries the following:
    1. Use the win32clipboard module from the win32 package.
    2. Calls the xclip command line tool (*nix)
    3. Calls the pbcopy command line tool (Mac)
    4. Try pygtk
    """
    # try windows first
    try:
        import win32clipboard

        win32clipboard.OpenClipboard()
        win32clipboard.EmptyClipboard()
        win32clipboard.SetClipboardText(text)
        win32clipboard.CloseClipboard()
        return True
    except:
        pass
    # try xclip
    try:
        import subprocess

        p = subprocess.Popen(['xclip', '-selection', 'c'], stdin=subprocess.PIPE)
        p.stdin.write(text)
        p.stdin.close()
        retcode = p.wait()
        return True
    except:
        pass
    # try pbcopy (Os X)
    try:
        import subprocess

        p = subprocess.Popen(['pbcopy'], stdin=subprocess.PIPE)
        p.stdin.write(text)
        p.stdin.close()
        retcode = p.wait()
        return True
    except:
        pass
    # try os /linux
    try:
        import subprocess

        p = subprocess.Popen(['xsel'], stdin=subprocess.PIPE)
        p.stdin.write(text)
        p.stdin.close()
        retcode = p.wait()
        return True
    except:
        pass
    # try pygtk
    try:
        # Code from
        # http://www.vector-seven.com/2007/06/27/
        #    passing-data-between-gtk-applications-with-gtkclipboard/
        import pygtk

        pygtk.require('2.0')
        import gtk
        # get the clipboard
        clipboard = gtk.clipboard_get()
        # set the clipboard text data
        clipboard.set_text(text)
        # make our data available to other applications
        clipboard.store()
    except:
        return False


def get_property(obj, name):
    """Get named object property
    
    Looks first in custom properties, then game properties. Returns a list.
    """
    prop_value = []
    try:
        prop_value.append(obj.properties[name])
    except:
        pass
    try:
        # look for game properties
        prop = obj.getProperty(name)
        if prop.type == "STRING" and prop.data.strip():
            prop_value.append(prop.data)
    except:
        pass
    return prop_value


def get_material(material):
    """Convert material to TikZ options"""
    if not material:
        return ""
    opts = ""
    mat_name = tikzify(material.name)
    used_materials[mat_name] = material
    return mat_name


def write_materials(used_materials):
    """Return code for the used materials"""
    c = "% Materials section \n"
    for material in used_materials.values():
        mat_name = tikzify(material.name)
        matopts = ''
        proponly = ONLY_PROPERTIES
        try:
            proponly = material.properties['onlyproperties']
            if proponly and type(proponly) == str:
                proponly = proponly.lower() not in ('0', 'false')
        except:
            pass
        try:
            matopts = material.properties['style']
        except:
            pass

        rgb = material.rgbCol
        spec = material.specCol
        alpha = material.alpha
        flags = material.getMode()
        options = []

        if not (proponly and matopts):
            c += "\\definecolor{%s_col}{rgb}{%s,%s,%s}\n" \
                 % tuple([mat_name] + rgb)
            options.append('%s_col' % mat_name)
            if alpha < 1.0:
                options.append('opacity=%s' % alpha)
        if matopts:
            options += [matopts]
        c += "\\tikzstyle{%s}= [%s]\n" % (mat_name, ",".join(options))
    return c


def write_object(obj, empties):
    """Write Curves"""
    s = ""
    name = obj.name
    prop = obj.properties

    mtrx = obj.matrix.rotationPart()
    x, y, z = obj.getLocation('worldspace')
    rot = obj.getEuler('worldspace')
    scale_x, scale_y, scale_z = obj.matrix.scalePart()

    # Convert to degrees
    rot_z = rot.z * R2D
    if obj.type not in ["Curve", "Empty"]:
        return s

    ps = ""
    if obj.type == 'Curve':
        curvedata = obj.data
        s += "%% %s\n" % name
        for curnurb in curvedata:
            if curnurb.type == TYPE_BEZIER:
                knots = []
                handles = []
                # Build lists of knots and handles
                for point in curnurb:
                    h1, knot, h2 = point.vec
                    handles.extend([h1, h2])
                    knots.append("(+%.4f,+%.4f)" % (knot[X], knot[Y]))

                if curnurb.isCyclic():
                    # The curve is closed.
                    # Move the first handle to the end of the handles list.
                    handles = handles[1:] + [handles[0]]
                    # Repeat the first knot at the end of the knot list
                    knots.append(knots[0])
                else:
                    # We don't need the first and last handles since the curve is
                    # not closed. 
                    handles = handles[1:-1]
                hh = []
                for h1, h2 in nsplit(handles, 2):
                    hh.append("controls (+%.4f,+%.4f) and (+%.4f,+%.4f)" \
                              % (h1[X], h1[Y], h2[X], h2[Y]))

                ps += "%s\n" % knots[0]
                for h, k in zip(hh, knots[1:]):
                    ps += "  .. %s .. %s\n" % (h, k)
                if curnurb.isCyclic():
                    ps += "  -- cycle\n"
            elif curnurb.type == TYPE_POLY:
                coords = ["(+%.4f,+%.4f)" % (point[X], point[Y]) for point in curnurb]

                if USE_PLOTPATH:
                    plotopts = get_property(obj, 'plotstyle')
                    if plotopts:
                        poptstr = "[%s]" % ",".join(plotopts)
                    else:
                        poptstr = ''
                    ps += " plot%s coordinates {%s}" % (poptstr, " ".join(coords))
                    if curnurb.isCyclic():
                        ps += " -- cycle"
                    if WRAP_LINES:
                        ps = "\n".join(wrap(ps, 80, subsequent_indent="  ", break_long_words=False))

                else:
                    if curnurb.isCyclic():
                        coords.extend([coords[0], 'cycle\n  '])
                    # Join the coordinates. Could have used "--".join(coords), but
                    # have to add some logic for pretty printing.
                    if WRAP_LINES:
                        ps += "%s\n  " % coords[0]
                        i = 0
                        for c in coords[1:]:
                            i += 1
                            if i % 3:
                                ps += "-- %s" % c
                            else:
                                ps += "  -- %s\n  " % c
                    else:
                        ps += "%s" % " -- ".join(coords)
            else:
                continue

        if not ps:
            return s
        options = []
        if DRAW_CURVE:
            options += ['draw']
        if FILL_CLOSED_CURVE:
            if ps.find('cycle') > 0:
                options += ['fill']
        if TRANSFORM_CURVE:
            if x <> 0: options.append('xshift=%.4fcm' % x)
            if y <> 0: options.append('yshift=%.4fcm' % y)
            if rot_z <> 0: options.append('rotate=%.4f' % rot_z)
            if scale_x <> 1: options += ['xscale=%.4f' % scale_x]
            if scale_y <> 1: options += ['yscale=%.4f' % scale_y]
        if EXPORT_MATERIALS:
            try:
                materials = obj.data.getMaterials()
            except:
                materials = []
            if materials:
                # pick first material
                for mat in materials:
                    if mat:
                        matopts = get_material(mat)
                        options.append(matopts)
                        break
        extraopts = get_property(obj, 'style')
        if extraopts:
            options.extend(extraopts)

        optstr = ",".join(options)
        emptstr = ""
        if EMPTIES:
            if obj in empties:
                for empty in empties[obj]:
                    # Get correct coordinate relative to the parent
                    if TRANSFORM_CURVE:
                        ex, ey, ez = (empty.mat * (obj.mat.copy()).invert()).translationPart()
                    else:
                        ex, ey, ez = (empty.matrix - obj.matrix).translationPart()
                    emptstr += "  (+%.4f,+%.4f) coordinate (%s)\n" \
                               % (ex, ey, empty.name)

        if not WRAP_LINES:
            ps = ' '.join(ps.replace('\n', ' ').split())
        if len(optstr) > 50 or emptstr:
            s += "\\path[%s]\n%s  %s;\n" % (optstr, emptstr, ps.rstrip())
        else:
            s += "\\path[%s] %s;\n" % (optstr, ps.rstrip())
    elif obj.type == 'Empty' and EMPTIES and not obj.parent:
        x, y, z = obj.loc
        s += "\\coordinate (%s) at (%.4f,%.4f);\n" % (tikzify(obj.name), x, y)

    return s


def write_objects(filepath):
    """Write all selected objects to filepath"""

    def z_comp(a, b):
        x, y, z1 = a.getLocation('worldspace')
        x, y, z2 = b.getLocation('worldspace')
        return cmp(z1, z2)

    # get all selected objects
    objects = Blender.Object.GetSelected()
    # get current scene
    scn = Blender.Scene.GetCurrent()
    # iterate over each object
    code = ""
    # Find all empties with parents
    empties_wp = [obj for obj in objects if obj.type == 'Empty' and obj.parent]
    empties_dict = {}
    for empty in empties_wp:
        if empty.parent in empties_dict:
            empties_dict[empty.parent] += [empty]
        else:
            empties_dict[empty.parent] = [empty]

    for obj in sorted(objects, z_comp):
        code += write_object(obj, empties_dict)
    s = ""
    if EXPORT_MATERIALS:
        matcode = write_materials(used_materials)
    else:
        matcode = ""

    try:
        preamblecode = scn.properties['preamble']
    except:
        preamblecode = ''
    templatevars = dict(pathcode=code, preamble=preamblecode, materials=matcode)
    if STANDALONE:
        extra = ""
        try:
            preambleopt = scn.properties['preamble']
            templatevars['preamble'] = str(preambleopt)
        except:
            pass
        template = standalone_template

    elif CODE_ONLY:
        template = "%(pathcode)s"
    else:
        template = fig_template

    s = template % templatevars
    if not CLIPBOARD_OUTPUT:
        try:
            f = file(filepath, 'w')
            # write header to file
            f.write('%% Generated by tikz_export.py v %s \n' % (__version__))
            f.write(s)
            print "Code written to %s" % filepath
        finally:
            f.close()
        return
    else:
        success = copy_to_clipboard(s)
        if not success:
            print "Failed to copy code to the clipboard"
            print "Pywin32, xclip, cbcopy or pygtk required for clipboard support"
            Blender.Draw.PupMenu('ERROR: Failed to copy generated code to the clipboard')

# Start of script -----------------------------------------------------

# Ensure that at leas one object is selected
if len(Blender.Object.GetSelected()) == 0:
    # no objects selected. Print error message and quit
    Blender.Draw.PupMenu('ERROR: Please select at least one curve')
else:
    fname = bsys.makename(ext=".tex")
    retval = draw_GUI()
    if retval and not CLIPBOARD_OUTPUT:
        Blender.Window.FileSelector(write_objects, "Export TikZ", fname)
    write_objects(fname)
    print "tikz_export ended ..."
