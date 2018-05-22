#!/usr/bin/env python3
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
except Exception as e:
    print(e)
    exit(-1)
from gi.repository import Gtk
import os

_ = str
NAME = 'nautilus'


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
        label = Gtk.Label(_('Watermark')+':')
        vbox.pack_start(label, False, False, 0)
        self.entry = Gtk.Entry()
        self.entry.set_width_chars(50)
        self.entry.set_sensitive(False)
        vbox.pack_start(self.entry, True, True, 0)
        button = Gtk.Button(_('Choose File'))
        button.connect('clicked', self.on_button_clicked)
        vbox.pack_start(button, False, False, 0)
        #
        label = Gtk.Label(_('Horizontal position')+':')
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
        label = Gtk.Label(_('Vertical position')+':')
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
                self.scrolledwindow1.get_allocation().width)/float(
                self.pixbuf1.get_width())
            factor_h = float(
                self.scrolledwindow1.get_allocation().height)/float(
                self.pixbuf1.get_height())
            if factor_w < factor_h:
                factor = factor_w
            else:
                factor = factor_h
            self.scale = int(factor*100)
            w = int(self.pixbuf1.get_width()*factor)
            h = int(self.pixbuf1.get_height()*factor)
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
                            (int((width-width_original)/2),
                             int((height-height_original)/2)))
            horizontal_position = self.get_horizontal_option()
            vertical_position = self.get_vertical_option()
            if horizontal_position == 0:
                watermark_left = 0
            elif horizontal_position == 1:
                watermark_left = int((width-width_watermark)/2)
            else:
                watermark_left = int(width-width_watermark)
            if vertical_position == 0:
                watermark_top = 0
            elif vertical_position == 1:
                watermark_top = int((height-height_watermark)/2)
            else:
                watermark_top = int(height-height_watermark)
            try:
                image_watermark = image_watermark.convert('RGBA')
            except Exception as e:
                pass
            image_out.paste(
                image_watermark, (watermark_left, watermark_top),
                mask=image_watermark)
            self.pixbuf2 = image2pixbuf(image_out)
            w = int(self.pixbuf1.get_width()*self.scale/100)
            h = int(self.pixbuf1.get_height()*self.scale/100)
            self.image2.set_from_pixbuf(
                self.pixbuf2.scale_simple(w, h, GdkPixbuf.InterpType.BILINEAR))

    def on_key_release_event(self, widget, event):
        print((event.keyval))
        if event.keyval == 65451 or event.keyval == 43:
            self.scale = self.scale*1.1
        elif event.keyval == 65453 or event.keyval == 45:
            self.scale = self.scale*.9
        elif event.keyval == 65456 or event.keyval == 48:
            factor_w = float(
                self.scrolledwindow1.get_allocation().width)/float(
                self.pixbuf1.get_width())
            factor_h = float(
                self.scrolledwindow1.get_allocation().height)/float(
                self.pixbuf1.get_height())
            if factor_w < factor_h:
                factor = factor_w
            else:
                factor = factor_h
            self.scale = int(factor*100)
            w = int(self.pixbuf1.get_width()*factor)
            h = int(self.pixbuf1.get_height()*factor)
            #
            self.image1.set_from_pixbuf(
                self.pixbuf1.scale_simple(w, h, GdkPixbuf.InterpType.BILINEAR))
            self.image2.set_from_pixbuf(
                self.pixbuf2.scale_simple(w, h, GdkPixbuf.InterpType.BILINEAR))
        elif event.keyval == 65457 or event.keyval == 49:
            self.scale = 100
        if self.image1:
            w = int(self.pixbuf1.get_width()*self.scale/100)
            h = int(self.pixbuf1.get_height()*self.scale/100)
            #
            self.image1.set_from_pixbuf(
                self.pixbuf1.scale_simple(w, h, GdkPixbuf.InterpType.BILINEAR))
            self.image2.set_from_pixbuf(
                self.pixbuf2.scale_simple(w, h, GdkPixbuf.InterpType.BILINEAR))

    def close_application(self, widget):
        self.hide()


if __name__ == '__main__':
    dialog = WatermarkDialog()
    dialog.run()
    exit(0)
