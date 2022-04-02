import bs4
from tkinter import Tk
from tkinter.filedialog import askdirectory
import os


file_open_window = Tk()
file_open_window.withdraw()
DIR = askdirectory(title="Выберете директорию с PDF выгрузками")
file_open_window.destroy()
os.chdir(DIR)


if len(DIR) == 0:
    quit()

# DIR = r"C:\Users\Danila\Desktop\Takeout\Google Play Книги"


soup_list = []

for book in os.listdir():
    in_book_dir =  './' + book
    if book[-3:] == "txt":
        continue
    for item in os.listdir(in_book_dir):
        if ".html" == item[-5:]:
            PATH = in_book_dir + "/" + item
            with open(PATH, "r", encoding="utf8") as notes_file:
                soup_list.append((book, bs4.BeautifulSoup(notes_file, "html.parser")))


words_per_book = { }
seen_set = set()

for name, soup in soup_list:
    all_notes = []
    for note in soup.find_all("div", {"class": "note"}):
        text = note.find("div", {"class": "book-text"}).text
        text = text.strip().replace('\n', '').replace('"', '')
        if text not in seen_set:
            all_notes.append(text)
            seen_set.add(text)
    words_per_book[name] = all_notes

file_open_window = Tk()
file_open_window.withdraw()
SAVE_DIR = askdirectory(title="Выберете директорию для файлов со словами")
file_open_window.destroy()

for key in words_per_book:
    with open(r"{}/{}.txt".format(SAVE_DIR, key), "w") as f:
        for line in words_per_book[key]:
            f.write(line + '\n')
