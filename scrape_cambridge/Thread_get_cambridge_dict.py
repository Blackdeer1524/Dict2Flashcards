import concurrent.futures
import json
import os
import string
import time

import bs4
import requests

from cambridge_parser import define

os.chdir("DICT/cambridge_dict")
REQUEST_SLEEP_TIME = 0


def get_headers():
    user_agent = 'Mozilla/5.0 (Windows NT 6.1; Win64; x64)'
    headers = {'User-Agent': user_agent}
    return headers


def get_word(word, exception_file, request_depth=0) -> dict:
    time.sleep(REQUEST_SLEEP_TIME)
    try:
        return define(word=word, headers=get_headers())
    except ValueError:
        pass
    except AttributeError:
        pass
        # exception_file.write(word + '\n')
    except Exception as e:
        print("\n\n" + "=" * 30)
        print("Error", word, e)
        print("=" * 30 + "\n")
        if request_depth < 5:
            time.sleep(30)
            return get_word(word, exception_file, request_depth+1)
        else:
            exception_file.write(word + '\n')
    return {}


def get_section_content(section_url):
    try:
        req = requests.get(section_url, headers=get_headers())
        return req.content
    except Exception as e:
        print("\n\n" + "=" * 30)
        print("SectionError", section_url, e)
        print("=" * 30 + "\n")
        time.sleep(15)
        return get_section_content(section_url)


def get_data_from_page(page_name, exception_file, executor: concurrent.futures.ThreadPoolExecutor) -> dict:
    try:
        page_url = f"https://dictionary.cambridge.org/browse/english/{page_name}/"
        time.sleep(REQUEST_SLEEP_TIME)
        response = requests.get(page_url, headers=get_headers())
        results = {}
        if response.status_code == 200:
            page_sections_futures = []
            letter_page_content = response.content
            letter_page_soup = bs4.BeautifulSoup(letter_page_content, "html.parser")
            all_words_block = letter_page_soup.find("div", {"class": "hdf ff-50 lmt-15"})
            word_range_blocks = all_words_block.find_all("a", {"class": "dil tcbd"})
            for current_words_range in word_range_blocks:
                section_url = current_words_range["href"]
                page_sections_futures.append(executor.submit(get_section_content, section_url))

            word_futures = []
            last_log_length = 0
            section_n = 1
            section_logs = ("Section % \\\\", "Section % //")
            for section_future in concurrent.futures.as_completed(page_sections_futures):
                log_string = f"\r{section_logs[section_n % 2]}{section_n / len(page_sections_futures) * 100: .2f}%"
                print("\r" + " " * last_log_length, end="")
                print(log_string, end="")
                section_n += 1
                last_log_length = len(log_string)

                section_content = section_future.result()
                section_soup = bs4.BeautifulSoup(section_content, "html.parser")
                section_words_block = section_soup.find("div", {"class": "hdf ff-50 lmt-15"})
                word_blocks = section_words_block.find_all("a", {"class": "tc-bd"})
                for word_link_block in word_blocks:
                    word_link_postfix = word_link_block["href"]
                    word = word_link_postfix.split(sep="/")[-1].replace("-", " ")
                    word_futures.append(executor.submit(get_word, word, exception_file))

            word_index = 0
            word_logs = ("Words % \\\\", "Words % //")
            for word_future in concurrent.futures.as_completed(word_futures):
                log_string = f"\r{word_logs[word_index % 2]}{word_index / len(word_futures) * 100: .2f}%"
                print("\r" + " " * last_log_length, end="")
                print(log_string, end="")
                word_index += 1
                last_log_length = len(log_string)

                results.update(word_future.result())
        else:
            time.sleep(30)
            results = get_data_from_page(page_name, exception_file, executor)
    except:
        time.sleep(30)
        results = get_data_from_page(page_name, exception_file, executor)
    return results


def main():
    result_dict = {}
    page_pointers = ["0-9"] + list(string.ascii_lowercase)

    def iteration(pointer, exception_file, executor: concurrent.futures.ThreadPoolExecutor) -> None:
        nonlocal result_dict
        print(f"\n{pointer} start...")
        section_file_path = f"./{pointer}_local_cambridge_dict.json"
        if not os.path.exists(section_file_path):
            result_dict = get_data_from_page(pointer, exception_file, executor)
            with open(section_file_path, "w", encoding="utf8") as write_file:
                json.dump(result_dict, write_file, indent=3)
            result_dict.clear()
        print(f"\n{pointer} done.\n")

    # max_workers=20
    with concurrent.futures.ThreadPoolExecutor() as executor:
        for pointer in page_pointers:
            exception_file = open(f"{os.getcwd()}/exceptions.txt", "a", encoding="UTF8")
            iteration(pointer, exception_file, executor)
            exception_file.close()


if __name__ == "__main__":
    main()
