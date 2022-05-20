import copy
import os
from concurrent.futures import ThreadPoolExecutor
from enum import IntEnum
from functools import partial
from io import BytesIO
from tkinter import Entry, Button
from tkinter import Frame
from tkinter import Toplevel
from tkinter import messagebox
from typing import Callable

import requests
from PIL import Image, ImageTk
from requests.exceptions import ConnectionError, RequestException, ConnectTimeout
from tkinterdnd2 import DND_FILES, DND_TEXT

from CONSTS import CURRENT_SYSTEM
from utils.widgets import ScrolledFrame

if CURRENT_SYSTEM == "Linux":
    import gi
    gi.require_version('Gtk', '3.0')
    from gi.repository import Gtk, Gdk
else:
    from PIL import ImageGrab


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


class ImageSearch(Toplevel):
    class StatusCodes(IntEnum):
        NORMAL = 0
        RETRIABLE_FETCHING_ERROR = 1
        NON_RETRIABLE_FETCHING_ERROR = 2
        IMAGE_PROCESSING_ERROR = 3

    def __init__(self, master, search_term, **kwargs):
        """
        master: \n
        search_term: \n
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
        self.search_term: str = search_term
        self.__img_urls: Deque = Deque(kwargs.get("init_urls", []))
        self.__url_scrapper: Callable[[str], list[str]] = kwargs.get("url_scrapper")

        if self.search_term and self.__url_scrapper is not None:
            try:
                self.__img_urls.extend(self.__url_scrapper(self.search_term))
            except ConnectionError:
                messagebox.showerror(message="Check your internet connection")

        self.__button_bg = self.activebackground = "#FFFFFF"
        self.__choose_color = "#FF0000"
        self.__window_bg = kwargs.get("window_bg", "#F0F0F0")
        self.__command_button_params = kwargs.get("command_button_params", {})
        self.__entry_params = kwargs.get("entry_params", {})
        self.__button_padx = kwargs.get("button_padx", 10)
        self.__button_pady = kwargs.get("button_pady", 10)
        Toplevel.__init__(self, master, bg=self.__window_bg)

        self.__headers = kwargs.get("headers")
        self.__timeout = kwargs.get("timeout", 1)
        self.__max_request_tries = kwargs.get("max_request_tries", 5)

        self.__n_images_in_row = kwargs.get("n_images_in_row", 3)
        self.__n_rows = kwargs.get("n_rows", 2)
        self.__n_images_per_cycle = self.__n_rows * self.__n_images_in_row

        self.__pool: ThreadPoolExecutor = ThreadPoolExecutor(max_workers=self.__n_images_per_cycle)

        self.saving_images: list[Image] = []
        self.working_state: list[bool] = []  # indices of picked buttons
        self.button_list: list[Button] = []

        self.optimal_visual_width = kwargs.get("show_image_width")
        self.optimal_visual_height = kwargs.get("show_image_height")
        self.optimal_result_width = kwargs.get("saving_image_width")
        self.optimal_result_height = kwargs.get("saving_image_height")

        self.title("Image search")
        self.__search_field = Entry(self, justify="center", **self.__entry_params)
        self.__search_field.insert(0, self.search_term)
        self.__start_search_button = Button(self, text="Search", command=self.restart_search,
                                          **self.__command_button_params)

        self.__search_field.grid(row=0, column=0, sticky="news",
                               padx=(self.__button_padx, 0), pady=self.__button_pady)
        self.__start_search_button.grid(row=0, column=1, sticky="news",
                                      padx=(0, self.__button_padx), pady=self.__button_pady)
        self.__start_search_button["state"] = "normal" if self.__url_scrapper else "disabled"

        self.__sf = ScrolledFrame(self, scrollbars="both")
        self.__sf.grid(row=1, column=0, columnspan=2)
        self.__sf.bind_scroll_wheel(self)
        self.__inner_frame = self.__sf.display_widget(partial(Frame, bg=self.__window_bg))

        window_width_limit = kwargs.get("window_width_limit")
        window_height_limit = kwargs.get("window_height_limit")
        self.window_width_limit = window_width_limit if window_width_limit is not None else \
            master.winfo_screenwidth() * 6 // 7
        self.window_height_limit = window_height_limit if window_height_limit is not None else \
            master.winfo_screenheight() * 2 // 3

        self.__show_more_gen = self.show_more()
        self.__show_more_button = Button(master=self, text="Show more",
                                       command=lambda x=self.__show_more_gen: next(x), **self.__command_button_params)
        self.__save_button = Button(master=self, text="Save",
                                  command=lambda: self.destroy(), **self.__command_button_params)
        self.__show_more_button.grid(row=3, column=0, sticky="news")
        self.__save_button.grid(row=3, column=1, sticky="news")

        self.__on_closing_action = kwargs.get("on_closing_action")

        self.__cb = None
        self.resizable(False, False)
        self.protocol("WM_DELETE_WINDOW", self.destroy)
        self.bind("<Escape>", lambda event: self.destroy())
        self.bind("<Return>", lambda event: self.destroy())
        self.bind("<Control-v>", lambda event: self.paste_image())
        self.drop_target_register(DND_FILES, DND_TEXT)
        self.dnd_bind('<<Drop>>', self.drop)

    def start(self):
        if CURRENT_SYSTEM == "Linux":
            self.__cb = Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD)
        next(self.__show_more_gen)
        self.resize()

    def restart_search(self):
        self.search_term = self.__search_field.get()
        if not self.search_term:
            messagebox.showerror(message="Empty search query")
            return
        try:
            self.__img_urls = Deque(self.__url_scrapper(self.search_term))
        except ConnectionError:
            messagebox.showerror(message="Check your internet connection")
            return
        self.__inner_frame = self.__sf.display_widget(partial(Frame, bg=self.__window_bg))

        left_indent = 0
        for i in range(len(self.working_state)):
            if self.working_state[i]:
                self.working_state[left_indent] = True
                self.saving_images[left_indent] = copy.deepcopy(self.saving_images[i])

                self.button_list[left_indent].grid_remove()
                b = Button(master=self.__inner_frame,
                           image=self.button_list[i].image,
                           bg=self.__choose_color,
                           activebackground=self.activebackground,
                           command=lambda button_index=left_indent:
                           self.choose_pic(button_index))
                b.image = self.button_list[i].image
                b.grid(row=left_indent // self.__n_images_in_row,
                       column=left_indent % self.__n_images_in_row,
                       padx=self.__button_padx, pady=self.__button_pady, sticky="news")
                self.button_list[left_indent] = b
                
                left_indent += 1
        del self.button_list[left_indent:]
        del self.working_state[left_indent:]
        del self.saving_images[left_indent:]

        self.__show_more_gen = self.show_more()
        self.__show_more_button.configure(command=lambda x=self.__show_more_gen: next(x))

        if self.__img_urls:
            self.__show_more_button["state"] = "normal"
            next(self.__show_more_gen)
        else:
            self.__show_more_button["state"] = "disabled"

    def destroy(self):
        if self.__on_closing_action is not None:
            self.__on_closing_action(self)
        super(ImageSearch, self).destroy()

    def resize(self):
        current_frame_width = self.__inner_frame.winfo_width()
        current_frame_height = self.__inner_frame.winfo_height()
        self.__sf.config(width=min(self.window_width_limit, current_frame_width),
                       height=min(self.window_height_limit - self.command_widget_total_height,
                                  current_frame_height))

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
            response = requests.get(url, headers=self.__headers, timeout=self.__timeout)
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
            image_fetch_tasks.append(self.__pool.submit(self.fetch_image, url))
        return image_fetch_tasks

    def process_bin_data(self, content=None):
        try:
            img = Image.open(BytesIO(content))
            button_img = ImageTk.PhotoImage(
                self.preprocess_image(img, width=self.optimal_visual_width, height=self.optimal_visual_height))
            return ImageSearch.StatusCodes.NORMAL, button_img, img
        except (IOError, UnicodeError):
            return ImageSearch.StatusCodes.IMAGE_PROCESSING_ERROR, None, None

    def choose_pic(self, button_index):
        self.working_state[button_index] = not self.working_state[button_index]
        self.button_list[button_index]["bg"] = self.__choose_color if self.working_state[button_index] else self.__button_bg

    def place_buttons(self, button_image_batch):
        for j in range(len(button_image_batch)):
            b = Button(master=self.__inner_frame, image=button_image_batch[j],
                       bg=self.__button_bg, activebackground=self.activebackground,
                       command=lambda button_index=len(self.working_state): self.choose_pic(button_index))
            b.image = button_image_batch[j]
            b.grid(row=len(self.working_state) // self.__n_images_in_row,
                   column=len(self.working_state) % self.__n_images_in_row,
                   padx=self.__button_padx, pady=self.__button_pady, sticky="news")
            self.working_state.append(False)
            self.button_list.append(b)

        self.__inner_frame.update()
        self.resize()

    def process_url_batch(self, batch_size, n_retries=0):
        """
        :param batch_size: how many images to process
        :param n_retries: (if some error occurred) replace "bad" image with the new one and tries to fetch it.
        :return:
        """
        def add_fetching_to_queue():
            nonlocal n_retries
            if self.__img_urls and n_retries < self.__max_request_tries:
                image_fetching_futures.append(self.__pool.submit(self.fetch_image, self.__img_urls.popleft()[0]))
                n_retries += 1

        button_images_batch = []
        url_batch = self.__img_urls.popleft(batch_size)
        image_fetching_futures = self.schedule_batch_fetching(url_batch)

        while image_fetching_futures:
            fetching_status, content, url = image_fetching_futures.pop(0).result()
            if fetching_status == ImageSearch.StatusCodes.NORMAL:
                processing_status, button_img, img = self.process_bin_data(content)
                if processing_status == ImageSearch.StatusCodes.NORMAL:
                    button_images_batch.append(button_img)
                    self.saving_images.append(img)
                else:
                    add_fetching_to_queue()
            elif fetching_status == ImageSearch.StatusCodes.RETRIABLE_FETCHING_ERROR:
                self.__img_urls.append(url)
                add_fetching_to_queue()
            else:
                add_fetching_to_queue()
        self.place_buttons(button_images_batch)

    def show_more(self):
        self.update()
        self.command_widget_total_height = self.__save_button.winfo_height() + self.__search_field.winfo_height() + \
                                           2 * self.__button_pady

        while self.__img_urls:
            self.process_url_batch(self.__n_images_per_cycle - len(self.working_state) % self.__n_images_in_row)
            if not self.__img_urls:
                break
            yield
        self.__show_more_button["state"] = "disabled"
        yield

    def process_single_image(self, img: Image.Image):
        button_img_batch = [ImageTk.PhotoImage(
            self.preprocess_image(img, width=self.optimal_visual_width, height=self.optimal_visual_height))]
        self.saving_images.append(img)
        self.place_buttons(button_img_batch)

    def drop(self, event):
        if event.data:
            data_path = event.data
            if os.path.exists(data_path):
                img = Image.open(data_path)
                self.process_single_image(img)
            elif data_path.startswith("http"):
                self.__img_urls.appendleft(data_path)
                self.process_url_batch(batch_size=1, n_retries=self.__max_request_tries)
        return event.action

    def paste_image(self):
        if CURRENT_SYSTEM == "Linux":
            def pixbuf2image(pix):
                """Convert gdkpixbuf to PIL image"""
                data = pix.get_pixels()
                w = pix.props.width
                h = pix.props.height
                stride = pix.props.rowstride
                mode = "RGB"
                if pix.props.has_alpha == True:
                    mode = "RGBA"
                im = Image.frombytes(mode, (w, h), data, "raw", mode, stride)
                return im

            if self.__cb.wait_is_image_available():
                pixbuf = self.__cb.wait_for_image()
                self.process_single_image(pixbuf2image(pixbuf))
        else:
            self.process_single_image(ImageGrab.grabclipboard())


if __name__ == "__main__":
    from tkinterdnd2 import Tk
    from parsers.image_parsers.google import get_image_links

    def start_image_search(word, master, **kwargs):
        image_finder = ImageSearch(search_term=word, master=master, **kwargs)
        image_finder.start()

    test_urls = ["https://www.google.com/images/branding/googlelogo/1x/googlelogo_color_272x92dp.png"]

    # def get_image_links(search_term: None) -> list:
    #     return ["https://www.google.com/images/branding/googlelogo/1x/googlelogo_color_272x92dp.png"]

    root = Tk()
    # root.withdraw()

    def on_closing(instance: ImageSearch):
        res = []
        for i in range(len(instance.working_state)):
            if instance.working_state[i]:
                instance.saving_images[i].save(f"./{i}.png")


    root.after(0, start_image_search("test", root, url_scrapper=get_image_links, show_image_width=300,
                                     on_closing_action=on_closing))
    root.mainloop()
