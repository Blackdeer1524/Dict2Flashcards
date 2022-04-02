from get_cambridge_dict import *
import time


os.chdir(r"C:\Users\Danila\Desktop\sentence_mining")
TIME_STAMP = int(time.time())


def get_batch(dataset, step):
    for i in range(0, len(dataset), step):
        yield dataset[i:i+step], round((i + 1 + step) / len(dataset), 2) * 100


async def main():
    results = []

    async def get_word_wrapper(session, word, ex_file):
        nonlocal results
        parsed_word = await get_word(session, word, ex_file)
        results.extend(parsed_word)

    def save_files(portion):
        print("\r" + " " * 100, end="")
        print(f"\r{portion}% save", end="")
        nonlocal results
        with open(f"./exceptions_local_cambridge_dict_{TIME_STAMP}.json", "w") as write_file:
            json.dump(results, write_file)

    # with open(f"{os.getcwd()}/DICT/exceptions.txt") as file:
    #     data = [i.strip() for i in file.readlines()]

    with open(f"{os.getcwd()}/DICT/exceptions_2.txt") as file:
        data = [i.strip() for i in file.readlines()]

    step = len(data) // 100
    print(f"{step} per batch")
    with open(f"{os.getcwd()}/DICT/exceptions_3.txt", "w") as ex_file:
        conn = aiohttp.TCPConnector(limit=2)
        timeout = aiohttp.ClientTimeout(total=10 * 60)
        async with aiohttp.ClientSession(connector=conn, timeout=timeout, trust_env=True) as session:
            for batch, portion in get_batch(data, step):
                tasks = []
                for word in batch:
                    tasks.append(get_word_wrapper(session, word, ex_file))
                await asyncio.gather(*tasks)
                save_files(portion)

sem = asyncio.Semaphore(100)
loop = asyncio.get_event_loop()
loop.run_until_complete(main())
loop.run_until_complete(asyncio.sleep(0.250))
loop.close()
