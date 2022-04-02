import json
import os
import string
from cambridge_parser import define


os.chdir("./DICT")
SEEN = set()
FIRST_HELP_USER_AGENTS = []
SECOND_HELP_USER_AGENTS = []


def get_random_headers():
    user_agent = 'Mozilla/5.0 (Windows NT 6.1; Win64; x64)'
    headers = {'User-Agent': user_agent}
    return headers


async def get_word(session, word, exception_file, d=0):
    try:
        parsed_result = await parse(session=session, word=word, headers=get_random_headers())
        return translate_word(parsed_result)
    except ValueError:
        exception_file.write(word + '\n')
    except AttributeError:
        pass
        # exception_file.write(word + '\n')
    except Exception as e:
        exception_file.write(word + '\n')
        print("\n\n" + "=" * 30)
        print("Error", word, e)
        print("=" * 30 + "\n")
        # if d < 5:
        #     await asyncio.sleep(30)
        #     return await get_word(session, word, exception_file, d+1)
        # else:
        #     exception_file.write(word + '\n')
    return []


async def get_links_from_letter_page(session, page_name, exception_file):
    page_url = f"https://dictionary.cambridge.org/browse/english/{page_name}/"
    page_results = []
    async with session.get(page_url, headers=get_random_headers()) as response:
        page_content = await response.content.read()
        response.close()
    main_soup = bs4.BeautifulSoup(page_content, "html.parser")
    main_links_block = main_soup.find("div", {"class": "hdf ff-50 lmt-15"})
    found_main_links = main_links_block.find_all("a", {"class": "dil tcbd"})

    async def one_iteration(sess, w, exception):
        nonlocal page_results
        found_result = await get_word(session=sess, word=w, exception_file=exception)
        page_results.extend(found_result)
        # page_results.append(w)

    async def get_section(sess, url):
        try:
            async with sess.get(url, headers=get_random_headers()) as section_response:
                return await section_response.content.read()
        except Exception as e:
            print("\n\n" + "=" * 30)
            print("SectionError", url, e)
            print("=" * 30 + "\n")
            return await get_section(sess, url)

    for main_links_block in found_main_links:
        get_word_tasks = []
        section_url = main_links_block["href"]

        section_content = await get_section(session, section_url)
        # async with session.get(section_url, headers=get_random_headers()) as section_response:
        #     section_content = await section_response.content.read()
        #     section_response.close()

        section_soup = bs4.BeautifulSoup(section_content, "html.parser")
        section_links_block = section_soup.find("div", {"class": "hdf ff-50 lmt-15"})
        found_section_links = section_links_block.find_all("a", {"class": "tc-bd"})
        for section_links_block in found_section_links:
            word_link_postfix = section_links_block["href"]
            word = word_link_postfix.split(sep="/")[-1].replace("-", " ")
            get_word_tasks.append(one_iteration(session, word, exception_file))
        await asyncio.gather(*get_word_tasks)
    return page_results


async def main():
    exception_file = open(f"{os.getcwd()}/exceptions.txt", "w")
    result_dict = []
    links = list(string.ascii_lowercase)
    links.append("0-9")

    async def iteration(session, pointer, exceptions):
        nonlocal result_dict
        print(f"{pointer} start...")
        current_page_results = await get_links_from_letter_page(session, pointer, exceptions)
        result_dict.extend(current_page_results)
        # with open("./local_cambridge_dict.txt", "w") as write_file:
        #     write_file.write("\n".join(result_dict) + "\n")
        with open(f"./{pointer}_local_cambridge_dict.json", "w") as write_file:
            json.dump(result_dict, write_file)
        result_dict = []
        print(f"\n{pointer} done.")

    tasks = []
    # force_close=True
    # https://stackoverflow.com/questions/51248714/aiohttp-client-exception-serverdisconnectederror-is-this-the-api-servers-issu
    conn = aiohttp.TCPConnector(limit=2)
    timeout = aiohttp.ClientTimeout(total=10*60)
    async with aiohttp.ClientSession(connector=conn, timeout=timeout, trust_env=True) as session:
        for page_pointer in links:
            # await iteration(session, page_pointer, exception_file)
            tasks.append(iteration(session, page_pointer, exception_file))
        await asyncio.gather(*tasks)
    exception_file.close()


if __name__ == "__main__":
    # policy = asyncio.WindowsSelectorEventLoopPolicy()
    # asyncio.set_event_loop_policy(policy)
    sem = asyncio.Semaphore(100)
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main())
    loop.run_until_complete(asyncio.sleep(0.250))
    loop.close()
