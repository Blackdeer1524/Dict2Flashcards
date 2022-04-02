import concurrent.futures
import os
import string
import time
import re

import bs4
import requests


if not os.path.exists("./DICT"):
    os.makedirs("./DICT/")
os.chdir("./DICT")

REQUEST_SLEEP_TIME = 0
CAMBRIDGE_PAGE_LINK = "https://dictionary.cambridge.org"

SCRIPT_PATTERN = re.compile(r"(<script(.|\n)*?</script>)|(<noscript(.|\n)*?</noscript>)|(<style(.|\n)*?</style>)|(<meta.*?>)|(<link.*?>)")
NEW_LINE_PATTERN = re.compile(" *\r*\n[\r\n ]*")


def lightweight(file_content):
    trash_free_content = re.sub(SCRIPT_PATTERN, "", file_content)
    fixed_height_new_line_content = re.sub(NEW_LINE_PATTERN, "\n", trash_free_content)
    return fixed_height_new_line_content.strip()


def get_headers():
    user_agent = 'Mozilla/5.0 (Windows NT 6.1; Win64; x64)'
    headers = {'User-Agent': user_agent}
    return headers


def get_section_content(section_url, request_depth=0):
    try:
        req = requests.get(section_url, headers=get_headers(), timeout=5)
        return req.content
    except Exception as e:
        print("\n\n" + "=" * 30)
        print("SectionError", section_url, e)
        print("=" * 30 + "\n")
        return get_section_content(section_url, request_depth+1)


def download_page(word, page_content, saving_location="./"):
    page_content = lightweight(page_content)
    if not saving_location.endswith("/"):
        saving_location += "/"
    with open(f"{saving_location}{word}_{int(time.time()*100)}.html", "w", encoding="utf-8") as f:
        f.write(page_content)


def get_word_page_content(word, link) -> tuple:
    try:
        req = requests.get(link, headers=get_headers(), timeout=5)
        page_content = req.content.decode("UTF-8")
        return word, page_content
    except Exception as e:
        print("\n\n" + "=" * 30)
        print("Word page content error", link, e)
        print("=" * 30 + "\n")
        return get_word_page_content(word, link)


def get_data_from_page(page_name, executor: concurrent.futures.ThreadPoolExecutor) -> None:
    try:
        page_saving_location = f"./{page_name}/"
        if not os.path.exists(page_saving_location):
            os.makedirs(page_saving_location)
        CURRENT_DICT_PAGES = set([name[:-18] for name in os.listdir(page_saving_location)])

        page_url = f"{CAMBRIDGE_PAGE_LINK}/browse/english/{page_name}/"
        response = requests.get(page_url, headers=get_headers(), timeout=5)

        if response.status_code == 200:
            letter_page_content = response.content
            letter_page_soup = bs4.BeautifulSoup(letter_page_content, "html.parser")
            all_words_block = letter_page_soup.find("div", {"class": "hdf ff-50 lmt-15"})
            word_range_blocks = all_words_block.find_all("a", {"class": "dil tcbd"})

            section_step = 1

            last_log_length = 0
            s = False
            section_logs = ("Section % \\\\", "Section % //")
            for batch_start in range(0, len(word_range_blocks), section_step):
                log_string = f"\r{section_logs[s]}{batch_start / len(word_range_blocks) * 100: .2f}%"
                print("\r" + " " * last_log_length, end="")
                print(log_string, end="")
                s = not s
                last_log_length = len(log_string)

                page_sections_futures = []
                for current_words_range in word_range_blocks[batch_start:batch_start+section_step]:
                    section_url = current_words_range["href"]
                    page_sections_futures.append(executor.submit(get_section_content, section_url))

                page_content_futures = []
                for section_future in concurrent.futures.as_completed(page_sections_futures):
                    section_content = section_future.result()
                    section_soup = bs4.BeautifulSoup(section_content, "html.parser")
                    section_words_block = section_soup.find("div", {"class": "hdf ff-50 lmt-15"})
                    word_blocks = section_words_block.find_all("a", {"class": "tc-bd"})
                    for word_link_block in word_blocks:
                        word_link_postfix = word_link_block["href"]
                        word = word_link_postfix.split(sep="/")[-1]
                        word_page_link = CAMBRIDGE_PAGE_LINK + word_link_postfix
                        if word not in CURRENT_DICT_PAGES:
                            page_content_futures.append(executor.submit(get_word_page_content, word, word_page_link))

                download_futures = []
                for page_content_future in concurrent.futures.as_completed(page_content_futures):
                    word, content = page_content_future.result()
                    download_futures.append(executor.submit(download_page, word, content, page_saving_location))

                for download_future in concurrent.futures.as_completed(download_futures):
                    download_future.result()
        else:
            get_data_from_page(page_name, executor)
    except Exception as e:
        print("\n\nget_data_from_page error!", e)
        get_data_from_page(page_name, executor)


def main():
    page_pointers = ["0-9"] + list(string.ascii_lowercase)

    def iteration(pointer, executor: concurrent.futures.ThreadPoolExecutor) -> None:
        print(f"\n\n{pointer} start...")
        get_data_from_page(pointer, executor)
        print(f"\n\n{pointer} done.\n")

    # max_workers=20
    with concurrent.futures.ThreadPoolExecutor() as executor:
        for pointer in page_pointers:
            iteration(pointer, executor)


if __name__ == "__main__":
    main()
    # from local_cambridge_parser import define
    # import json
    #
    # with open("./tests.txt", "r") as tests_f:
    #     tests = tests_f.readlines()
    #
    # for line in tests:
    #     word = line.strip()
    #     link = "https://dictionary.cambridge.org/dictionary/english/" + word
    #     _, content = get_word_page_content(word, link)
    #     download_page(word, content, saving_location="./DICT/")
    #
    # for downloaded_page_name in os.listdir("./DICT/"):
    #     word = downloaded_page_name[:-18]
    #     search_test_path = f"./tests/original_{word}.json"
    #     if not os.path.exists(search_test_path):
    #         print(search_test_path, 'doesn\'t exist')
    #         continue
    #     with open(search_test_path, "r", encoding="UTF-8") as right_j_f:
    #         right_res = json.load(right_j_f)
    #
    #     with open(f"./DICT/{downloaded_page_name}", "r", encoding="utf-8") as f:
    #         obtained_content = f.read()
    #     current_res = define(obtained_content)
    #
    #     print(word, ": ", sep="", end="")
    #     if current_res == right_res:
    #         print("Pass")
    #     else:
    #         with open(f"./wrong_{word}.json", "w", encoding="UTF-8") as wrong_j_f:
    #             json.dump(current_res, wrong_j_f, indent=4)
    #         print("Failed")
