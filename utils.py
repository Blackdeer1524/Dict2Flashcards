import copy
from functools import partial
from io import BytesIO
from tkinter import Button, Checkbutton, Text, Label, Frame, Toplevel, Entry, Canvas, Scrollbar, OptionMenu, \
                    StringVar, BooleanVar
from tkinter import messagebox
from tkinter import ttk
import sys
import os

from PIL import Image, ImageTk, ImageGrab
from enum import IntEnum
import requests
from requests.exceptions import ConnectionError, RequestException, ConnectTimeout
from concurrent.futures import ThreadPoolExecutor
import random
import traceback
import re
import shutil
from tkinterdnd2 import DND_FILES, DND_TEXT


LETTERS = set("abcdefghijklmnopqrstuvwxyz")
AUDIO_NAME_SPEC_CHARS = '/\\:*?\"<>| '


# Data structures
class Deque:
    def __init__(self, collection=None):
        """
        :param collection: iterable
        """
        self.deque = collection if collection is not None else []

    def __len__(self):
        return len(self.deque)

    def __bool__(self):
        return bool(self.deque)

    def pop(self, n=1) -> list:
        return [self.deque.pop() for _ in range(min(n, len(self.deque)))]

    def popleft(self, n=1) -> list:
        return [self.deque.pop(0) for _ in range(min(n, len(self.deque)))]

    def append(self, item):
        self.deque.append(item)

    def appendleft(self, item):
        self.deque.insert(0, item)

    def extend(self, collection):
        self.deque.extend(collection)

    def extendleft(self, collection):
        for i in range(len(collection)-1, -1, -1):
            self.appendleft(collection[i])

    def __repr__(self):
        return f"Deque {self.deque}"


# Widgets
class TextWithPlaceholder(Text):
    def __init__(self, master, placeholder="", placeholder_fg_color="grey", *args, **kwargs):
        super(TextWithPlaceholder, self).__init__(master=master, *args, **kwargs)
        self.placeholder = placeholder
        self.placeholder_fg_color = placeholder_fg_color
        self.default_fg_color = self["foreground"]
        self.bind("<FocusIn>", self._foc_in)
        self.bind("<FocusOut>", self._foc_out)
        self["wrap"] = "word"
        self.under_focus = False

    def get(self, index1, index2=None):
        if self["foreground"] == self.placeholder_fg_color:
            return ""
        else:
            return self.tk.call(self._w, 'get', index1, index2)

    def _foc_in(self, *args):
        self.under_focus = True
        if self["foreground"] == self.placeholder_fg_color:
            self.delete(1.0, 'end')
            self['foreground'] = self.default_fg_color

    def fill_placeholder(self, *args):
        self['foreground'] = self.placeholder_fg_color
        self.insert(1.0, self.placeholder)

    def _foc_out(self, *args):
        self.under_focus = False
        if not self.get(1.0).strip():
            self.fill_placeholder()


class EntryWithPlaceholder(Entry):
    def __init__(self, master, placeholder="", placeholder_fg_color='grey', *args, **kwargs):
        super().__init__(master=master, *args, **kwargs)
        self.placeholder = placeholder
        self.placeholder_fg_color = placeholder_fg_color
        self.default_fg_color = self['foreground']
        self.bind("<FocusIn>", self._foc_in)
        self.bind("<FocusOut>", self._foc_out)
        self.under_focus = False

    def get(self):
        if self["foreground"] == self.placeholder_fg_color:
            return ""
        else:
            return self.tk.call(self._w, 'get')

    def _foc_in(self, *args):
        self.under_focus = True
        if self["foreground"] == self.placeholder_fg_color:
            self.delete(0, 'end')
            self['foreground'] = self.default_fg_color

    def fill_placeholder(self, *args):
        self['foreground'] = self.placeholder_fg_color
        self.insert(0, self.placeholder)

    def _foc_out(self, *args):
        self.under_focus = False
        if not self.get().strip():
            self.fill_placeholder()


# functions
class SearchType(IntEnum):
    exact = 0
    forward = 1
    backward = 2
    everywhere = 3


def string_search(source, query, search_type=3, case_sencitive=True):
    """
    :param source: where to search
    :param query: what to search
    :param search_type:
        exact = 0
        forward = 1
        backward = 2
        everywhere = 3
    :param case_sencitive:
    :return:
    """
    query = query.strip()
    if search_type == SearchType.exact:
        search_pattern = r"\b{}\b".format(query)
    elif search_type == SearchType.forward:
        search_pattern = r"\b{}".format(query)
    elif search_type == SearchType.backward:
        search_pattern = r"{}\b".format(query)
    else:
        search_pattern = r"{}".format(query)

    if not case_sencitive:
        pattern = re.compile(search_pattern, re.IGNORECASE)
    else:
        pattern = re.compile(search_pattern)

    if re.search(pattern, source):
        return True
    return False


def remove_special_chars(text, sep=" ", special_chars='№!"#$%&\'()*+,-./:;<=>?@[\\]^_`{|}~ '):
    """
    :param text: to to clean
    :param sep: replacement for special chars
    :param special_chars: special characters to remove
    :return:
    """
    new_text = ""
    start_index = 0
    while start_index < len(text) and text[start_index] in special_chars:
        start_index += 1

    while start_index < len(text):
        if text[start_index] in special_chars:
            while text[start_index] in special_chars:
                start_index += 1
                if start_index >= len(text):
                    return new_text
            new_text += sep
        new_text += text[start_index]
        start_index += 1
    return new_text


def spawn_toplevel_in_center(master, toplevel_widget, desired_toplevel_width=0, desired_toplevel_height=0):
    def get_center_spawn_conf():
        """
        :param master: master of placing widget
        :param placing_widget_width: current window width
        :param placing_widget_height: current window height
        :return: widget spawn conf
        """
        nonlocal master, width, height
        # получение координат на экране через self.winfo_rootx(), self.winfo_rooty() даёт некоторое смещение
        master_size, master_position_on_screen_x, master_position_on_screen_y = master.winfo_geometry().split(sep="+")
        master_width, master_height = master_size.split(sep="x")
        master_window_center_x = int(master_position_on_screen_x) + int(master_width) // 2
        master_window_center_y = int(master_position_on_screen_y) + int(master_height) // 2
        window_size = f"{width}x{height}"
        spawn_cords = f"+{master_window_center_x - width // 2}+{master_window_center_y - height // 2}"
        return window_size + spawn_cords

    toplevel_widget.update()
    width = desired_toplevel_width if desired_toplevel_width else toplevel_widget.winfo_width()
    height = desired_toplevel_height if desired_toplevel_height else toplevel_widget.winfo_height()
    toplevel_widget.geometry(get_center_spawn_conf())
    toplevel_widget.resizable(0, 0)
    toplevel_widget.grab_set()


def get_option_menu(master, init_text, values, command, widget_configuration=None, option_submenu_params=None):
    if widget_configuration is None:
        widget_configuration = {}
    if option_submenu_params is None:
        option_submenu_params = {}

    var = StringVar()
    var.set(init_text)
    option_menu = OptionMenu(master, var, *values, command=command)
    option_menu.configure(**widget_configuration)
    for submenu_index in range(len(values)):
        option_menu["menu"].entryconfig(submenu_index, **option_submenu_params)
    return option_menu


def get_save_audio_name(word: str, pos: str, wp_name: str) -> str:
    word = word.strip().lower()
    if pos:
        raw_audio_name = f"{remove_special_chars(word, sep='-')}-{remove_special_chars(pos, sep='-')}"
    else:
        raw_audio_name = remove_special_chars(word, sep='-')
    prepared_word_parser_name = remove_special_chars(wp_name, sep='-')
    audio_name = f"mined-{raw_audio_name}-{prepared_word_parser_name}.mp3"
    return audio_name


def get_local_audio_path(word, pos="", local_audio_folder_path="./", with_pos=True):
    word = word.strip().lower()
    if not word:
        return ""

    letter_group = word[0] if word[0] in LETTERS else "0-9"
    name = f"{remove_special_chars(word.lower(), '-', AUDIO_NAME_SPEC_CHARS)}.mp3"
    search_root = os.path.join(local_audio_folder_path, letter_group)
    if with_pos:
        pos = remove_special_chars(pos.lower(), '-', AUDIO_NAME_SPEC_CHARS)
        res = os.path.join(search_root, pos, name)
    else:
        res = ""
        for current_dir_path, dirs, files in os.walk(search_root):
            if name in files:
                res = os.path.join(current_dir_path, name)
                break
    return res if os.path.exists(res) else ""


def error_handler(error_processing=None):
    def error_decorator(func):
        def method_wrapper(self, *args, **kwargs):
            try:
                return func(self, *args, **kwargs)
            except Exception as e:
                if error_processing is None:
                    exc_type, exc_value, exc_traceback = sys.exc_info()
                    lines = traceback.format_exception(exc_type, exc_value, exc_traceback)
                    error_log = ''.join(lines)
                    print(error_log)
                else:
                    error_processing(self, e, *args, **kwargs)
        return method_wrapper
    return error_decorator


# classes
class ScrolledFrame(Frame):
    """Implementation of the scrollable frame widget.
    Copyright (c) 2018 Benjamin Johnson
    Permission is hereby granted, free of charge, to any person obtaining a copy
    of this software and associated documentation files (the "Software"), to deal
    in the Software without restriction, including without limitation the rights
    to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
    copies of the Software, and to permit persons to whom the Software is
    furnished to do so, subject to the following conditions:
    The above copyright notice and this permission notice shall be included in all
    copies or substantial portions of the Software.
    THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
    IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
    FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
    AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
    LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
    OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
    SOFTWARE.

    Scrollable Frame widget.
    Use display_widget() to set the interior widget. For example,
    to display a Label with the text "Hello, world!", you can say:
        sf = ScrolledFrame(self)
        sf.pack()
        sf.display_widget(Label, text="Hello, world!")
    The constructor accepts the usual Tkinter keyword arguments, plus
    a handful of its own:
      scrollbars (str; default: "both")
        Which scrollbars to provide.
        Must be one of "vertical", "horizontal," "both", or "neither".
      use_ttk (bool; default: False)
        Whether to use ttk widgets if available.
        The default is to use standard Tk widgets. This setting has
        no effect if ttk is not available on your system.
    """
    def __init__(self, master=None, **kw):
        """Return a new scrollable frame widget."""

        Frame.__init__(self, master)

        # Hold these names for the interior widget
        self._interior = None
        self._interior_id = None

        # Whether to fit the interior widget's width to the canvas
        self._fit_width = False

        # Which scrollbars to provide
        if "scrollbars" in kw:
            scrollbars = kw["scrollbars"]
            del kw["scrollbars"]

            if not scrollbars:
                scrollbars = self._DEFAULT_SCROLLBARS
            elif not scrollbars in self._VALID_SCROLLBARS:
                raise ValueError("scrollbars parameter must be one of "
                                 "'vertical', 'horizontal', 'both', or "
                                 "'neither'")
        else:
            scrollbars = self._DEFAULT_SCROLLBARS

        # Default to a 1px sunken border
        if not "borderwidth" in kw:
            kw["borderwidth"] = 1
        if not "relief" in kw:
            kw["relief"] = "sunken"

        # Set up the grid
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # Canvas to hold the interior widget
        c = self._canvas = Canvas(self,
                                     borderwidth=0,
                                     highlightthickness=0,
                                     takefocus=0)

        # Enable scrolling when the canvas has the focus
        self.bind_arrow_keys(c)
        self.bind_scroll_wheel(c)

        # Call _resize_interior() when the canvas widget is updated
        c.bind("<Configure>", self._resize_interior)

        # Scrollbars
        xs = self._x_scrollbar = Scrollbar(self,
                                           orient="horizontal",
                                           command=c.xview)
        ys = self._y_scrollbar = Scrollbar(self,
                                           orient="vertical",
                                           command=c.yview)
        c.configure(xscrollcommand=xs.set, yscrollcommand=ys.set)

        # Lay out our widgets
        c.grid(row=0, column=0, sticky="nsew")
        if scrollbars == "vertical" or scrollbars == "both":
            ys.grid(row=0, column=1, sticky="ns")
        if scrollbars == "horizontal" or scrollbars == "both":
            xs.grid(row=1, column=0, sticky="we")

        # Forward these to the canvas widget
        self.bind = c.bind
        self.focus_set = c.focus_set
        self.unbind = c.unbind
        self.xview = c.xview
        self.xview_moveto = c.xview_moveto
        self.yview = c.yview
        self.yview_moveto = c.yview_moveto

        # Process our remaining configuration options
        self.configure(**kw)

    def __setitem__(self, key, value):
        """Configure resources of a widget."""

        if key in self._CANVAS_KEYS:
            # Forward these to the canvas widget
            self._canvas.configure(**{key: value})

        else:
            # Handle everything else normally
            Frame.configure(self, **{key: value})

    # ------------------------------------------------------------------------

    def bind_arrow_keys(self, widget):
        """Bind the specified widget's arrow key events to the canvas."""

        widget.bind("<Up>",
                    lambda event: self._canvas.yview_scroll(-1, "units"))

        widget.bind("<Down>",
                    lambda event: self._canvas.yview_scroll(1, "units"))

        widget.bind("<Left>",
                    lambda event: self._canvas.xview_scroll(-1, "units"))

        widget.bind("<Right>",
                    lambda event: self._canvas.xview_scroll(1, "units"))

    def bind_scroll_wheel(self, widget):
        """Bind the specified widget's mouse scroll event to the canvas."""

        widget.bind("<MouseWheel>", self._scroll_canvas)
        widget.bind("<Button-4>", self._scroll_canvas)
        widget.bind("<Button-5>", self._scroll_canvas)

    def cget(self, key):
        """Return the resource value for a KEY given as string."""

        if key in self._CANVAS_KEYS:
            return self._canvas.cget(key)

        else:
            return Frame.cget(self, key)

    # Also override this alias for cget()
    __getitem__ = cget

    def configure(self, cnf=None, **kw):
        """Configure resources of a widget."""

        # This is overridden so we can use our custom __setitem__()
        # to pass certain options directly to the canvas.
        if cnf:
            for key in cnf:
                self[key] = cnf[key]

        for key in kw:
            self[key] = kw[key]

    # Also override this alias for configure()
    config = configure

    def display_widget(self, widget_class, fit_width=False, **kw):
        """Create and display a new widget.
        If fit_width == True, the interior widget will be stretched as
        needed to fit the width of the frame.
        Keyword arguments are passed to the widget_class constructor.
        Returns the new widget.
        """

        # Blank the canvas
        self.erase()

        # Set width fitting
        self._fit_width = fit_width

        # Set the new interior widget
        self._interior = widget_class(self._canvas, **kw)

        # Add the interior widget to the canvas, and save its widget ID
        # for use in _resize_interior()
        self._interior_id = self._canvas.create_window(0, 0,
                                                       anchor="nw",
                                                       window=self._interior)

        # Call _update_scroll_region() when the interior widget is resized
        self._interior.bind("<Configure>", self._update_scroll_region)

        # Fit the interior widget to the canvas if requested
        # We don't need to check fit_width here since _resize_interior()
        # already does.
        self._resize_interior()

        # Scroll to the top-left corner of the canvas
        self.scroll_to_top()

        return self._interior

    def erase(self):
        """Erase the displayed widget."""

        # Clear the canvas
        self._canvas.delete("all")

        # Delete the interior widget
        del self._interior
        del self._interior_id

        # Save these names
        self._interior = None
        self._interior_id = None

        # Reset width fitting
        self._fit_width = False

    def scroll_to_top(self):
        """Scroll to the top-left corner of the canvas."""

        self._canvas.xview_moveto(0)
        self._canvas.yview_moveto(0)

    # ------------------------------------------------------------------------

    def _resize_interior(self, event=None):
        """Resize the interior widget to fit the canvas."""

        if self._fit_width and self._interior_id:
            # The current width of the canvas
            canvas_width = self._canvas.winfo_width()

            # The interior widget's requested width
            requested_width = self._interior.winfo_reqwidth()

            if requested_width != canvas_width:
                # Resize the interior widget
                new_width = max(canvas_width, requested_width)
                self._canvas.itemconfigure(self._interior_id, width=new_width)

    def _scroll_canvas(self, event):
        """Scroll the canvas."""

        c = self._canvas

        if sys.platform.startswith("darwin"):
            # macOS
            c.yview_scroll(-1 * event.delta, "units")

        elif event.num == 4:
            # Unix - scroll up
            c.yview_scroll(-1, "units")

        elif event.num == 5:
            # Unix - scroll down
            c.yview_scroll(1, "units")

        else:
            # Windows
            c.yview_scroll(-1 * (event.delta // 120), "units")

    def _update_scroll_region(self, event):
        """Update the scroll region when the interior widget is resized."""

        # The interior widget's requested width and height
        req_width = self._interior.winfo_reqwidth()
        req_height = self._interior.winfo_reqheight()

        # Set the scroll region to fit the interior widget
        self._canvas.configure(scrollregion=(0, 0, req_width, req_height))

    # ------------------------------------------------------------------------

    # Keys for configure() to forward to the canvas widget
    _CANVAS_KEYS = "width", "height", "takefocus"

    # Scrollbar-related configuration
    _DEFAULT_SCROLLBARS = "both"
    _VALID_SCROLLBARS = "vertical", "horizontal", "both", "neither"


class ImageSearch(Toplevel):
    class StatusCodes(IntEnum):
        NORMAL = 0
        RETRIABLE_FETCHING_ERROR = 1
        NON_RETRIABLE_FETCHING_ERROR = 2
        IMAGE_PROCESSING_ERROR = 3

    def __init__(self, master, search_term, saving_dir, **kwargs):
        """
        master: \n
        search_term: \n
        saving_dir: \n
        url_scrapper: function that returns image urls by given query\n
        max_request_tries: how many retries allowed per one image-showing cycle\n
        init_urls: custom urls to be displayed\n
        headers: request headers\n
        timeout: request timeout\n
        show_image_width: maximum image display width\n
        show_image_height: maximum image display height\n
        saving_image_width: maximum image saving width\n
        saving_image_height: maximum image saving height\n
        image_saving_name_pattern: modifies saving name. example: "this_image_{}"\n
        n_images_in_row: \n
        n_rows: \n
        button_padx: \n
        button_pady: \n
        window_width_limit: maximum width of the window\n
        window_height_limit: maximum height of the window\n
        window_bg: window background placeholder_fg_color\n
        entry_params(**kwargs)s: entry widget params\n
        command_button_params(**kwargs): "Show more" and "Download" buttons params\n
        on_close_action(**kwargs): additional action performed on closing.
        """
        self.search_term = search_term
        self.img_urls = Deque(kwargs.get("init_urls", []))
        self.url_scrapper = kwargs.get("url_scrapper")

        if self.search_term and self.url_scrapper is not None:
            try:
                self.img_urls.extend(self.url_scrapper(self.search_term))
            except ConnectionError:
                messagebox.showerror(message="Check your internet connection")

        self.button_bg = self.activebackground = "#FFFFFF"
        self.window_bg = kwargs.get("window_bg", "#F0F0F0")
        self.command_button_params = kwargs.get("command_button_params", {})
        self.entry_params = kwargs.get("entry_params", {})
        self.button_padx = kwargs.get("button_padx", 10)
        self.button_pady = kwargs.get("button_pady", 10)
        Toplevel.__init__(self, master, bg=self.window_bg)

        self.saving_dir = saving_dir

        self.headers = kwargs.get("headers")
        self.timeout = kwargs.get("timeout", 1)
        self.max_request_tries = kwargs.get("max_request_tries", 5)

        self.last_button_row = 0
        self.last_button_column = 0
        self.last_button_index = 0
        self.n_images_in_row = kwargs.get("n_images_in_row", 3)
        self.n_rows = kwargs.get("n_rows", 2)
        self.n_images_per_cycle = self.n_rows * self.n_images_in_row

        self.pool = ThreadPoolExecutor(max_workers=self.n_images_per_cycle)

        self.saving_images = []
        self.saving_images_names = []
        self.saving_indices = []

        self.image_saving_name_pattern = kwargs.get("image_saving_name_pattern", "{}")

        self.optimal_visual_width = kwargs.get("show_image_width")
        self.optimal_visual_height = kwargs.get("show_image_height")

        self.optimal_result_width = kwargs.get("saving_image_width")
        self.optimal_result_height = kwargs.get("saving_image_height")

        self.title("Image search")
        self.search_field = Entry(self, justify="center", **self.entry_params)
        self.search_field.insert(0, self.search_term)
        self.start_search_button = Button(self, text="Search", command=self.restart_search,
                                          **self.command_button_params)

        self.search_field.grid(row=0, column=0, sticky="news",
                               padx=(self.button_padx, 0), pady=self.button_pady)
        self.start_search_button.grid(row=0, column=1, sticky="news",
                                      padx=(0, self.button_padx), pady=self.button_pady)
        self.start_search_button["state"] = "normal" if self.url_scrapper else "disabled"

        self.sf = ScrolledFrame(self, scrollbars="both")
        self.sf.grid(row=1, column=0, columnspan=2)
        self.sf.bind_scroll_wheel(self)
        self.inner_frame = self.sf.display_widget(partial(Frame, bg=self.window_bg))

        window_width_limit = kwargs.get("window_width_limit")
        window_height_limit = kwargs.get("window_height_limit")
        self.window_width_limit = window_width_limit if window_width_limit is not None else \
            master.winfo_screenwidth() * 6 // 7
        self.window_height_limit = window_height_limit if window_height_limit is not None else \
            master.winfo_screenheight() * 2 // 3

        self.show_more_gen = self.show_more()

        self.show_more_button = Button(master=self, text="Show more",
                                       command=lambda x=self.show_more_gen: next(x), **self.command_button_params)
        self.download_button = Button(master=self, text="Download",
                                 command=lambda: self.close_image_search(), **self.command_button_params)
        self.show_more_button.grid(row=3, column=0, sticky="news")
        self.download_button.grid(row=3, column=1, sticky="news")

        self.on_closing_action = kwargs.get("on_close_action")

        self.resizable(0, 0)
        self.protocol("WM_DELETE_WINDOW", self.destroy)
        self.bind("<Escape>", lambda event: self.destroy())
        self.bind("<Return>", lambda event: self.close_image_search())
        self.bind("<Control-v>", lambda event: self.paste_image())
        self.drop_target_register(DND_FILES, DND_TEXT)
        self.dnd_bind('<<Drop>>', self.drop)

    def start(self):
        next(self.show_more_gen)
        self.resize()

    def restart_search(self):
        self.search_term = self.search_field.get()
        if not self.search_term:
            messagebox.showerror(message="Empty search query")
            return
        try:
            self.img_urls = Deque(self.url_scrapper(self.search_term))
        except ConnectionError:
            messagebox.showerror(message="Check your internet connection")
            return

        self.saving_images = []
        self.saving_images_names = []
        self.saving_indices = []

        self.last_button_row = 0
        self.last_button_column = 0
        self.last_button_index = 0

        self.show_more_gen = self.show_more()
        self.show_more_button.configure(command=lambda x=self.show_more_gen: next(x))

        self.inner_frame = self.sf.display_widget(partial(Frame, bg=self.window_bg))
        if self.img_urls:
            self.show_more_button["state"] = "normal"
            next(self.show_more_gen)
        else:
            self.show_more_button["state"] = "disabled"

    def destroy(self):
        if self.on_closing_action is not None:
            self.on_closing_action(self)
        super(ImageSearch, self).destroy()

    def resize(self):
        current_frame_width = self.inner_frame.winfo_width()
        current_frame_height = self.inner_frame.winfo_height()

        self.sf.config(width=min(self.window_width_limit, current_frame_width),
                       height=min(self.window_height_limit - self.command_widget_total_height,
                                  current_frame_height))

    def close_image_search(self):
        for saving_index in self.saving_indices:
            saving_image = self.preprocess_image(self.saving_images[saving_index],
                                              width=self.optimal_result_width,
                                              height=self.optimal_result_height)
            saving_image.save(f"{self.saving_dir}/{self.saving_images_names[saving_index]}.png")
        self.destroy()

    @staticmethod
    def preprocess_image(img, width: int = None, height: int = None):
        processed_img = copy.copy(img)
        if width is not None and processed_img.width > width:
            k_width = width / processed_img.width
            processed_img = processed_img.resize((width, int(processed_img.height * k_width)),
                                                 Image.ANTIALIAS)

        if height is not None and processed_img.height > height:
            k_height = height / processed_img.height
            processed_img = processed_img.resize((int(processed_img.width * k_height), height),
                                                 Image.ANTIALIAS)
        return processed_img

    def fetch_image(self, url):
        """
        fetches image from web
        :param url: image url
        :return: status, button_img, img
        """
        try:
            response = requests.get(url, headers=self.headers, timeout=self.timeout)
            response.raise_for_status()
            content = response.content
            return ImageSearch.StatusCodes.NORMAL, content, url
        except ConnectTimeout:
            return ImageSearch.StatusCodes.RETRIABLE_FETCHING_ERROR, None, None
        except RequestException:
            return ImageSearch.StatusCodes.NON_RETRIABLE_FETCHING_ERROR, None, None

    def schedule_batch_fetching(self, url_batch: list):
        image_fetch_tasks = []
        for url in url_batch:
            image_fetch_tasks.append(self.pool.submit(self.fetch_image, url))
        return image_fetch_tasks

    def process_bin_data(self, content=None):
        try:
            img = Image.open(BytesIO(content))
            button_img = ImageTk.PhotoImage(
                self.preprocess_image(img, width=self.optimal_visual_width, height=self.optimal_visual_height))
            return ImageSearch.StatusCodes.NORMAL, button_img, img
        except (IOError, UnicodeError):
            return ImageSearch.StatusCodes.IMAGE_PROCESSING_ERROR, None, None

    def choose_pic(self, button):
        if not button.is_picked:
            button["bg"] = "#FF0000"
            self.saving_indices.append(button.image_index)
        else:
            button["bg"] = self.button_bg
            self.saving_indices.remove(button.image_index)
        button.is_picked = not button.is_picked

    def place_buttons(self, button_image_batch):
        for j in range(len(button_image_batch)):
            b = Button(master=self.inner_frame, image=button_image_batch[j],
                       bg=self.button_bg, activebackground=self.activebackground)
            b.image = button_image_batch[j]
            b.image_index = self.last_button_index
            b.is_picked = False
            b["command"] = lambda current_button=b: self.choose_pic(current_button)
            b.grid(row=self.last_button_index // self.n_images_in_row,
                   column=self.last_button_index % self.n_images_in_row,
                   padx=self.button_padx, pady=self.button_pady, sticky="news")
            self.last_button_index += 1
        self.last_button_row = self.last_button_index // self.n_images_in_row
        self.last_button_column = self.last_button_index % self.n_images_in_row
        self.inner_frame.update()
        self.resize()

    def process_url_batch(self, batch_size, n_retries=0):
        """
        :param batch_size: how many images to process
        :param n_retries: (if some error occurred) replace "bad" image with the new one and tries to fetch it.
        :return:
        """

        def add_fetching_to_queue():
            nonlocal n_retries
            if self.img_urls and n_retries < self.max_request_tries:
                image_fetching_futures.append(self.pool.submit(self.fetch_image, self.img_urls.popleft()[0]))
                n_retries += 1

        button_images_batch = []
        url_batch = self.img_urls.popleft(batch_size)
        image_fetching_futures = self.schedule_batch_fetching(url_batch)

        while image_fetching_futures:
            fetching_status, content, url = image_fetching_futures.pop(0).result()
            if fetching_status == ImageSearch.StatusCodes.NORMAL:
                processing_status, button_img, img = self.process_bin_data(content)
                if processing_status == ImageSearch.StatusCodes.NORMAL:
                    hash_url = hash(url)
                    button_images_batch.append(button_img)
                    self.saving_images.append(img)
                    self.saving_images_names.append(self.image_saving_name_pattern.format(hash_url))
                else:
                    add_fetching_to_queue()
            elif fetching_status == ImageSearch.StatusCodes.RETRIABLE_FETCHING_ERROR:
                self.img_urls.append(url)
                add_fetching_to_queue()
            else:
                add_fetching_to_queue()
        self.place_buttons(button_images_batch)

    def show_more(self):
        self.update()
        self.command_widget_total_height = self.download_button.winfo_height() + self.search_field.winfo_height() + \
                                           2 * self.button_pady
        
        while self.img_urls:
            self.process_url_batch(self.n_images_per_cycle - self.last_button_column)
            if not self.img_urls:
                break
            yield
        self.show_more_button["state"] = "disabled"
        yield
    
    def process_single_image(self, img: Image):
        button_img_batch = [ImageTk.PhotoImage(
            self.preprocess_image(img, width=self.optimal_visual_width, height=self.optimal_visual_height))]
        self.saving_images.append(img)
        self.saving_images_names.append(self.image_saving_name_pattern.format(hash(random.random())))
        self.place_buttons(button_img_batch)
    
    def drop(self, event):
        if event.data:
            data_path = event.data
            if os.path.exists(data_path):
                img = Image.open(data_path)
                self.process_single_image(img)
            elif data_path.startswith("http"):
                self.img_urls.appendleft(data_path)
                self.process_url_batch(batch_size=1, n_retries=self.max_request_tries)
        return event.action

    def paste_image(self):
        self.process_single_image(ImageGrab.grabclipboard())


class AudioDownloader(Toplevel):
    class CopyEncounterAction(IntEnum):
        UNSPECIFIED = 0
        SKIP = 1
        REWRITE = 2

    def __init__(self, master, headers, timeout, request_delay=5_000,
                 temp_dir="./", saving_dir="./", local_media_dir="./",
                 toplevel_cfg=None, pb_cfg=None, label_cfg=None, button_cfg=None, checkbutton_cfg=None):
        self.toplevel_cfg = toplevel_cfg
        if self.toplevel_cfg is None:
            self.toplevel_cfg = {}
        if pb_cfg is None:
            pb_cfg = {}
        pb_cfg.pop("orient", None)
        pb_cfg.pop("mode", None)
        self.label_cfg = label_cfg
        if self.label_cfg is None:
            self.label_cfg = {}
        self.button_cfg = button_cfg
        if self.button_cfg is None:
            self.button_cfg = {}
        self.checkbutton_cfg = checkbutton_cfg
        if self.checkbutton_cfg is None:
            self.checkbutton_cfg = {}
        
        self.if_copy_encountered = AudioDownloader.CopyEncounterAction.UNSPECIFIED
        self.already_processed_audios = set()
        self.temp_dir = temp_dir
        self.saving_dir = saving_dir
        self.local_media_dir = local_media_dir
        self.headers = headers
        self.timeout = timeout
        self.request_delay = request_delay
        self.errors = {"error_types": {}, "missing_audios": []}

        super(AudioDownloader, self).__init__(master, **self.toplevel_cfg)
        self.withdraw()
        self.title("Скачивание аудио...")
        
        self.pb = ttk.Progressbar(self,
                                  orient='horizontal',
                                  mode='determinate',
                                  **pb_cfg)  # lenght = self.WIDTH - 2 * self.text_padx
        self.pb.grid(column=0, row=0, columnspan=2, padx=5, pady=5)
        self.current_word_label = Label(self, **self.label_cfg)
        self.current_word_label.grid(column=0, row=1, columnspan=2, sticky="news")
        self.label_cfg.pop("relief", None)
        self.deiconify()
        spawn_toplevel_in_center(master, self)

    def catch_fetching_error(self, exception):
        exception_type = str(exception)
        if self.errors["error_types"].get(exception_type) is None:
            self.errors["error_types"][exception_type] = 1
        else:
            self.errors["error_types"][exception_type] += 1
        self.errors["missing_audios"].append(self.current_word_label["text"])

    @staticmethod
    def fetch_audio(url, save_path, headers, timeout=5, exception_action=lambda exc: None) -> bool:
        try:
            r = requests.get(url, headers=headers, timeout=timeout)
            r.raise_for_status()
        except Exception as e:
            exception_action(e)
            return False
        audio_bin = r.content
        with open(save_path, "wb") as audio_file:
            audio_file.write(audio_bin)
        return True

    def download_audio(self, audio_links_list):
        """
        :param audio_links_list:
            [(word, pos, parser_name, url(optional)), ...]
        :return:
        """
        length = len(audio_links_list)

        def iterate(index: int, word: str, pos: str, wp_name: str, url: str):
            """
            :param index:
            :param word:
            :param pos:
            :param wp_name:
            :param url:
            :return:
            """
            self.pb["value"] = min(100.0, round(index / length * 100, 2))
            label_audio_name = f"{word} - {pos}"
            self.current_word_label["text"] = label_audio_name
            self.update()

            save_audio_name = get_save_audio_name(word, pos, wp_name)
            save_audio_path = os.path.join(self.saving_dir, save_audio_name)
            temp_audio_path = os.path.join(self.temp_dir, save_audio_name)
            local_audio_path = get_local_audio_path(word, pos,
                                                    local_audio_folder_path=os.path.join(self.local_media_dir, wp_name),
                                                    with_pos=bool(pos))

            wait_before_next_batch = True
            if word and save_audio_name not in self.already_processed_audios:
                self.already_processed_audios.add(save_audio_name)
                if os.path.exists(temp_audio_path):
                    os.rename(temp_audio_path, save_audio_path)
                    wait_before_next_batch = False
                elif url and (not os.path.exists(save_audio_path) or
                              self.if_copy_encountered == AudioDownloader.CopyEncounterAction.REWRITE):
                    wait_before_next_batch = self.fetch_audio(url, save_audio_path, self.headers, self.timeout,
                                                              self.catch_fetching_error)
                elif local_audio_path:
                    shutil.copy(local_audio_path, save_audio_path)
                    wait_before_next_batch = False

                elif self.if_copy_encountered == AudioDownloader.CopyEncounterAction.SKIP:
                    wait_before_next_batch = False
                else:
                    def skip_encounter():
                        nonlocal wait_before_next_batch
                        if apply_to_all_var.get():
                            self.if_copy_encountered = AudioDownloader.CopyEncounterAction.SKIP
                        wait_before_next_batch = False
                        copy_encounter_tl.destroy()
                        self.grab_set()

                    def rewrite_encounter():
                        nonlocal wait_before_next_batch
                        if apply_to_all_var.get():
                            self.if_copy_encountered = AudioDownloader.CopyEncounterAction.REWRITE
                        copy_encounter_tl.destroy()
                        self.grab_set()
                        wait_before_next_batch = self.fetch_audio(url, save_audio_path, self.headers, self.timeout,
                                                                  self.catch_fetching_error)

                    apply_to_all_var = BooleanVar()

                    copy_encounter_tl = Toplevel(self, **self.toplevel_cfg)
                    copy_encounter_tl.withdraw()

                    message = f"Файл\n  {save_audio_name}  \nуже существует.\nВыберите нужную опцию:"

                    encounter_label = Label(copy_encounter_tl, text=message, relief="ridge",
                                            wraplength=self.winfo_width() * 2 // 3, **self.label_cfg)

                    skip_encounter_button = Button(copy_encounter_tl, text="Пропустить", 
                                                   command=skip_encounter, **self.button_cfg)
                    rewrite_encounter_button = Button(copy_encounter_tl, text="Заменить", 
                                                      command=rewrite_encounter, **self.button_cfg)
                    apply_to_all_button = Checkbutton(copy_encounter_tl, variable=apply_to_all_var,
                                                           text="Применить ко всем", **self.checkbutton_cfg)

                    encounter_label.grid(row=0, column=0, padx=5, pady=5, sticky="news")
                    skip_encounter_button.grid(row=1, column=0, padx=5, pady=5, sticky="news")
                    rewrite_encounter_button.grid(row=2, column=0, padx=5, pady=5, sticky="news")
                    apply_to_all_button.grid(row=3, column=0, padx=5, pady=5, sticky="news")

                    copy_encounter_tl.deiconify()
                    spawn_toplevel_in_center(self, copy_encounter_tl)

                    copy_encounter_tl.bind("<Escape>", lambda event: copy_encounter_tl.destroy())
                    self.wait_window(copy_encounter_tl)
                    self.grab_set()
            else:
                wait_before_next_batch = False

            if audio_links_list:
                delay = self.request_delay if wait_before_next_batch else 0
                next_word, next_pos, next_wp_name, next_url = audio_links_list.pop(0)
                self.master.after(delay, lambda: iterate(index+1, next_word, next_pos, next_wp_name, next_url))
            else:
                if self.errors["missing_audios"]:
                    absent_audio_words = ", ".join(self.errors['missing_audios'])
                    n_errors = f"Количество необработаных слов: {len(self.errors['missing_audios'])}\n"
                    for error_type in self.errors["error_types"]:
                        n_errors += f"{error_type}: {self.errors['error_types'][error_type]}\n"

                    error_message = f"{n_errors}\n\n{absent_audio_words}"
                    messagebox.showerror(message=error_message)
                self.destroy()

        if audio_links_list:
            start_word, start_pos, start_wp_name, start_url = audio_links_list.pop(0)
            iterate(1, start_word, start_pos, start_wp_name, start_url)
        else:
            self.destroy()


if __name__ == "__main__":
    from tkinterdnd2 import Tk

    def start_image_search(word, master, saving_dir, **kwargs):
        image_finder = ImageSearch(search_term=word, master=master, saving_dir=saving_dir,
                                   **kwargs)
        image_finder.start()

    test_urls = ["https://www.google.com/images/branding/googlelogo/1x/googlelogo_color_272x92dp.png"]

    def get_image_links(search_term: None) -> list:
        return ["https://www.google.com/images/branding/googlelogo/1x/googlelogo_color_272x92dp.png"]

    root = Tk()
    root.withdraw()

    root.after(0, start_image_search("test", root, "./", init_urls=test_urls, show_image_width=300))
    root.after(0, start_image_search("test", root, "./", url_scrapper=get_image_links, show_image_width=300))
    root.mainloop()
