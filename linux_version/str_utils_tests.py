from utils import SearchType, string_search, remove_special_chars


if __name__ == "__main__":
    print(SearchType["exact"])
    print(SearchType(0).name)
    print([search_type.name for search_type in SearchType])
    assert not string_search("besty", "est", search_type=SearchType.exact, case_sencitive=False)
    assert string_search("a lot happened", "lot", search_type=SearchType.exact, case_sencitive=False)
    assert string_search("a estiful", "est", search_type=SearchType.forward, case_sencitive=False)
    assert string_search(",estiful", "est", search_type=SearchType.forward, case_sencitive=False)
    assert not string_search("crestful", "est", search_type=SearchType.forward, case_sencitive=False)
    assert not string_search("bestiful", "est", search_type=SearchType.forward, case_sencitive=False)
    assert string_search("best", "est", search_type=SearchType.backward, case_sencitive=False)
    assert string_search("best№1", "est", search_type=SearchType.backward)

    assert string_search("ABC", "C")
    assert not string_search("ABC", "D")
    assert string_search("ABC", "")
    assert string_search("ABC", " ABC")
    assert string_search("ABC", "ABC ")
    assert string_search("ABC", " ABC ")
    assert string_search("ABC", "ABC")
    assert not string_search("ABC", "ABCD")
    assert string_search("ABC", "AB")
    assert string_search("come across", "come")
    assert string_search("come across", "across")
    assert string_search("come sth across", " ")
    assert not string_search("", "come")


    assert remove_special_chars("%^&*(*&^%khafsdkjlh2i$%& o1u3123 ioufhkddlshfldks n6e%^&*(*&^%") == \
        "khafsdkjlh2i o1u3123 ioufhkddlshfldks n6e"

    assert remove_special_chars("khafsdkjlh2io1u3123 ioufhkddlshfldks ne") == \
        "khafsdkjlh2io1u3123 ioufhkddlshfldks ne"

    assert remove_special_chars("kha!#$@$@!fsdkjlh2&*(io1u3123^((&^%#ioufhkddlshfldks ne$*&") == \
        "kha fsdkjlh2 io1u3123 ioufhkddlshfldks ne"

    assert remove_special_chars('!"#$%&\'()*+,-./:;<=>?@[\\]^_`{|}~ k-k', '-') == \
        "k-k"
    assert remove_special_chars("dshhf hgkj fsf o1237*&( s", "-", " ") == "dshhf hgkj fsf o1237*&( s".replace(" ", '-')
    assert remove_special_chars("") == ""
