import os
import string


os.chdir("./parsers/media/")


ascii_lowercase = set(string.ascii_lowercase)
catalogs = ["0-9"] + list(ascii_lowercase)


for local_audio_dir in os.listdir():
    if not os.path.isdir(local_audio_dir):
        continue

    for letter_dir in catalogs:
        letter_dir_path = os.path.join(local_audio_dir, letter_dir)
        for root, dirs, files in os.walk(letter_dir_path):
            for filename in files:
                file_path = os.path.join(root, filename)

                extention_ind = filename.rfind(".")

                if extention_ind == -1:
                    name = filename
                    extention = ".mp3"
                    new_file_path = os.path.join(root, f"{name}{extention}")
                else:
                    name, extention = filename[:extention_ind], filename[extention_ind:]
                    name = name.replace(".mp3", "")
                    if extention == ".mp3":
                        if name[-1] == "$":
                            new_file_path = os.path.join(root, f"{name[:-1]}{extention}")
                        else:
                            new_file_path = os.path.join(root, f"{name}{extention}")
                    else:
                        new_file_path = os.path.join(root, f"{name}{extention}.mp3")
                os.rename(file_path, new_file_path)
