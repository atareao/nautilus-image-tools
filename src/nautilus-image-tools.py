#!/usr/bin/env python2
# -*- coding: utf-8 -*-
#
# This file is part of Image-Tools
#
# Copyright (C) 2013-2016
# Lorenzo Carbonell Cerezo <lorenzo.carbonell.cerezo@gmail.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import gi
try:
    gi.require_version('Gtk', '3.0')
    gi.require_version('GdkPixbuf', '2.0')
    gi.require_version('Nautilus', '3.0')
except Exception as e:
    print(e)
    exit(-1)
from gi.repository import Nautilus as FileManager
from gi.repository import GObject
from gi.repository import Gtk
from gi.repository import GdkPixbuf
from gi.repository import GLib
import os
import array
import StringIO
from threading import Thread
from PIL import Image
from PIL import ImageOps
from PIL import ImageChops
from PIL import ImageFilter
from PIL import ImageFont
from PIL import ImageDraw
from PIL import ImageEnhance
from PIL.ExifTags import TAGS
import random
import time

APP = '$APP$'
VERSION = '$VERSION$'

_ = str

EXTENSIONS = ['.bmp', '.dds', '.exif', '.gif', '.jpg', '.jpeg', '.jp2',
              '.jpx', '.pcx', '.png', '.pnm', '.ras', '.tga', '.tif',
              '.tiff', '.xbm', '.xpm']


class IdleObject(GObject.GObject):
    """
    Override GObject.GObject to always emit signals in the main thread
    by emmitting on an idle handler
    """
    def __init__(self):
        GObject.GObject.__init__(self)

    def emit(self, *args):
        GLib.idle_add(GObject.GObject.emit, self, *args)


class DoItInBackground(IdleObject, Thread):
    __gsignals__ = {
        'started': (GObject.SIGNAL_RUN_FIRST, GObject.TYPE_NONE, (int,)),
        'ended': (GObject.SIGNAL_RUN_FIRST, GObject.TYPE_NONE, (bool,)),
        'start_one': (GObject.SIGNAL_RUN_FIRST, GObject.TYPE_NONE, (str,)),
        'end_one': (GObject.SIGNAL_RUN_FIRST, GObject.TYPE_NONE, (float,)),
    }

    def __init__(self, elements, whattodo, *args):
        IdleObject.__init__(self)
        Thread.__init__(self)
        self.elements = elements
        self.whattodo = whattodo
        self.args = args
        self.stopit = False
        self.ok = False
        self.daemon = True

    def stop(self, *args):
        self.stopit = True

    def run(self):
        total = 0
        for element in self.elements:
            total += os.path.getsize(element)
        self.emit('started', total)
        try:
            self.ok = True
            for element in self.elements:
                if self.stopit is True:
                    self.ok = False
                    break
                self.emit('start_one', element)
                self.whattodo(element, self.args)
                self.emit('end_one', os.path.getsize(element))
        except Exception as e:
            print(e)
            self.ok = False
        self.emit('ended', self.ok)


class Progreso(Gtk.Dialog, IdleObject):
    __gsignals__ = {
        'i-want-stop': (GObject.SIGNAL_RUN_FIRST, GObject.TYPE_NONE, ()),
    }

    def __init__(self, title, parent):
        Gtk.Dialog.__init__(self, title, parent,
                            Gtk.DialogFlags.MODAL |
                            Gtk.DialogFlags.DESTROY_WITH_PARENT)
        IdleObject.__init__(self)
        self.set_position(Gtk.WindowPosition.CENTER_ALWAYS)
        self.set_size_request(330, 30)
        self.set_resizable(False)
        self.connect('destroy', self.close)
        self.set_modal(True)
        vbox = Gtk.VBox(spacing=5)
        vbox.set_border_width(5)
        self.get_content_area().add(vbox)
        #
        frame1 = Gtk.Frame()
        vbox.pack_start(frame1, True, True, 0)
        table = Gtk.Table(2, 2, False)
        frame1.add(table)
        #
        self.label = Gtk.Label()
        table.attach(self.label, 0, 2, 0, 1,
                     xpadding=5,
                     ypadding=5,
                     xoptions=Gtk.AttachOptions.SHRINK,
                     yoptions=Gtk.AttachOptions.EXPAND)
        #
        self.progressbar = Gtk.ProgressBar()
        self.progressbar.set_size_request(300, 0)
        table.attach(self.progressbar, 0, 1, 1, 2,
                     xpadding=5,
                     ypadding=5,
                     xoptions=Gtk.AttachOptions.SHRINK,
                     yoptions=Gtk.AttachOptions.EXPAND)
        button_stop = Gtk.Button()
        button_stop.set_size_request(40, 40)
        button_stop.set_image(
            Gtk.Image.new_from_stock(Gtk.STOCK_STOP, Gtk.IconSize.BUTTON))
        button_stop.connect('clicked', self.on_button_stop_clicked)
        table.attach(button_stop, 1, 2, 1, 2,
                     xpadding=5,
                     ypadding=5,
                     xoptions=Gtk.AttachOptions.SHRINK)
        self.stop = False
        self.show_all()
        self.value = 0.0

    def set_max_value(self, anobject, max_value):
        self.max_value = float(max_value)

    def get_stop(self):
        return self.stop

    def on_button_stop_clicked(self, widget):
        self.stop = True
        self.emit('i-want-stop')

    def close(self, *args):
        self.destroy()

    def increase(self, anobject, value):
        self.value += float(value)
        fraction = self.value / self.max_value
        self.progressbar.set_fraction(fraction)
        if self.value >= self.max_value:
            self.hide()

    def set_element(self, anobject, element):
        self.label.set_text(_('Sending: %s') % element)


def process_files(title, window, files, whattodo, *args):
    diib = DoItInBackground(files, whattodo, args)
    progreso = Progreso(title, window)
    diib.connect('started', progreso.set_max_value)
    diib.connect('start_one', progreso.set_element)
    diib.connect('end_one', progreso.increase)
    diib.connect('ended', progreso.close)
    progreso.connect('i-want-stop', diib.stop)
    diib.start()
    progreso.run()


class WatermarkDialog(Gtk.Dialog):
    def __init__(self, image_filename=None):
        Gtk.Dialog.__init__(
            self,
            _('Watermark'),
            None,
            Gtk.DialogFlags.MODAL | Gtk.DialogFlags.DESTROY_WITH_PARENT,
            (Gtk.STOCK_OK, Gtk.ResponseType.ACCEPT,
             Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL))
        self.set_size_request(500, 140)
        self.set_resizable(False)
        self.set_icon_name(NAME.lower())
        self.connect('destroy', self.close_application)
        #
        vbox0 = Gtk.VBox(spacing=5)
        vbox0.set_border_width(5)
        self.get_content_area().add(vbox0)
        #
        notebook = Gtk.Notebook()
        vbox0.add(notebook)
        #
        frame = Gtk.Frame()
        notebook.append_page(frame, tab_label=Gtk.Label(_('Water mark')))
        #
        table = Gtk.Table(rows=4, columns=2, homogeneous=False)
        table.set_border_width(5)
        table.set_col_spacings(5)
        table.set_row_spacings(5)
        frame.add(table)
        #
        frame1 = Gtk.Frame()
        table.attach(frame1, 0, 1, 0, 1,
                     xoptions=Gtk.AttachOptions.EXPAND,
                     yoptions=Gtk.AttachOptions.SHRINK)
        self.scrolledwindow1 = Gtk.ScrolledWindow()
        self.scrolledwindow1.set_size_request(400, 400)
        self.scrolledwindow1.connect('key-release-event',
                                     self.on_key_release_event)
        frame1.add(self.scrolledwindow1)
        #
        viewport1 = Gtk.Viewport()
        viewport1.set_size_request(400, 400)
        self.scrolledwindow1.add(viewport1)
        #
        frame2 = Gtk.Frame()
        table.attach(frame2, 1, 2, 0, 1,
                     xoptions=Gtk.AttachOptions.EXPAND,
                     yoptions=Gtk.AttachOptions.SHRINK)
        scrolledwindow2 = Gtk.ScrolledWindow()
        scrolledwindow2.set_size_request(400, 400)
        self.connect('key-release-event', self.on_key_release_event)
        frame2.add(scrolledwindow2)
        #
        viewport2 = Gtk.Viewport()
        viewport2.set_size_request(400, 400)
        scrolledwindow2.add(viewport2)
        #
        self.scale = 100
        #
        vertical_options = Gtk.ListStore(str, int)
        vertical_options.append([_('Top'), 0])
        vertical_options.append([_('Middle'), 1])
        vertical_options.append([_('Bottom'), 2])
        #
        horizontal_options = Gtk.ListStore(str, int)
        horizontal_options.append([_('Left'), 0])
        horizontal_options.append([_('Center'), 1])
        horizontal_options.append([_('Right'), 2])
        #
        self.rbutton0 = Gtk.CheckButton(_('Overwrite original file?'))
        table.attach(self.rbutton0, 0, 2, 1, 2,
                     xoptions=Gtk.AttachOptions.FILL,
                     yoptions=Gtk.AttachOptions.SHRINK)
        #
        vbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        table.attach(vbox, 0, 2, 2, 3,
                     xoptions=Gtk.AttachOptions.FILL,
                     yoptions=Gtk.AttachOptions.SHRINK)
        label = Gtk.Label(_('Watermark') + ':')
        vbox.pack_start(label, False, False, 0)
        self.entry = Gtk.Entry()
        self.entry.set_width_chars(50)
        self.entry.set_sensitive(False)
        vbox.pack_start(self.entry, True, True, 0)
        button = Gtk.Button(_('Choose File'))
        button.connect('clicked', self.on_button_clicked)
        vbox.pack_start(button, False, False, 0)
        #
        label = Gtk.Label(_('Horizontal position') + ':')
        table.attach(label, 0, 1, 3, 4,
                     xoptions=Gtk.AttachOptions.FILL,
                     yoptions=Gtk.AttachOptions.SHRINK)
        #
        self.horizontal = Gtk.ComboBox.new_with_model_and_entry(
            horizontal_options)
        self.horizontal.set_entry_text_column(0)
        self.horizontal.set_active(0)
        self.horizontal.connect('changed', self.on_value_changed)
        table.attach(self.horizontal, 1, 2, 3, 4,
                     xoptions=Gtk.AttachOptions.FILL,
                     yoptions=Gtk.AttachOptions.SHRINK)
        #
        label = Gtk.Label(_('Vertical position') + ':')
        table.attach(label, 0, 1, 4, 5,
                     xoptions=Gtk.AttachOptions.FILL,
                     yoptions=Gtk.AttachOptions.SHRINK)
        #
        self.vertical = Gtk.ComboBox.new_with_model_and_entry(vertical_options)
        self.vertical.set_entry_text_column(0)
        self.vertical.set_active(0)
        self.vertical.connect('changed', self.on_value_changed)
        table.attach(self.vertical, 1, 2, 4, 5,
                     xoptions=Gtk.AttachOptions.FILL,
                     yoptions=Gtk.AttachOptions.SHRINK)
        #
        self.pixbuf1 = None
        self.pixbuf2 = None
        self.image1 = None
        self.image2 = None
        self.pil_image1 = None
        self.pil_image2 = None
        if image_filename is not None:
            self.image1 = Gtk.Image()
            self.image1.set_from_file(image_filename)
            self.pixbuf1 = self.image1.get_pixbuf()
            viewport1.add(self.image1)
            self.image2 = Gtk.Image()
            self.image2.set_from_file(image_filename)
            viewport2.add(self.image2)
            self.pixbuf2 = self.image2.get_pixbuf()
            self.pil_image1 = Image.open(image_filename)
            if self.pil_image1.mode != 'RGB':
                self.pil_image1 = self.pil_image1.convert('RGB')
        self.show_all()
        if image_filename is not None:
            factor_w = float(
                self.scrolledwindow1.get_allocation().width) / float(
                self.pixbuf1.get_width())
            factor_h = float(
                self.scrolledwindow1.get_allocation().height) / float(
                self.pixbuf1.get_height())
            if factor_w < factor_h:
                factor = factor_w
            else:
                factor = factor_h
            self.scale = int(factor * 100)
            w = int(self.pixbuf1.get_width() * factor)
            h = int(self.pixbuf1.get_height() * factor)
            #
            self.image1.set_from_pixbuf(
                self.pixbuf1.scale_simple(w, h, GdkPixbuf.InterpType.BILINEAR))
            self.image2.set_from_pixbuf(
                self.pixbuf2.scale_simple(w, h, GdkPixbuf.InterpType.BILINEAR))

    def on_value_changed(self, widget):
        self.update_watermark()

    def get_horizontal_option(self):
        tree_iter = self.horizontal.get_active_iter()
        if tree_iter is not None:
            model = self.horizontal.get_model()
            return model[tree_iter][1]
        return 0

    def get_vertical_option(self):
        tree_iter = self.vertical.get_active_iter()
        if tree_iter is not None:
            model = self.vertical.get_model()
            return model[tree_iter][1]
        return 0

    def update_preview_cb(self, file_chooser, preview):
        filename = file_chooser.get_preview_filename()
        try:
            pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_size(filename, 128, 128)
            preview.set_from_pixbuf(pixbuf)
            have_preview = True
        except Exception as e:
            print(e)
            have_preview = False
        file_chooser.set_preview_widget_active(have_preview)
        return

    def on_button_clicked(self, button):
        dialog = Gtk.FileChooserDialog(
            _('Please choose a file'),
            self,
            Gtk.FileChooserAction.OPEN,
            (Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL,
             Gtk.STOCK_OPEN, Gtk.ResponseType.OK))
        dialog.set_default_response(Gtk.ResponseType.OK)
        dialog.set_select_multiple(False)
        dialog.set_current_folder(os.getenv('HOME'))
        filter_png = Gtk.FileFilter()
        filter_png.set_name(_('Png files'))
        filter_png.add_mime_type('image/png')
        dialog.add_filter(filter_png)
        preview = Gtk.Image()
        dialog.set_preview_widget(preview)
        dialog.connect('update-preview', self.update_preview_cb, preview)
        response = dialog.run()
        if response == Gtk.ResponseType.OK:
            self.entry.set_text(dialog.get_filename())
        dialog.destroy()
        self.update_watermark()

    def update_watermark(self):
        file_watermark = self.entry.get_text()
        if file_watermark and os.path.exists(file_watermark):
            image_in = self.pil_image1.copy()
            image_watermark = Image.open(file_watermark)
            width_original, height_original = image_in.size
            width_watermark, height_watermark = image_watermark.size
            if width_original < width_watermark:
                width = width_watermark
            else:
                width = width_original
            if height_original < height_watermark:
                height = height_watermark
            else:
                height = height_original
            image_out = Image.new('RGBA', (width, height))
            image_out.paste(image_in,
                            (int((width - width_original) / 2),
                             int((height - height_original) / 2)))
            horizontal_position = self.get_horizontal_option()
            vertical_position = self.get_vertical_option()
            if horizontal_position == 0:
                watermark_left = 0
            elif horizontal_position == 1:
                watermark_left = int((width - width_watermark) / 2)
            else:
                watermark_left = int(width - width_watermark)
            if vertical_position == 0:
                watermark_top = 0
            elif vertical_position == 1:
                watermark_top = int((height - height_watermark) / 2)
            else:
                watermark_top = int(height - height_watermark)
            try:
                image_watermark = image_watermark.convert('RGBA')
            except Exception as e:
                print(e)
            image_out.paste(
                image_watermark, (watermark_left, watermark_top),
                mask=image_watermark)
            self.pixbuf2 = image2pixbuf(image_out)
            w = int(self.pixbuf1.get_width() * self.scale / 100)
            h = int(self.pixbuf1.get_height() * self.scale / 100)
            self.image2.set_from_pixbuf(
                self.pixbuf2.scale_simple(w, h, GdkPixbuf.InterpType.BILINEAR))

    def on_key_release_event(self, widget, event):
        print((event.keyval))
        if event.keyval == 65451 or event.keyval == 43:
            self.scale = self.scale * 1.1
        elif event.keyval == 65453 or event.keyval == 45:
            self.scale = self.scale * .9
        elif event.keyval == 65456 or event.keyval == 48:
            factor_w = float(
                self.scrolledwindow1.get_allocation().width) / float(
                self.pixbuf1.get_width())
            factor_h = float(
                self.scrolledwindow1.get_allocation().height) / float(
                self.pixbuf1.get_height())
            if factor_w < factor_h:
                factor = factor_w
            else:
                factor = factor_h
            self.scale = int(factor * 100)
            w = int(self.pixbuf1.get_width() * factor)
            h = int(self.pixbuf1.get_height() * factor)
            #
            self.image1.set_from_pixbuf(
                self.pixbuf1.scale_simple(w, h, GdkPixbuf.InterpType.BILINEAR))
            self.image2.set_from_pixbuf(
                self.pixbuf2.scale_simple(w, h, GdkPixbuf.InterpType.BILINEAR))
        elif event.keyval == 65457 or event.keyval == 49:
            self.scale = 100
        if self.image1:
            w = int(self.pixbuf1.get_width() * self.scale / 100)
            h = int(self.pixbuf1.get_height() * self.scale / 100)
            #
            self.image1.set_from_pixbuf(
                self.pixbuf1.scale_simple(w, h, GdkPixbuf.InterpType.BILINEAR))
            self.image2.set_from_pixbuf(
                self.pixbuf2.scale_simple(w, h, GdkPixbuf.InterpType.BILINEAR))

    def close_application(self, widget):
        self.hide()


class ConvertDialog(Gtk.Dialog):
    def __init__(self, window):
        Gtk.Dialog.__init__(self,
                            _('Convert to'),
                            window,
                            Gtk.DialogFlags.MODAL |
                            Gtk.DialogFlags.DESTROY_WITH_PARENT,
                            (Gtk.STOCK_OK, Gtk.ResponseType.ACCEPT,
                             Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL))
        self.set_size_request(300, 140)
        self.set_resizable(False)
        self.set_icon_name(NAME.lower())
        self.connect('destroy', self.close_application)
        #
        vbox0 = Gtk.VBox(spacing=5)
        vbox0.set_border_width(5)
        self.get_content_area().add(vbox0)
        #
        notebook = Gtk.Notebook()
        vbox0.add(notebook)
        #
        frame1 = Gtk.Frame()
        notebook.append_page(frame1, tab_label=Gtk.Label(_('Convert to')))
        #
        table1 = Gtk.Table(rows=1, columns=2, homogeneous=False)
        table1.set_border_width(5)
        table1.set_col_spacings(5)
        table1.set_row_spacings(5)
        frame1.add(table1)
        #
        options = Gtk.ListStore(str)
        for extension in EXTENSIONS:
            options.append([extension[1:]])
        label = Gtk.Label(_('Convert to') + ':')
        table1.attach(label, 0, 1, 0, 1,
                      xoptions=Gtk.AttachOptions.EXPAND,
                      yoptions=Gtk.AttachOptions.SHRINK)
        #
        self.convert_to = Gtk.ComboBox.new_with_model_and_entry(options)
        self.convert_to.set_entry_text_column(0)
        self.convert_to.set_active(0)
        table1.attach(self.convert_to, 1, 2, 0, 1,
                      xoptions=Gtk.AttachOptions.EXPAND,
                      yoptions=Gtk.AttachOptions.SHRINK)
        #
        self.show_all()

    def get_convert_to(self):
        tree_iter = self.convert_to.get_active_iter()
        if tree_iter is not None:
            model = self.convert_to.get_model()
            return model[tree_iter][0]
        return 'png'

    def close_application(self, widget):
        self.hide()


class EnhanceDialog(Gtk.Dialog):
    def __init__(self, title, window, image_filename=None):
        Gtk.Dialog.__init__(self, title, window,
                            Gtk.DialogFlags.MODAL |
                            Gtk.DialogFlags.DESTROY_WITH_PARENT,
                            (Gtk.STOCK_OK, Gtk.ResponseType.ACCEPT,
                             Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL))
        self.set_default_size(800, 400)
        self.set_resizable(True)
        self.connect('destroy', self.close)
        #
        vbox = Gtk.VBox(spacing=5)
        vbox.set_border_width(5)
        self.get_content_area().add(vbox)
        #
        frame = Gtk.Frame()
        vbox.pack_start(frame, True, True, 0)
        #
        table = Gtk.Table(rows=2, columns=3, homogeneous=False)
        table.set_border_width(5)
        table.set_col_spacings(5)
        table.set_row_spacings(5)
        frame.add(table)
        #
        frame1 = Gtk.Frame()
        table.attach(frame1, 0, 1, 0, 1,
                     xoptions=Gtk.AttachOptions.EXPAND,
                     yoptions=Gtk.AttachOptions.SHRINK)
        self.scrolledwindow1 = Gtk.ScrolledWindow()
        self.scrolledwindow1.set_size_request(400, 400)
        self.connect('key-release-event', self.on_key_release_event)
        frame1.add(self.scrolledwindow1)
        #
        viewport1 = Gtk.Viewport()
        viewport1.set_size_request(400, 400)
        self.scrolledwindow1.add(viewport1)
        #
        frame2 = Gtk.Frame()
        table.attach(frame2, 1, 2, 0, 1,
                     xoptions=Gtk.AttachOptions.EXPAND,
                     yoptions=Gtk.AttachOptions.SHRINK)
        scrolledwindow2 = Gtk.ScrolledWindow()
        scrolledwindow2.set_size_request(400, 400)
        self.connect('key-release-event', self.on_key_release_event)
        frame2.add(scrolledwindow2)
        #
        viewport2 = Gtk.Viewport()
        viewport2.set_size_request(400, 400)
        scrolledwindow2.add(viewport2)
        #
        self.scale = 100
        #
        #
        self.rbutton0 = Gtk.CheckButton(_('Overwrite original file?'))
        table.attach(self.rbutton0, 0, 2, 1, 2,
                     xoptions=Gtk.AttachOptions.FILL,
                     yoptions=Gtk.AttachOptions.SHRINK)
        #
        table.attach(Gtk.Label(_('Brightness')), 0, 1, 2, 3,
                     xoptions=Gtk.AttachOptions.FILL,
                     yoptions=Gtk.AttachOptions.SHRINK)
        self.slider1 = Gtk.HScale()
        self.slider1.set_digits(0)
        self.slider1.set_name('scale1')
        self.slider1.set_adjustment(Gtk.Adjustment(100, 0, 200, 1, 10, 0))
        self.slider1.connect("value-changed", self.slider_on_value_changed)
        table.attach(self.slider1, 1, 2, 2, 3,
                     xoptions=Gtk.AttachOptions.FILL,
                     yoptions=Gtk.AttachOptions.SHRINK)
        #
        table.attach(Gtk.Label(_('Color')), 0, 1, 3, 4,
                     xoptions=Gtk.AttachOptions.FILL,
                     yoptions=Gtk.AttachOptions.SHRINK)
        self.slider2 = Gtk.HScale()
        self.slider2.set_digits(0)
        self.slider2.set_name('scale2')
        self.slider2.set_adjustment(Gtk.Adjustment(100, 0, 200, 1, 10, 0))
        self.slider2.connect("value-changed", self.slider_on_value_changed)
        table.attach(self.slider2, 1, 2, 3, 4,
                     xoptions=Gtk.AttachOptions.FILL,
                     yoptions=Gtk.AttachOptions.SHRINK)
        #
        table.attach(Gtk.Label(_('Contrast')), 0, 1, 4, 5,
                     xoptions=Gtk.AttachOptions.FILL,
                     yoptions=Gtk.AttachOptions.SHRINK)
        self.slider3 = Gtk.HScale()
        self.slider3.set_digits(0)
        self.slider3.set_name('scale3')
        self.slider3.set_adjustment(Gtk.Adjustment(100, 0, 200, 1, 10, 0))
        self.slider3.connect("value-changed", self.slider_on_value_changed)
        table.attach(self.slider3, 1, 2, 4, 5,
                     xoptions=Gtk.AttachOptions.FILL,
                     yoptions=Gtk.AttachOptions.SHRINK)
        #
        table.attach(Gtk.Label(_('Sharpness')), 0, 1, 5, 6,
                     xoptions=Gtk.AttachOptions.FILL,
                     yoptions=Gtk.AttachOptions.SHRINK)
        self.slider4 = Gtk.HScale()
        self.slider4.set_digits(0)
        self.slider4.set_name('scale4')
        self.slider4.set_adjustment(Gtk.Adjustment(100, 0, 200, 1, 10, 0))
        self.slider4.connect("value-changed", self.slider_on_value_changed)
        table.attach(self.slider4, 1, 2, 5, 6,
                     xoptions=Gtk.AttachOptions.FILL,
                     yoptions=Gtk.AttachOptions.SHRINK)
        #
        self.pixbuf1 = None
        self.pixbuf2 = None
        self.image1 = None
        self.image2 = None
        self.pil_image1 = None
        self.pil_image2 = None
        if image_filename is not None:
            self.image1 = Gtk.Image()
            self.image1.set_from_file(image_filename)
            self.pixbuf1 = self.image1.get_pixbuf()
            viewport1.add(self.image1)
            self.image2 = Gtk.Image()
            self.image2.set_from_file(image_filename)
            viewport2.add(self.image2)
            self.pixbuf2 = self.image2.get_pixbuf()
            self.pil_image1 = Image.open(image_filename)
        self.show_all()
        if image_filename is not None:
            factor_w = (float(self.scrolledwindow1.get_allocation().width) /
                        float(self.pixbuf1.get_width()))
            factor_h = (float(self.scrolledwindow1.get_allocation().height) /
                        float(self.pixbuf1.get_height()))
            if factor_w < factor_h:
                factor = factor_w
            else:
                factor = factor_h
            self.scale = int(factor * 100)
            w = int(self.pixbuf1.get_width() * factor)
            h = int(self.pixbuf1.get_height() * factor)
            #
            self.image1.set_from_pixbuf(
                self.pixbuf1.scale_simple(w, h, GdkPixbuf.InterpType.BILINEAR))
            self.image2.set_from_pixbuf(
                self.pixbuf2.scale_simple(w, h, GdkPixbuf.InterpType.BILINEAR))

    def slider_on_value_changed(self, widget):
        brightness = float(self.slider1.get_value() / 100.0)
        color = float(self.slider2.get_value() / 100.0)
        contrast = float(self.slider3.get_value() / 100.0)
        sharpness = float(self.slider4.get_value() / 100.0)
        pil_image2 = self.pil_image1
        if int(brightness * 100) != 100:
            enhancer = ImageEnhance.Brightness(pil_image2)
            pil_image2 = enhancer.enhance(brightness)
        if int(color * 100) != 100:
            enhancer = ImageEnhance.Color(pil_image2)
            pil_image2 = enhancer.enhance(color)
        if int(contrast * 100) != 100:
            enhancer = ImageEnhance.Contrast(pil_image2)
            pil_image2 = enhancer.enhance(contrast)
        if int(sharpness * 100) != 100:
            enhancer = ImageEnhance.Sharpness(pil_image2)
            pil_image2 = enhancer.enhance(sharpness)
        #
        self.pixbuf2 = image2pixbuf(pil_image2)
        w = int(self.pixbuf1.get_width() * self.scale / 100)
        h = int(self.pixbuf1.get_height() * self.scale / 100)
        self.image2.set_from_pixbuf(
            self.pixbuf2.scale_simple(w, h, GdkPixbuf.InterpType.BILINEAR))

    def on_key_release_event(self, widget, event):
        print((event.keyval))
        if event.keyval == 65451 or event.keyval == 43:
            self.scale = self.scale * 1.1
        elif event.keyval == 65453 or event.keyval == 45:
            self.scale = self.scale * .9
        elif event.keyval == 65456 or event.keyval == 48:
            factor_w = (float(self.scrolledwindow1.get_allocation().width) /
                        float(self.pixbuf1.get_width()))
            factor_h = (float(self.scrolledwindow1.get_allocation().height) /
                        float(self.pixbuf1.get_height()))
            if factor_w < factor_h:
                factor = factor_w
            else:
                factor = factor_h
            self.scale = int(factor * 100)
            w = int(self.pixbuf1.get_width() * factor)
            h = int(self.pixbuf1.get_height() * factor)
            #
            self.image1.set_from_pixbuf(
                self.pixbuf1.scale_simple(w, h, GdkPixbuf.InterpType.BILINEAR))
            self.image2.set_from_pixbuf(
                self.pixbuf2.scale_simple(w, h, GdkPixbuf.InterpType.BILINEAR))
        elif event.keyval == 65457 or event.keyval == 49:
            self.scale = 100
        if self.image1:
            w = int(self.pixbuf1.get_width() * self.scale / 100)
            h = int(self.pixbuf1.get_height() * self.scale / 100)
            #
            self.image1.set_from_pixbuf(
                self.pixbuf1.scale_simple(w, h, GdkPixbuf.InterpType.BILINEAR))
            self.image2.set_from_pixbuf(
                self.pixbuf2.scale_simple(w, h, GdkPixbuf.InterpType.BILINEAR))

    def close(self, widget):
        self.destroy()


class VintageDialog(Gtk.Dialog):
    def __init__(self, title, image_filename=None):
        Gtk.Dialog.__init__(self, title, None,
                            Gtk.DialogFlags.MODAL |
                            Gtk.DialogFlags.DESTROY_WITH_PARENT,
                            (Gtk.STOCK_OK, Gtk.ResponseType.ACCEPT,
                             Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL))
        self.set_default_size(800, 400)
        self.set_resizable(True)
        self.connect('destroy', self.close)
        #
        vbox = Gtk.VBox(spacing=5)
        vbox.set_border_width(5)
        self.get_content_area().add(vbox)
        #
        frame = Gtk.Frame()
        vbox.pack_start(frame, True, True, 0)
        #
        table = Gtk.Table(rows=2, columns=3, homogeneous=False)
        table.set_border_width(5)
        table.set_col_spacings(5)
        table.set_row_spacings(5)
        frame.add(table)
        #
        frame1 = Gtk.Frame()
        table.attach(frame1, 0, 1, 0, 1,
                     xoptions=Gtk.AttachOptions.EXPAND,
                     yoptions=Gtk.AttachOptions.SHRINK)
        self.scrolledwindow1 = Gtk.ScrolledWindow()
        self.scrolledwindow1.set_size_request(400, 400)
        self.scrolledwindow1.connect('key-release-event',
                                     self.on_key_release_event)
        frame1.add(self.scrolledwindow1)
        #
        viewport1 = Gtk.Viewport()
        viewport1.set_size_request(400, 400)
        self.scrolledwindow1.add(viewport1)
        #
        frame2 = Gtk.Frame()
        table.attach(frame2, 1, 2, 0, 1,
                     xoptions=Gtk.AttachOptions.EXPAND,
                     yoptions=Gtk.AttachOptions.SHRINK)
        scrolledwindow2 = Gtk.ScrolledWindow()
        scrolledwindow2.set_size_request(400, 400)
        self.connect('key-release-event', self.on_key_release_event)
        frame2.add(scrolledwindow2)
        #
        viewport2 = Gtk.Viewport()
        viewport2.set_size_request(400, 400)
        scrolledwindow2.add(viewport2)
        #
        self.scale = 100
        #
        #
        self.rbutton0 = Gtk.CheckButton(_('Overwrite original file?'))
        table.attach(self.rbutton0, 0, 2, 1, 2,
                     xoptions=Gtk.AttachOptions.FILL,
                     yoptions=Gtk.AttachOptions.SHRINK)
        #
        table.attach(Gtk.Label(_('Noise')), 0, 1, 2, 3,
                     xoptions=Gtk.AttachOptions.FILL,
                     yoptions=Gtk.AttachOptions.SHRINK)
        self.slider1 = Gtk.HScale()
        self.slider1.set_digits(0)
        self.slider1.set_name('scale1')
        self.slider1.set_adjustment(Gtk.Adjustment(0, 0, 100, 1, 10, 0))
        self.slider1.connect("value-changed", self.slider_on_value_changed)
        table.attach(self.slider1, 1, 2, 2, 3,
                     xoptions=Gtk.AttachOptions.FILL,
                     yoptions=Gtk.AttachOptions.SHRINK)
        #
        self.pixbuf1 = None
        self.pixbuf2 = None
        self.image1 = None
        self.image2 = None
        self.pil_image1 = None
        self.pil_image2 = None
        if image_filename is not None:
            self.image1 = Gtk.Image()
            self.image1.set_from_file(image_filename)
            self.pixbuf1 = self.image1.get_pixbuf()
            viewport1.add(self.image1)
            self.image2 = Gtk.Image()
            self.image2.set_from_file(image_filename)
            viewport2.add(self.image2)
            self.pixbuf2 = self.image2.get_pixbuf()
            self.pil_image1 = Image.open(image_filename)
            if self.pil_image1.mode != 'RGB':
                self.pil_image1 = self.pil_image1.convert('RGB')
            self.slider1.set_value(20)
        self.show_all()
        if image_filename is not None:
            factor_w = (float(self.scrolledwindow1.get_allocation().width) /
                        float(self.pixbuf1.get_width()))
            factor_h = (float(self.scrolledwindow1.get_allocation().height) /
                        float(self.pixbuf1.get_height()))
            if factor_w < factor_h:
                factor = factor_w
            else:
                factor = factor_h
            self.scale = int(factor * 100)
            w = int(self.pixbuf1.get_width() * factor)
            h = int(self.pixbuf1.get_height() * factor)
            #
            self.image1.set_from_pixbuf(self.pixbuf1.scale_simple(
                w, h, GdkPixbuf.InterpType.BILINEAR))
            self.image2.set_from_pixbuf(self.pixbuf2.scale_simple(
                w, h, GdkPixbuf.InterpType.BILINEAR))

    def slider_on_value_changed(self, widget):
        progreso = ProgressDialog(_('Vintage Operation'), 4)
        progreso.increase()
        pil_image2 = self.pil_image1.copy()
        progreso.increase()
        pil_image2 = vintage_colors(pil_image2)
        progreso.increase()
        pil_image2 = add_noise(pil_image2, int(self.slider1.get_value()))
        progreso.increase()
        #
        self.pixbuf2 = image2pixbuf(pil_image2)
        w = int(self.pixbuf1.get_width()*self.scale/100)
        h = int(self.pixbuf1.get_height()*self.scale/100)
        self.image2.set_from_pixbuf(self.pixbuf2.scale_simple(
            w, h, GdkPixbuf.InterpType.BILINEAR))

    def on_key_release_event(self, widget, event):
        print((event.keyval))
        if event.keyval == 65451 or event.keyval == 43:
            self.scale = self.scale*1.1
        elif event.keyval == 65453 or event.keyval == 45:
            self.scale = self.scale*.9
        elif event.keyval == 65456 or event.keyval == 48:
            factor_w = (float(self.scrolledwindow1.get_allocation().width) /
                        float(self.pixbuf1.get_width()))
            factor_h = (float(self.scrolledwindow1.get_allocation().height) /
                        float(self.pixbuf1.get_height()))
            if factor_w < factor_h:
                factor = factor_w
            else:
                factor = factor_h
            self.scale = int(factor*100)
            w = int(self.pixbuf1.get_width()*factor)
            h = int(self.pixbuf1.get_height()*factor)
            #
            self.image1.set_from_pixbuf(self.pixbuf1.scale_simple(
                w, h, GdkPixbuf.InterpType.BILINEAR))
            self.image2.set_from_pixbuf(self.pixbuf2.scale_simple(
                w, h, GdkPixbuf.InterpType.BILINEAR))
        elif event.keyval == 65457 or event.keyval == 49:
            self.scale = 100
        if self.image1:
            w = int(self.pixbuf1.get_width()*self.scale/100)
            h = int(self.pixbuf1.get_height()*self.scale/100)
            #
            self.image1.set_from_pixbuf(self.pixbuf1.scale_simple(
                w, h, GdkPixbuf.InterpType.BILINEAR))
            self.image2.set_from_pixbuf(self.pixbuf2.scale_simple(
                w, h, GdkPixbuf.InterpType.BILINEAR))

    def close(self, widget):
        self.destroy()


class DefaultDialog(Gtk.Dialog):
    def __init__(self, title, window):
        Gtk.Dialog.__init__(self,
                            title,
                            window,
                            Gtk.DialogFlags.MODAL |
                            Gtk.DialogFlags.DESTROY_WITH_PARENT,
                            (Gtk.STOCK_OK, Gtk.ResponseType.ACCEPT,
                             Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL))
        self.set_size_request(300, 140)
        self.set_resizable(False)
        self.set_icon_name(NAME.lower())
        self.connect('destroy', self.close_application)

        vbox0 = Gtk.VBox(spacing=5)
        vbox0.set_border_width(5)
        self.get_content_area().add(vbox0)

        notebook = Gtk.Notebook()
        vbox0.add(notebook)

        frame1 = Gtk.Frame()
        notebook.append_page(frame1, tab_label=Gtk.Label(title))

        table1 = Gtk.Table(rows=1, columns=1, homogeneous=False)
        table1.set_border_width(5)
        table1.set_col_spacings(5)
        table1.set_row_spacings(5)
        frame1.add(table1)

        self.rbutton0 = Gtk.CheckButton(_('Overwrite original file?'))
        table1.attach(self.rbutton0, 0, 2, 0, 1,
                      xoptions=Gtk.AttachOptions.EXPAND,
                      yoptions=Gtk.AttachOptions.SHRINK)
        self.show_all()

    def close_application(self, widget):
        self.hide()


class RotateDialog(Gtk.Dialog):
    def __init__(self):
        Gtk.Dialog.__init__(self, _('Rotate images'), None,
                            Gtk.DialogFlags.MODAL |
                            Gtk.DialogFlags.DESTROY_WITH_PARENT,
                            (Gtk.STOCK_OK, Gtk.ResponseType.ACCEPT,
                             Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL))
        self.set_size_request(300, 140)
        self.set_resizable(False)
        self.set_icon_name(NAME.lower())
        self.connect('destroy', self.close_application)
        #
        vbox0 = Gtk.VBox(spacing=5)
        vbox0.set_border_width(5)
        self.get_content_area().add(vbox0)
        #
        notebook = Gtk.Notebook()
        vbox0.add(notebook)
        #
        frame1 = Gtk.Frame()
        notebook.append_page(frame1, tab_label=Gtk.Label(_('Rotate images')))
        #
        table1 = Gtk.Table(rows=3, columns=2, homogeneous=False)
        table1.set_border_width(5)
        table1.set_col_spacings(5)
        table1.set_row_spacings(5)
        frame1.add(table1)
        #
        self.rbutton0 = Gtk.CheckButton(_('Overwrite original file?'))
        table1.attach(self.rbutton0, 0, 2, 0, 1,
                      xoptions=Gtk.AttachOptions.EXPAND,
                      yoptions=Gtk.AttachOptions.SHRINK)
        label = Gtk.Label(_('Degrees') + ':')
        table1.attach(label, 0, 1, 1, 2,
                      xoptions=Gtk.AttachOptions.EXPAND,
                      yoptions=Gtk.AttachOptions.SHRINK)
        self.sp = Gtk.SpinButton()
        self.sp.set_adjustment(Gtk.Adjustment(90, 0, 360, 5, 45, 0))
        self.sp.set_value(90)
        table1.attach(self.sp, 1, 2, 1, 2,
                      xoptions=Gtk.AttachOptions.EXPAND,
                      yoptions=Gtk.AttachOptions.SHRINK)

        self.rbutton1 = Gtk.RadioButton.new_from_widget(None)
        self.rbutton1.add(Gtk.Image.new_from_icon_name(
            'object-rotate-left', Gtk.IconSize.BUTTON))
        table1.attach(self.rbutton1, 0, 1, 2, 3,
                      xoptions=Gtk.AttachOptions.EXPAND,
                      yoptions=Gtk.AttachOptions.SHRINK)
        self.rbutton2 = Gtk.RadioButton.new_from_widget(self.rbutton1)
        self.rbutton2.add(Gtk.Image.new_from_icon_name(
            'object-rotate-right', Gtk.IconSize.BUTTON))
        table1.attach(self.rbutton2, 1, 2, 2, 3,
                      xoptions=Gtk.AttachOptions.EXPAND,
                      yoptions=Gtk.AttachOptions.SHRINK)
        self.show_all()

    def close_application(self, widget):
        self.hide()


class FlipDialog(Gtk.Dialog):
    def __init__(self):
        Gtk.Dialog.__init__(self, _('Flip images'), None,
                            Gtk.DialogFlags.MODAL |
                            Gtk.DialogFlags.DESTROY_WITH_PARENT,
                            (Gtk.STOCK_OK, Gtk.ResponseType.ACCEPT,
                             Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL))
        self.set_size_request(300, 140)
        self.set_resizable(False)
        self.set_icon_name(NAME.lower())
        self.connect('destroy', self.close_application)
        #
        vbox0 = Gtk.VBox(spacing=5)
        vbox0.set_border_width(5)
        self.get_content_area().add(vbox0)
        #
        notebook = Gtk.Notebook()
        vbox0.add(notebook)
        #
        frame1 = Gtk.Frame()
        notebook.append_page(frame1, tab_label=Gtk.Label(_('Flip images')))
        #
        table1 = Gtk.Table(rows=2, columns=2, homogeneous=False)
        table1.set_border_width(5)
        table1.set_col_spacings(5)
        table1.set_row_spacings(5)
        frame1.add(table1)
        #
        self.rbutton0 = Gtk.CheckButton(_('Overwrite original file?'))
        table1.attach(self.rbutton0, 0, 2, 0, 1,
                      xoptions=Gtk.AttachOptions.EXPAND,
                      yoptions=Gtk.AttachOptions.SHRINK)
        self.rbutton1 = Gtk.RadioButton.new_from_widget(None)
        self.rbutton1.add(Gtk.Image.new_from_icon_name(
            'object-flip-horizontal', Gtk.IconSize.BUTTON))
        table1.attach(self.rbutton1, 0, 1, 1, 2,
                      xoptions=Gtk.AttachOptions.EXPAND,
                      yoptions=Gtk.AttachOptions.SHRINK)
        self.rbutton2 = Gtk.RadioButton.new_from_widget(self.rbutton1)
        self.rbutton2.add(Gtk.Image.new_from_icon_name(
            'object-flip-vertical', Gtk.IconSize.BUTTON))
        table1.attach(self.rbutton2, 1, 2, 1, 2,
                      xoptions=Gtk.AttachOptions.EXPAND,
                      yoptions=Gtk.AttachOptions.SHRINK)
        self.show_all()

    def close_application(self, widget):
        self.hide()


class ResizeDialog(Gtk.Dialog):
    def __init__(self):
        Gtk.Dialog.__init__(self, _('Resize images'), None,
                            Gtk.DialogFlags.MODAL |
                            Gtk.DialogFlags.DESTROY_WITH_PARENT,
                            (Gtk.STOCK_OK, Gtk.ResponseType.ACCEPT,
                             Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL))
        self.set_size_request(300, 140)
        self.set_resizable(False)
        self.set_icon_name(NAME.lower())
        self.connect('destroy', self.close_application)
        #
        vbox0 = Gtk.VBox(spacing=5)
        vbox0.set_border_width(5)
        self.get_content_area().add(vbox0)
        #
        notebook = Gtk.Notebook()
        vbox0.add(notebook)
        #
        frame1 = Gtk.Frame()
        notebook.append_page(frame1, tab_label=Gtk.Label(_('Flip images')))
        #
        table1 = Gtk.Table(rows=4, columns=3, homogeneous=False)
        table1.set_border_width(5)
        table1.set_col_spacings(5)
        table1.set_row_spacings(5)
        frame1.add(table1)
        #
        options = Gtk.ListStore(str, bool)
        options.append([_('pixels'), False])
        options.append([_('%'), True])
        #
        self.rbutton0 = Gtk.CheckButton(_('Overwrite original file?'))
        table1.attach(self.rbutton0, 0, 3, 0, 1,
                      xoptions=Gtk.AttachOptions.EXPAND,
                      yoptions=Gtk.AttachOptions.SHRINK)
        self.rbutton1 = Gtk.CheckButton(_('Maintain aspect ratio?'))
        self.rbutton1.connect('toggled', self.on_rbutton1_changed)
        table1.attach(self.rbutton1, 0, 3, 1, 2,
                      xoptions=Gtk.AttachOptions.EXPAND,
                      yoptions=Gtk.AttachOptions.SHRINK)
        label1 = Gtk.Label(_('Width') + ':')
        table1.attach(label1, 0, 1, 2, 3,
                      xoptions=Gtk.AttachOptions.EXPAND,
                      yoptions=Gtk.AttachOptions.SHRINK)
        self.width = Gtk.SpinButton()
        self.width.set_adjustment(Gtk.Adjustment(100, 0, 1000, 1, 10, 0))
        self.width.set_value(100)
        self.width.connect('changed', self.on_width_changed)
        table1.attach(self.width, 1, 2, 2, 3,
                      xoptions=Gtk.AttachOptions.EXPAND,
                      yoptions=Gtk.AttachOptions.SHRINK)
        self.width_pixels = Gtk.Entry()
        self.width_pixels.set_text('256')
        self.width_pixels.connect('changed', self.on_width_changed)
        table1.attach(self.width_pixels, 1, 2, 2, 3,
                      xoptions=Gtk.AttachOptions.EXPAND,
                      yoptions=Gtk.AttachOptions.SHRINK)
        self.width_option = Gtk.ComboBox.new_with_model_and_entry(options)
        self.width_option.set_entry_text_column(0)
        self.width_option.connect("changed",
                                  self.on_width_option_combo_changed)
        self.width_option.set_active(0)
        table1.attach(self.width_option, 2, 3, 2, 3,
                      xoptions=Gtk.AttachOptions.EXPAND,
                      yoptions=Gtk.AttachOptions.SHRINK)

        label2 = Gtk.Label(_('Height') + ':')
        table1.attach(label2, 0, 1, 3, 4,
                      xoptions=Gtk.AttachOptions.EXPAND,
                      yoptions=Gtk.AttachOptions.SHRINK)
        self.height = Gtk.SpinButton()
        self.height.set_adjustment(Gtk.Adjustment(100, 0, 1000, 1, 10, 0))
        self.height.set_value(100)
        table1.attach(self.height, 1, 2, 3, 4,
                      xoptions=Gtk.AttachOptions.EXPAND,
                      yoptions=Gtk.AttachOptions.SHRINK)
        self.height_pixels = Gtk.Entry()
        self.height_pixels.set_text('256')
        table1.attach(self.height_pixels, 1, 2, 3, 4,
                      xoptions=Gtk.AttachOptions.EXPAND,
                      yoptions=Gtk.AttachOptions.SHRINK)

        self.height_option = Gtk.ComboBox.new_with_model_and_entry(options)
        self.height_option.set_entry_text_column(0)
        self.height_option.connect("changed",
                                   self.on_height_option_combo_changed)
        self.height_option.set_active(0)
        table1.attach(self.height_option, 2, 3, 3, 4,
                      xoptions=Gtk.AttachOptions.EXPAND,
                      yoptions=Gtk.AttachOptions.SHRINK)
        self.show_all()
        self.width_pixels.set_visible(True)
        self.width.set_visible(False)
        self.height_pixels.set_visible(True)
        self.height.set_visible(False)

    def get_percentage_width(self):
        tree_iter = self.width_option.get_active_iter()
        if tree_iter is not None:
            model = self.width_option.get_model()
            name, isornotis = model[tree_iter][:2]
        else:
            entry = self.width_option.get_child()
            name = entry.get_text()
        return name == '%'

    def get_width(self):
        tree_iter = self.width_option.get_active_iter()
        if tree_iter is not None:
            model = self.width_option.get_model()
            name, isornotis = model[tree_iter][:2]
        else:
            entry = self.width_option.get_child()
            name = entry.get_text()
        if name == '%':
            return float(self.width.get_value())
        return float(self.width_pixels.get_text())

    def get_height(self):
        tree_iter = self.height_option.get_active_iter()
        if tree_iter is not None:
            model = self.height_option.get_model()
            name, isornotis = model[tree_iter][:2]
        else:
            entry = self.height_option.get_child()
            name = entry.get_text()
        if name == '%':
            return float(self.height.get_value())
        return float(self.height_pixels.get_text())

    def get_percentage_height(self):
        tree_iter = self.height_option.get_active_iter()
        if tree_iter is not None:
            model = self.height_option.get_model()
            name, isornotis = model[tree_iter][:2]
        else:
            entry = self.height_option.get_child()
            name = entry.get_text()
        return name == '%'

    def on_rbutton1_changed(self, widget):
        self.height_pixels.set_sensitive(not self.rbutton1.get_active())
        self.height.set_sensitive(not self.rbutton1.get_active())
        self.height_option.set_sensitive(not self.rbutton1.get_active())

    def on_width_option_combo_changed(self, widget):
        tree_iter = widget.get_active_iter()
        if tree_iter is not None:
            model = widget.get_model()
            name, isornotis = model[tree_iter][:2]
        else:
            entry = widget.get_child()
            name = entry.get_text()
        if name == '%':
            self.width_pixels.set_visible(False)
            self.width.set_visible(True)
        else:
            self.width_pixels.set_visible(True)
            self.width.set_visible(False)
        if self.rbutton1.get_active():
            self.height_option.set_active(self.width_option.get_active())

    def on_width_changed(self, widget):
        if self.rbutton1.get_active():
            self.height.set_value(self.width.get_value())
            self.height_pixels.set_text(self.width_pixels.get_text())

    def on_height_option_combo_changed(self, widget):
        tree_iter = widget.get_active_iter()
        if tree_iter is not None:
            model = widget.get_model()
            name, isornotis = model[tree_iter][:2]
        else:
            entry = widget.get_child()
            name = entry.get_text()
        if name == '%':
            self.height_pixels.set_visible(False)
            self.height.set_visible(True)
        else:
            self.height_pixels.set_visible(True)
            self.height.set_visible(False)

    def close_application(self, widget):
        self.hide()

# #######################################################################
# #################### FUNCIONES AUXILIARES #############################
# #######################################################################


FONT = '/usr/share/fonts/truetype/ubuntu-font-family/UbuntuMono-R.ttf'
RATIO = 0.1
MARGIN = 20
TOP = False

VINTAGE_COLOR_LEVELS = {
    'r': [0, 0, 0, 1, 1, 2, 3, 3, 3, 4, 4, 4, 5, 5, 5, 6, 6, 7, 7, 7, 7, 8, 8,
          8, 9, 9, 9, 9, 10, 10, 10, 10, 11, 11, 12, 12, 12, 12, 13, 13, 13,
          14, 14, 15, 15, 16, 16, 17, 17, 17, 18, 19, 19, 20, 21, 22, 22, 23,
          24, 25, 26, 27, 28, 29, 30, 31, 32, 33, 34, 35, 36, 37, 39, 40, 41,
          42, 44, 45, 47, 48, 49, 52, 54, 55, 57, 59, 60, 62, 65, 67, 69, 70,
          72, 74, 77, 79, 81, 83, 86, 88, 90, 92, 94, 97, 99, 101, 103, 107,
          109, 111, 112, 116, 118, 120, 124, 126, 127, 129, 133, 135, 136, 140,
          142, 143, 145, 149, 150, 152, 155, 157, 159, 162, 163, 165, 167, 170,
          171, 173, 176, 177, 178, 180, 183, 184, 185, 188, 189, 190, 192, 194,
          195, 196, 198, 200, 201, 202, 203, 204, 206, 207, 208, 209, 211, 212,
          213, 214, 215, 216, 218, 219, 219, 220, 221, 222, 223, 224, 225, 226,
          227, 227, 228, 229, 229, 230, 231, 232, 232, 233, 234, 234, 235, 236,
          236, 237, 238, 238, 239, 239, 240, 241, 241, 242, 242, 243, 244, 244,
          245, 245, 245, 246, 247, 247, 248, 248, 249, 249, 249, 250, 251, 251,
          252, 252, 252, 253, 254, 254, 254, 255, 255, 255, 255, 255, 255, 255,
          255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255,
          255, 255, 255, 255, 255, 255, 255, 255],
    'g': [0, 0, 1, 2, 2, 3, 5, 5, 6, 7, 8, 8, 10, 11, 11, 12, 13, 15, 15, 16,
          7, 18, 18, 19, 21, 22, 22, 23, 24, 26, 26, 27, 28, 29, 31, 31, 32,
          33, 34, 35, 35, 37, 38, 39, 40, 41, 43, 44, 44, 45, 46, 47, 48, 50,
          51, 52, 53, 54, 56, 57, 58, 59, 60, 61, 63, 64, 65, 66, 67, 68, 69,
          71, 72, 73, 74, 75, 76, 77, 79, 80, 81, 83, 84, 85, 86, 88, 89, 90,
          92, 93, 94, 95, 96, 97, 100, 101, 102, 103, 105, 106, 107, 108, 109,
          111, 113, 114, 115, 117, 118, 119, 120, 122, 123, 124, 126, 127,
          128, 129, 131, 132, 133, 135, 136, 137, 138, 140, 141, 142, 144,
          145, 146, 148, 149, 150, 151, 153, 154, 155, 157, 158, 159, 160,
          162, 163, 164, 166, 167, 168, 169, 171, 172, 173, 174, 175, 176,
          177, 178, 179, 181, 182, 183, 184, 186, 186, 187, 188, 189, 190,
          192, 193, 194, 195, 195, 196, 197, 199, 200, 201, 202, 202, 203,
          204, 205, 206, 207, 208, 208, 209, 210, 211, 212, 213, 214, 214,
          215, 216, 217, 218, 219, 219, 220, 221, 222, 223, 223, 224, 225,
          226, 226, 227, 228, 228, 229, 230, 231, 232, 232, 232, 233, 234,
          235, 235, 236, 236, 237, 238, 238, 239, 239, 240, 240, 241, 242,
          242, 242, 243, 244, 245, 245, 246, 246, 247, 247, 248, 249, 249,
          249, 250, 251, 251, 252, 252, 252, 253, 254, 255],
    'b': [53, 53, 53, 54, 54, 54, 55, 55, 55, 56, 57, 57, 57, 58, 58, 58, 59,
          59, 59, 60, 61, 61, 61, 62, 62, 63, 63, 63, 64, 65, 65, 65, 66, 66,
          67, 67, 67, 68, 69, 69, 69, 70, 70, 71, 71, 72, 73, 73, 73, 74, 74,
          75, 75, 76, 77, 77, 78, 78, 79, 79, 80, 81, 81, 82, 82, 83, 83, 84,
          85, 85, 86, 86, 87, 87, 88, 89, 89, 90, 90, 91, 91, 93, 93, 94, 94,
          95, 95, 96, 97, 98, 98, 99, 99, 100, 101, 102, 102, 103, 104, 105,
          105, 106, 106, 107, 108, 109, 109, 110, 111, 111, 112, 113, 114, 114,
          115, 116, 117, 117, 118, 119, 119, 121, 121, 122, 122, 123, 124, 125,
          126, 126, 127, 128, 129, 129, 130, 131, 132, 132, 133, 134, 134, 135,
          136, 137, 137, 138, 139, 140, 140, 141, 142, 142, 143, 144, 145, 145,
          146, 146, 148, 148, 149, 149, 150, 151, 152, 152, 153, 153, 154, 155,
          156, 156, 157, 157, 158, 159, 160, 160, 161, 161, 162, 162, 163, 164,
          164, 165, 165, 166, 166, 167, 168, 168, 169, 169, 170, 170, 171, 172,
          172, 173, 173, 174, 174, 175, 176, 176, 177, 177, 177, 178, 178, 179,
          180, 180, 181, 181, 181, 182, 182, 183, 184, 184, 184, 185, 185, 186,
          186, 186, 187, 188, 188, 188, 189, 189, 189, 190, 190, 191, 191, 192,
          192, 193, 193, 193, 194, 194, 194, 195, 196, 196, 196, 197, 197, 197,
          198, 199]
    }


def get_average_pixel(file_in, x0, y0, x1, y1):
    image_in = Image.open(file_in)
    image_in = image_in.convert('RGB')
    r, g, b = 0, 0, 0
    count = 0
    for x in xrange(x0, x1):
        for y in xrange(y0, y1):
            tempr, tempg, tempb = image_in.getpixel((x, y))
            r += tempr
            g += tempg
            b += tempb
            count += 1
    # calculate averages
    return (r/count), (g/count), (b/count), count


def get_exif(fn):
    try:
        ret = {}
        i = Image.open(fn)
        info = i._getexif()
        for tag, value in info.items():
            decoded = TAGS.get(tag, tag)
            ret[decoded] = value
        return ret
    except Exception as e:
        return None


def get_date(fn):
    exif = get_exif(fn)
    if exif and 'DateTimeOriginal' in exif.keys():
        date = exif['DateTimeOriginal'].split(' ')[0].split(':')
    else:
        date = time.localtime(os.path.getctime(fn))
    return ('%s/%s/%s' % (date[2], date[1], date[0]))


def write_date(photo, date):
    im = Image.open(photo)
    fontsize = 1
    f = ImageFont.truetype(FONT, fontsize)
    while f.getsize(date)[0] < RATIO * im.size[0]:
        # iterate until the text size is just larger than the criteria
        fontsize += 1
        f = ImageFont.truetype(FONT, fontsize)
    f = ImageFont.truetype(FONT, fontsize - 1)
    d = ImageDraw.Draw(im)
    largo, alto = im.size
    l, a = f.getsize(date)
    if TOP:
        x0 = MARGIN
        y0 = MARGIN
    else:
        x0 = largo - l - MARGIN
        y0 = alto - a - MARGIN
    x1 = x0 + l
    y1 = y0 + a
    print '################'
    print x0, x1, y0, y1
    p = PixelCounter(photo)
    r, g, b, c = p.averagePixels(x0, y0, x1, y1)
    d.text((x0, y0), date, font=f, fill='rgb(%s,%s,%s)' % (
        255-r, 255-g, 255-b))
    im.save(photo)


def add_noise(im, noise_level=20):
    def pixel_noise(x, y, r, g, b):  # expect rgb; rgba will blow up
        noise = random.randint(0, noise_level) - noise_level / 2
        return (max(0, min(r + noise, 255)),
                max(0, min(g + noise, 255)),
                max(0, min(b + noise, 255)))
    modify_all_pixels(im, pixel_noise)
    return im


def modify_all_pixels(im, pixel_callback):
    width, height = im.size
    pxls = im.load()
    for x in xrange(width):
        for y in xrange(height):
            pxls[x, y] = pixel_callback(x, y, *pxls[x, y])


def vintage_colors(im, color_map=VINTAGE_COLOR_LEVELS):
    r_map = color_map['r']
    g_map = color_map['g']
    b_map = color_map['b']

    def adjust_levels(x, y, r, g, b):  # expect rgb; rgba will blow up
        return r_map[r], g_map[g], b_map[b]
    modify_all_pixels(im, adjust_levels)
    return im


def image2pixbuf(image):
    if image.mode != 'RGBA':
        image = image.convert('RGBA')
    buff = StringIO.StringIO()
    image.save(buff, 'ppm')
    contents = buff.getvalue()
    buff.close()
    loader = GdkPixbuf.PixbufLoader.new_with_type('pnm')
    loader.write(contents)
    pixbuf = loader.get_pixbuf()
    loader.close()
    return pixbuf


def image2pixbuf2(image):
    arr = array.array('B', image.tostring())
    height, width = image.size
    return GdkPixbuf.Pixbuf.new_from_data(
        arr, GdkPixbuf.Colorspace.RGB, True, 8, width, height,
        width * 4, None, None)


def pixbuf2Image(pixbuf):
    width, height = pixbuf.get_width(), pixbuf.get_height()
    return Image.fromstring("RGBA", (width, height), pixbuf.get_pixels())


def makeShadow(image, iterations, border, offset, backgroundColour,
               shadowColour):
    # image: base image to give a drop shadow
    # iterations: number of times to apply the blur filter to the shadow
    # border: border to give the image to leave space for the shadow
    # offset: offset of the shadow as [x,y]
    # backgroundCOlour: colour of the background
    # shadowColour: colour of the drop shadow

    # Calculate the size of the shadow's image
    fullWidth = image.size[0] + abs(offset[0]) + 2 * border
    fullHeight = image.size[1] + abs(offset[1]) + 2 * border

    # Create the shadow's image. Match the parent image's mode.
    shadow = Image.new('RGBA', (fullWidth, fullHeight))

    # Place the shadow, with the required offset
    shadowLeft = border + max(offset[0], 0)
    shadowTop = border + max(offset[1], 0)
    # Paste in the constant colour
    shadow.paste(shadowColour,
                 [shadowLeft, shadowTop,
                  shadowLeft + image.size[0],
                  shadowTop + image.size[1]])

    # Apply the BLUR filter repeatedly
    for i in range(iterations):
        shadow = shadow.filter(ImageFilter.BLUR)

    # Paste the original image on top of the shadow
    imgLeft = border - min(offset[0], 0)
    imgTop = border - min(offset[1], 0)
    shadow.paste(image, (imgLeft, imgTop))

    return shadow


def watermark_image(file_in, overwrite, file_watermark, horizontal_position,
                    vertical_position):
    image_in = Image.open(file_in)
    image_watermark = Image.open(file_watermark)
    width_original, height_original = image_in.size
    width_watermark, height_watermark = image_watermark.size
    if width_original < width_watermark:
        width = width_watermark
    else:
        width = width_original
    if height_original < height_watermark:
        height = height_watermark
    else:
        height = height_original
    image_out = Image.new('RGBA', (width, height))
    image_out.paste(image_in, (int((width - width_original) / 2),
                    int((height - height_original) / 2)))
    if horizontal_position == 0:
        watermark_left = 0
    elif horizontal_position == 1:
        watermark_left = int((width - width_watermark) / 2)
    else:
        watermark_left = int(width - width_watermark)
    if vertical_position == 0:
        watermark_top = 0
    elif vertical_position == 1:
        watermark_top = int((height - height_watermark) / 2)
    else:
        watermark_top = int(height - height_watermark)
    try:
        image_watermark = image_watermark.convert('RGBA')
    except Exception as e:
        print(e)
        pass
    image_out.paste(image_watermark,
                    (watermark_left, watermark_top), mask=image_watermark)
    if overwrite:
        image_out.save(file_in)
    else:
        basename, extension = os.path.splitext(file_in)
        new_basename = basename + '_wartermark'
        image_out.save(new_basename + extension)


def filter_image(file_in, overwrite, afilter, filter_extension):
    image_in = Image.open(file_in)
    image_out = image_in.filter(afilter)
    if overwrite:
        image_out.save(file_in)
    else:
        basename, extension = os.path.splitext(file_in)
        new_basename = basename + '_' + filter_extension
        image_out.save(new_basename + extension)


def shadow_image(file_in, overwrite=False, iterations=8, border=-1,
                 offset=(20, 20), backgroundColour='white',
                 shadowColour='#444444'):
    image_in = Image.open(file_in)
    if border < 0:
        width, height = image_in.size
        if width > height:
            border = int(0.02 * width)
        else:
            border = int(0.02 * height)
    offset = (int(border / 2), int(border / 2))
    image_out = makeShadow(image_in, iterations, border, offset,
                           backgroundColour, shadowColour)
    if overwrite:
        image_out.save(file_in)
    else:
        basename, extension = os.path.splitext(file_in)
        new_basename = basename + '_with_shadow'
        image_out.save(new_basename + extension)


def blur_image(file_in, overwrite=False):
    filter_image(file_in, overwrite, ImageFilter.BLUR, 'blur')


def contour_image(file_in, overwrite=False):
    filter_image(file_in, overwrite, ImageFilter.CONTOUR, 'contour')


def detail_image(file_in, overwrite=False):
    filter_image(file_in, overwrite, ImageFilter.DETAIL, 'detail')


def edge_enhance_image(file_in, overwrite=False):
    filter_image(file_in, overwrite, ImageFilter.EDGE_ENHANCE, 'edge_enhance')


def edge_enhance_more_image(file_in, overwrite=False):
    filter_image(file_in, overwrite, ImageFilter.EDGE_ENHANCE_MORE,
                 'edge_enhance_more')


def emboss_image(file_in, overwrite=False):
    filter_image(file_in, overwrite, ImageFilter.EMBOSS, 'emboss')


def find_edges_image(file_in, overwrite=False):
    filter_image(file_in, overwrite, ImageFilter.FIND_EDGES, 'find_edges')


def smooth_image(file_in, overwrite=False):
    filter_image(file_in, overwrite, ImageFilter.SMOOTH, 'smooth')


def smooth_more_image(file_in, overwrite=False):
    filter_image(file_in, overwrite, ImageFilter.SMOOTH, 'smooth_more')


def sharpen_image(file_in, overwrite=False):
    filter_image(file_in, overwrite, ImageFilter.SHARPEN, 'sharpen')


def enhance_image(file_in, overwrite=False, brightness=100, color=100,
                  contrast=100, sharpness=100):
    image_in = Image.open(file_in)
    if int(brightness) != 100:
        enhancer = ImageEnhance.Brightness(image_in)
        image_in = enhancer.enhance(float(brightness / 100.0))
    if int(color * 100) != 100:
        enhancer = ImageEnhance.Color(image_in)
        image_in = enhancer.enhance(float(color / 100.0))
    if int(contrast * 100) != 100:
        enhancer = ImageEnhance.Contrast(image_in)
        image_in = enhancer.enhance(float(contrast / 100.0))
    if int(sharpness * 100) != 100:
        enhancer = ImageEnhance.Sharpness(image_in)
        image_in = enhancer.enhance(float(sharpness / 100.0))
    if overwrite:
        image_in.save(file_in)
    else:
        basename, extension = os.path.splitext(file_in)
        new_basename = basename + '_enhance'
        image_in.save(new_basename + extension)


def resize_image(file_in, overwrite=False, maintain_aspect_ratio=False,
                 percentage_width=True, percentage_height=True,
                 new_width=50, new_height=50):
    image_in = Image.open(file_in)
    width, height = image_in.size
    if percentage_width:
        new_width = int(width * new_width / 100)
    else:
        new_width = int(new_width)
    if maintain_aspect_ratio:
        new_height = height * new_width / width
    else:
        if percentage_height:
            new_height = int(height * new_height / 100)
        else:
            new_height = int(new_height)
    image_out = image_in.resize((new_width, new_height), Image.ANTIALIAS)
    if overwrite:
        image_out.save(file_in)
    else:
        basename, extension = os.path.splitext(file_in)
        new_basename = basename + '_resize'
        image_out.save(new_basename + extension)


def black_white_image(file_in, overwrite=False):
    image_in = Image.open(file_in)
    image_out = image_in.convert('1')
    if overwrite:
        image_out.save(file_in)
    else:
        basename, extension = os.path.splitext(file_in)
        new_basename = basename + '_black_and_White'
        image_out.save(new_basename + extension)


def greyscale_image(file_in, overwrite=False):
    image_in = Image.open(file_in)
    image_out = image_in.convert('LA')
    if overwrite:
        image_out.save(file_in)
    else:
        basename, extension = os.path.splitext(file_in)
        new_basename = basename + '_greyscale'
        try:
            image_out.save(new_basename + extension)
        except Exception as e:
            print(e)


def negative_image(file_in, overwrite=False):
    image_in = Image.open(file_in)
    image_out = ImageChops.invert(image_in)
    if overwrite:
        image_out.save(file_in)
    else:
        basename, extension = os.path.splitext(file_in)
        new_basename = basename + '_negative'
        image_out.save(new_basename + extension)


def date_image(file_in, overwrite=False):
    image_in = Image.open(file_in)
    date = get_date(file_in)
    fontsize = 1
    f = ImageFont.truetype(FONT, fontsize)
    while f.getsize(date)[0] < RATIO * image_in.size[0]:
        # iterate until the text size is just larger than the criteria
        fontsize += 1
        f = ImageFont.truetype(FONT, fontsize)
    f = ImageFont.truetype(FONT, fontsize - 1)
    d = ImageDraw.Draw(image_in)
    largo, alto = image_in.size
    l, a = f.getsize(date)
    if TOP:
        x0 = MARGIN
        y0 = MARGIN
    else:
        x0 = largo - l - MARGIN
        y0 = alto - a - MARGIN
    x1 = x0 + l
    y1 = y0 + a
    r, g, b, c = get_average_pixel(file_in, x0, y0, x1, y1)
    d.text((x0, y0), date, font=f,
           fill='rgb(%s, %s, %s)' % (255 - r, 255 - g, 255 - b))
    if overwrite:
        image_in.save(file_in)
    else:
        basename, extension = os.path.splitext(file_in)
        new_basename = basename + '_with_date'
        image_in.save(new_basename + extension)


def border_image(file_in, overwrite=False, border_width=-1, fill='white'):
    image_in = Image.open(file_in)
    if border_width < 0:
        width, height = image_in.size
        if width > height:
            border_width = int(0.02 * width)
        else:
            border_width = int(0.02 * height)
    image_out = ImageOps.expand(image_in, border_width, fill)
    if overwrite:
        image_out.save(file_in)
    else:
        basename, extension = os.path.splitext(file_in)
        new_basename = basename + '_with_border'
        image_out.save(new_basename + extension)


def vintage_image(file_in, overwrite=False, noise_level=20):
    image_in = Image.open(file_in)
    if image_in.mode != 'RGB':
        image_in = image_in.convert('RGB')
    vintage_colors(image_in)
    add_noise(image_in)
    if overwrite:
        image_in.save(file_in)
    else:
        basename, extension = os.path.splitext(file_in)
        new_basename = basename + '_vintage'
        image_in.save(new_basename + extension)


def rotate_image(file_in, overwrite=True, degrees=90):
    print(degrees)
    image_in = Image.open(file_in)
    image_out = image_in.rotate(degrees, Image.BICUBIC, True)
    if overwrite:
        image_out.save(file_in)
    else:
        basename, extension = os.path.splitext(file_in)
        new_basename = basename + '_rotated'
        image_out.save(new_basename + extension)


def convert_image(file_in, new_extension):
    image_in = Image.open(file_in)
    basename, old_extension = os.path.splitext(file_in)
    if not new_extension.startswith('.'):
        new_extension = '.' + new_extension
    image_out = image_in.save(basename + new_extension)


def flip_image(file_in, overwrite=True, horizontal=True):
    image_in = Image.open(file_in)
    if horizontal:
        image_out = image_in.transpose(Image.FLIP_LEFT_RIGHT)
    else:
        image_out = image_in.transpose(Image.FLIP_TOP_BOTTOM)
    if overwrite:
        image_out.save(file_in)
    else:
        basename, extension = os.path.splitext(file_in)
        new_basename = basename + '_flipped'
        image_out.save(new_basename + extension)


def get_files(files_in):
    files = []
    for file_in in files_in:
        file_in = urllib.unquote(file_in.get_uri()[7:])
        fileName, fileExtension = os.path.splitext(file_in)
        if fileExtension.lower() in EXTENSIONS and os.path.isfile(file_in):
            files.append(file_in)
    return files

########################################################################


"""
Tools to manipulate pdf
"""


class ImageToolsMenuProvider(GObject.GObject, FileManager.MenuProvider):
    """Implements the 'Replace in Filenames' extension to the FileManager
       right-click menu"""

    def __init__(self):
        pass

    def all_files_are_images(self, items):
        for item in items:
            fileName, fileExtension = os.path.splitext(item.get_uri()[7:])
            if fileExtension.lower() in EXTENSIONS:
                return True
        return False

    def about(self, widget, window):
        ad = Gtk.AboutDialog(parent=window)
        ad.set_name(APP)
        ad.set_version(VERSION)
        ad.set_copyright('Copyrignt (c) 2016\nLorenzo Carbonell')
        ad.set_comments(APP)
        ad.set_license('''
This program is free software: you can redistribute it and/or modify it under
the terms of the GNU General Public License as published by the Free Software
Foundation, either version 3 of the License, or (at your option) any later
version.

This program is distributed in the hope that it will be useful, but WITHOUT
ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
FOR A PARTICULAR PURPOSE. See the GNU General Public License for more details.

You should have received a copy of the GNU General Public License along with
this program. If not, see <http://www.gnu.org/licenses/>.
''')
        ad.set_website('http://www.atareao.es')
        ad.set_website_label('http://www.atareao.es')
        ad.set_authors([
            'Lorenzo Carbonell <lorenzo.carbonell.cerezo@gmail.com>'])
        ad.set_documenters([
            'Lorenzo Carbonell <lorenzo.carbonell.cerezo@gmail.com>'])
        ad.set_icon_name(APP)
        ad.set_logo_icon_name(APP)
        ad.run()
        ad.destroy()

    def enhance_images(self, menu_item, window, sel_items):
        files = get_files(sel_items)
        if len(files) > 0:
            rd = EnhanceDialog(_('Enhance image'), files[0])
            if rd.run() == Gtk.ResponseType.ACCEPT:
                rd.hide()
                process_files(_('Enhance images'), window, files,
                              enhance_image,
                              (rd.rbutton0.get_active(),
                               rd.slider1.get_value(),
                               rd.slider2.get_value(),
                               rd.slider3.get_value(),
                               rd.slider4.get_value()))
            rd.destroy()

    def rotate_images(self, menu_item, window, sel_items):
        files = get_files(sel_items)
        if len(files) > 0:
            rd = RotateDialog()
            if rd.run() == Gtk.ResponseType.ACCEPT:
                if rd.rbutton1.get_active():
                    degrees = rd.sp.get_value()
                else:
                    degrees = 360 - rd.sp.get_value()
                rd.hide()
                process_files(_('Rotate images'), window, files,
                              rotate_image,
                              (rd.rbutton0.get_active(),
                               degrees))
            rd.destroy()

    def resize_images(self, menu_item, window, sel_items):
        files = get_files(sel_items)
        if len(files) > 0:
            rd = ResizeDialog()
            im = Image.open(files[0])
            width, height = im.size
            rd.width_pixels.set_text(str(width))
            rd.height_pixels.set_text(str(height))
            if rd.run() == Gtk.ResponseType.ACCEPT:
                pw = rd.get_percentage_width()
                ph = rd.get_percentage_height()
                width = rd.get_width()
                height = rd.get_height()
                rd.hide()
                process_files(files, resize_image, rd.rbutton0.get_active(),
                              rd.rbutton1.get_active(), pw, ph, width, height)
                process_files(_('Resize images'), window, files,
                              resize_image,
                              (rd.rbutton0.get_active(),
                               rd.rbutton1.get_active(),
                               pw, ph, width, height))
            rd.destroy()

    def flip_images(self, *args):
        menu_item, sel_items = args
        files = get_files(sel_items)
        if len(files) > 0:
            rd = FlipDialog()
            if rd.run() == Gtk.ResponseType.ACCEPT:
                rd.hide()
                process_files(files, flip_image, rd.rbutton0.get_active(),
                              rd.rbutton1.get_active())
            rd.destroy()

    def negative_images(self, *args):
        menu_item, sel_items = args
        files = get_files(sel_items)
        if len(files) > 0:
            rd = DefaultDialog(_('Negative'))
            if rd.run() == Gtk.ResponseType.ACCEPT:
                rd.hide()
                process_files(files, negative_image, rd.rbutton0.get_active())
            rd.destroy()

    def black_and_white_images(self, *args):
        menu_item, sel_items = args
        files = get_files(sel_items)
        if len(files) > 0:
            rd = DefaultDialog(_('Black & White'))
            if rd.run() == Gtk.ResponseType.ACCEPT:
                rd.hide()
                process_files(files, black_white_image,
                              rd.rbutton0.get_active())
            rd.destroy()

    def greyscale_images(self, *args):
        menu_item, sel_items = args
        files = get_files(sel_items)
        if len(files) > 0:
            rd = DefaultDialog(_('Grey scale'))
            if rd.run() == Gtk.ResponseType.ACCEPT:
                process_files(files,
                              greyscale_image,
                              rd.rbutton0.get_active())
            rd.destroy()

    def vintage_images(self, *args):
        menu_item, sel_items = args
        files = get_files(sel_items)
        if len(files) > 0:
            rd = VintageDialog(_('Vintage'), files[0])
            if rd.run() == Gtk.ResponseType.ACCEPT:
                rd.hide()
                process_files(files, vintage_image, rd.rbutton0.get_active(),
                              rd.slider1.get_value())
            rd.destroy()

    def blur_images(self, *args):
        menu_item, sel_items = args
        files = get_files(sel_items)
        if len(files) > 0:
            rd = DefaultDialog(_('Blur'))
            if rd.run() == Gtk.ResponseType.ACCEPT:
                rd.hide()
                process_files(files, blur_image, rd.rbutton0.get_active())
            rd.destroy()

    def contour_images(self, *args):
        menu_item, sel_items = args
        files = get_files(sel_items)
        if len(files) > 0:
            rd = DefaultDialog(_('Contour'))
            if rd.run() == Gtk.ResponseType.ACCEPT:
                rd.hide()
                process_files(files, contour_image, rd.rbutton0.get_active())
            rd.destroy()

    def shadow_images(self, *args):
        menu_item, sel_items = args
        files = get_files(sel_items)
        if len(files) > 0:
            rd = DefaultDialog(_('Shadow'))
            if rd.run() == Gtk.ResponseType.ACCEPT:
                rd.hide()
                process_files(files, shadow_image, rd.rbutton0.get_active())
            rd.destroy()

    def watermark_images(self, menu_item, sel_items, window):
        files = get_files(sel_items)
        if len(files) > 0:
            rd = WatermarkDialog(files[0])
            if rd.run() == Gtk.ResponseType.ACCEPT:
                rd.hide()
                process_files(files, watermark_image, rd.rbutton0.get_active(),
                              rd.entry.get_text(), rd.get_horizontal_option(),
                              rd.get_vertical_option())
            rd.destroy()

    def border_images(self, menu_item, sel_items, window):
        files = get_files(sel_items)
        if len(files) > 0:
            rd = DefaultDialog(_('Border'))
            if rd.run() == Gtk.ResponseType.ACCEPT:
                rd.hide()
                process_files(files, border_image, rd.rbutton0.get_active(),
                              -1, 'white')

                diib = DoItInBackground(files,
                                        border_image,
                                        (rd.rbutton0.get_active(),
                                         -1, 'white'))
                progreso = Progreso(_('Convert images'),
                                    window)
                diib.connect('started', progreso.set_max_value)
                diib.connect('start_one', progreso.set_element)
                diib.connect('end_one', progreso.increase)
                diib.connect('ended', progreso.close)
                progreso.connect('i-want-stop', diib.stop)
                diib.start()
                progreso.run()
                process_files(files, convert_image, rd.get_convert_to())
            rd.destroy()

    def convert_images(self, menu_item, sel_items, window):
        files = get_files(sel_items)
        if len(files) > 0:
            rd = ConvertDialog(window)
            if rd.run() == Gtk.ResponseType.ACCEPT:
                convert_to = rd.get_convert_to()
                rd.destroy()
                diib = DoItInBackground(files,
                                        convert_image,
                                        (convert_to))
                progreso = Progreso(_('Convert images'),
                                    window)
                diib.connect('started', progreso.set_max_value)
                diib.connect('start_one', progreso.set_element)
                diib.connect('end_one', progreso.increase)
                diib.connect('ended', progreso.close)
                progreso.connect('i-want-stop', diib.stop)
                diib.start()
                progreso.run()
                process_files(files, convert_image, rd.get_convert_to())
            else:
                rd.destroy()

    def get_file_items(self, window, sel_items):
        if not self.all_files_are_images(sel_items):
            return
        top_menuitem = FileManager.MenuItem(
            name='ImageToolsMenuProvider::Gtk-image-tools',
            label=_('Image tools'),
            tip=_('Tools to work with images'))
        #
        submenu = FileManager.Menu()
        top_menuitem.set_submenu(submenu)
        #
        items = [('rotate', _('Rotate'), _('Rotate images'),
                  self.rotate_images),
                 ('enhance', _('Enhance'), _('Enhance images'),
                  self.enhance_images),
                 ('negative', _('Negative'), _('Negative images'),
                  self.negative_images),
                 ('flip', _('Flip'), _('Flip images'),
                  self.flip_images),
                 ('resize', _('Resize'), _('Resize images'),
                  self.resize_images),
                 ('black_and_white', _('Black and white'),
                  _('Transform images to black and white'),
                  self.black_and_white_images),
                 ('greyscale', _('Greyscale'),
                  _('Transform images to grey scale'),
                  self.greyscale_images),
                 ('vintage', _('Vintage'),
                  _('Apply vintage effect'),
                  self.vintage_images),
                 ('blur', _('Blur'), _('Apply blur filter'),
                  self.blur_images),
                 ('shadow', _('Shadow'), _('Add shadow'),
                  self.shadow_images),
                 ('watermark', _('Watermark'),
                  _('Add a watermark'),
                  self.watermark_images),
                 ('contour', _('Contour'),
                  _('Apply contour filter'),
                  self.contour_images),
                 ('border', _('Border'), _('Add a border'),
                  self.border_images),
                 ('convert', _('Convert'),
                  _('Convert images to another format'),
                  self.convert_images),
        ]
        items = sorted(items, key=lambda item: item[1])
        for item in items:
            sub_menuitem = FileManager.MenuItem(
                name='ImageToolsMenuProvider::Gtk-image-tools-' + item[0],
                label=item[1],
                tip=item[2])
            sub_menuitem.connect('activate', item[3], window, sel_items)
            submenu.append_item(sub_menuitem)
        #
        sub_menuitem_99 = FileManager.MenuItem(
            name='ImageToolsMenuProvider::Gtk-image-tools-99',
            label=_('About'),
            tip=_('About'))
        sub_menuitem_99.connect('activate', self.about, window)
        submenu.append_item(sub_menuitem_99)
        #
        return top_menuitem,


if __name__ == '__main__':
    import mimetypes
    mimetypes.init()
    for extension in EXTENSIONS:
        print(extension)
    '''
    if len(sys.argv) < 2:
        dd2 = WatermarkDialog(
            '/home/atareao_s/Escritorio/IMG_20130804_113326.jpg')
        dd2.run()
    '''
    '''
    import glob
    files = glob.glob('*.png')
    wm = WatermarkDialog()
    wm.run()

    for afile in files:
        #rotate_image(afile,False,45)
        #flip_image(afile,False,False)
        #convert_image(afile,'png')
        #vintage_image(afile)
        #border_image(afile,border_width=20)
        #shadow_image(afile)
        #blur_image(afile)
        #sharpen_image(afile)
        #negative_image(afile)
        #greyscale_image(afile)
        #resize_image(afile,False,10)
        #date_image(afile)
        pass
    '''
    exit(0)
