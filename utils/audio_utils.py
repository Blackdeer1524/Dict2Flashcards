import os
import shutil
from enum import IntEnum
from tkinter import Button, Checkbutton, Label, Toplevel, BooleanVar
from tkinter import messagebox
from tkinter import ttk

import requests

from .string_utils import remove_special_chars, LETTERS
from .window_utils import spawn_toplevel_in_center

AUDIO_NAME_SPEC_CHARS = '/\\:*?\"<>| '


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
                self.master.after(delay, lambda: iterate(index +1, next_word, next_pos, next_wp_name, next_url))
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