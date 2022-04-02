import os
import json


# media_folder_path = "C:/Users/Danila/AppData/Roaming/Anki2/1-й пользователь/collection.media/sentence_mining"
# for word_folder in os.listdir(media_folder_path):
#     sub_folder_path = media_folder_path + "/" + word_folder
#     for meaning_folder in os.listdir(sub_folder_path):
#         image_folder = sub_folder_path + "/" + meaning_folder
#         for image_name in os.listdir(image_folder):
#             image_path = image_folder + "/" + image_name
#             new_image_path = media_folder_path + "/mined-" + image_name
#             if not os.path.exists(new_image_path):
#                 os.rename(image_path, new_image_path)

json_deck_path = "C:/Users/Danila/Desktop/English_language/deck.json"
with open(json_deck_path, encoding="UTF8") as f:
    deck = json.load(f)

for i in range(len(deck["media_files"])):
    current_media_path = deck["media_files"][i]
    if "mined" in current_media_path:
        s_current_media_path = current_media_path.split("/")
        image_name = s_current_media_path[-1]
        new_image_name = f"mined-{image_name.replace('mined-', '')}"
        new_path = f"{new_image_name}"
        deck["media_files"][i] = new_path

for note_i in range(len(deck["notes"])):
    img_field = deck["notes"][note_i]["fields"][-3]
    if "mined" in img_field:
        s_img_field = img_field.split(sep="'")
        if len(s_img_field) <= 2:
            s_img_field = s_img_field[0].split('"')
        for image_path_ind in range(1, len(s_img_field), 2):
            image_path = s_img_field[image_path_ind]
            s_image_path = image_path.split("/")
            image_name = s_image_path[-1]
            new_image_name = f"mined-{image_name.replace('mined-', '')}"
            new_path = f"{new_image_name}"
            s_img_field[image_path_ind] = new_path
        new_img_field = "'".join(s_img_field)
        deck["notes"][note_i]["fields"][-3] = new_img_field

with open(json_deck_path, "w", encoding="UTF8") as f:
    json.dump(deck, f, indent=5)
